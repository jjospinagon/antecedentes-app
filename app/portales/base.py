"""
Contrato comun de los portales + utilidades tolerantes a cambios de HTML.

Los portales del Estado cambian ids y maquetacion sin aviso. Por eso todos
los localizadores se declaran como LISTAS de candidatos y se prueban en
orden; si ninguno funciona el flujo NO se rompe: la app te muestra la
pantalla real en el celular y tu completas el campo con el dedo.
"""
from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass, field
from typing import Callable, Iterable

from playwright.async_api import BrowserContext, Page, Response

from .. import config

Log = Callable[[str], None]


# ---------------------------------------------------------------- datos ---
@dataclass
class DatosConsulta:
    """Datos que digita el usuario una sola vez."""
    tipo_doc: str                      # CC | CE | TI | PA | NIT
    numero: str                        # solo digitos
    fecha_expedicion: str | None = None  # 'YYYY-MM-DD'
    nombre: str | None = None          # opcional, solo para nombrar el PDF

    @property
    def es_nit(self) -> bool:
        return self.tipo_doc.upper() == "NIT"

    @property
    def fecha_ddmmyyyy(self) -> str | None:
        if not self.fecha_expedicion:
            return None
        try:
            a, m, d = self.fecha_expedicion.split("-")
            return f"{d}/{m}/{a}"
        except ValueError:
            return self.fecha_expedicion


@dataclass
class Resultado:
    portal_id: str
    portal_nombre: str
    ok: bool
    pdf: bytes | None = None
    detalle: str = ""
    bitacora: list[str] = field(default_factory=list)


# ------------------------------------------------------------ utilidades ---
async def _visible(page: Page, selector: str) -> bool:
    try:
        loc = page.locator(selector).first
        return await loc.is_visible(timeout=1200)
    except Exception:
        return False


async def escribir(page: Page, candidatos: Iterable[str], valor: str,
                   log: Log, etiqueta: str = "campo") -> bool:
    """Escribe `valor` en el primer selector visible de `candidatos`."""
    for sel in candidatos:
        if await _visible(page, sel):
            try:
                loc = page.locator(sel).first
                await loc.click(timeout=config.TIMEOUT_ACCION_MS)
                await loc.fill("")
                await loc.type(valor, delay=35)
                log(f"  OK {etiqueta} -> {sel}")
                return True
            except Exception as e:  # pragma: no cover
                log(f"  fallo {etiqueta} en {sel}: {type(e).__name__}")
    log(f"  AVISO: no se ubico '{etiqueta}'. Diligencialo manualmente en pantalla.")
    return False


async def elegir(page: Page, candidatos: Iterable[str], *,
                 valores: Iterable[str] = (), etiquetas: Iterable[str] = (),
                 log: Log, etiqueta: str = "lista") -> bool:
    """Selecciona una opcion de un <select> probando por value y por texto."""
    for sel in candidatos:
        if not await _visible(page, sel):
            continue
        loc = page.locator(sel).first
        for v in valores:
            try:
                await loc.select_option(value=str(v), timeout=4000)
                log(f"  OK {etiqueta} -> {sel} (value={v})")
                return True
            except Exception:
                pass
        for t in etiquetas:
            try:
                await loc.select_option(label=re.compile(t, re.I), timeout=4000)
                log(f"  OK {etiqueta} -> {sel} (texto~{t})")
                return True
            except Exception:
                pass
    log(f"  AVISO: no se ubico '{etiqueta}'. Selecciona la opcion en pantalla.")
    return False


async def pulsar(page: Page, candidatos: Iterable[str], log: Log,
                 etiqueta: str = "boton") -> bool:
    for sel in candidatos:
        if await _visible(page, sel):
            try:
                await page.locator(sel).first.click(timeout=config.TIMEOUT_ACCION_MS)
                log(f"  OK {etiqueta} -> {sel}")
                return True
            except Exception as e:
                log(f"  fallo {etiqueta} en {sel}: {type(e).__name__}")
    log(f"  AVISO: no se ubico '{etiqueta}'.")
    return False


async def marcar_checkboxes(page: Page, log: Log) -> None:
    """Acepta terminos/politicas: marca todo checkbox visible sin marcar."""
    try:
        cajas = page.locator("input[type=checkbox]:visible, .ui-chkbox-box:visible")
        for i in range(min(await cajas.count(), 6)):
            c = cajas.nth(i)
            try:
                if await c.get_attribute("type") == "checkbox":
                    if not await c.is_checked():
                        await c.check(timeout=3000, force=True)
                else:
                    await c.click(timeout=3000)
                log(f"  OK acepto casilla {i + 1}")
            except Exception:
                pass
    except Exception:
        pass


async def reposar(page: Page, ms: int = 1200) -> None:
    try:
        await page.wait_for_load_state("networkidle", timeout=ms * 5)
    except Exception:
        pass
    await asyncio.sleep(ms / 1000)


# -------------------------------------------------------- captura de PDF ---
class CazadorPDF:
    """
    Intercepta el PDF que produce el portal por cualquiera de las tres vias
    posibles: descarga directa, respuesta HTTP application/pdf, o pestana
    emergente. Si ninguna aplica, se imprime la pagina a PDF.
    """

    def __init__(self, ctx: BrowserContext, log: Log):
        self.ctx = ctx
        self.log = log
        self.bytes_pdf: bytes | None = None
        self._paginas: list[Page] = []

    def enganchar(self, page: Page) -> None:
        page.on("download", self._on_download)
        page.on("response", self._on_response)
        self.ctx.on("page", self._on_page)

    # -- handlers (sincronos que lanzan tareas) --
    def _on_download(self, download) -> None:
        asyncio.create_task(self._leer_descarga(download))

    def _on_response(self, resp: Response) -> None:
        tipo = (resp.headers or {}).get("content-type", "")
        if "application/pdf" in tipo.lower():
            asyncio.create_task(self._leer_respuesta(resp))

    def _on_page(self, page: Page) -> None:
        self._paginas.append(page)
        page.on("download", self._on_download)
        page.on("response", self._on_response)

    async def _leer_descarga(self, download) -> None:
        try:
            ruta = await download.path()
            if ruta:
                with open(ruta, "rb") as fh:
                    self.bytes_pdf = fh.read()
                self.log(f"  PDF capturado por descarga ({len(self.bytes_pdf)} bytes)")
        except Exception as e:
            self.log(f"  descarga no legible: {e}")

    async def _leer_respuesta(self, resp: Response) -> None:
        try:
            data = await resp.body()
            if data[:4] == b"%PDF":
                self.bytes_pdf = data
                self.log(f"  PDF capturado por respuesta HTTP ({len(data)} bytes)")
        except Exception:
            pass

    async def resolver(self, page: Page) -> bytes:
        """Devuelve el PDF interceptado o imprime la pagina visible."""
        for _ in range(10):
            if self.bytes_pdf:
                return self.bytes_pdf
            await asyncio.sleep(0.4)

        # Pestana emergente que muestra el PDF en visor
        for p in self._paginas:
            try:
                if p.url.lower().endswith(".pdf") or "pdf" in p.url.lower():
                    r = await self.ctx.request.get(p.url)
                    data = await r.body()
                    if data[:4] == b"%PDF":
                        self.log("  PDF capturado desde pestana emergente")
                        return data
            except Exception:
                pass

        objetivo = self._paginas[-1] if self._paginas else page
        self.log("  Sin PDF nativo: se imprime la pantalla del resultado")
        try:
            await objetivo.emulate_media(media="print")
        except Exception:
            pass
        return await objetivo.pdf(
            format="Letter", print_background=True,
            margin={"top": "12mm", "bottom": "12mm", "left": "10mm", "right": "10mm"},
        )


# ------------------------------------------------------------- contrato ---
class Portal:
    id: str = "base"
    nombre: str = "Portal"
    entidad: str = ""
    url: str = ""
    admite_nit: bool = False
    admite_persona_natural: bool = True
    nota: str = ""

    def aplica(self, datos: DatosConsulta) -> bool:
        return self.admite_nit if datos.es_nit else self.admite_persona_natural

    async def abrir(self, page: Page, log: Log) -> None:
        log(f"Abriendo {self.url}")
        await page.goto(self.url, timeout=config.TIMEOUT_NAV_MS,
                        wait_until="domcontentloaded")
        await reposar(page, 900)

    async def preparar(self, page: Page, datos: DatosConsulta, log: Log) -> None:
        """Diligencia todo lo automatizable y deja el captcha al humano."""
        raise NotImplementedError

    async def enviar(self, page: Page, log: Log) -> None:
        raise NotImplementedError
