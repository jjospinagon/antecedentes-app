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


# --------------------------------------------------- captcha visible ------
# El reto de imagenes de reCAPTCHA a veces se abre desplazado y su boton
# "Verificar" queda fuera de la pantalla espejo. Este script fija el popup del
# reto arriba-izquierda, dentro de la vista, para que SIEMPRE se pueda llegar
# a las casillas y a Verificar. No toca el captcha en si; solo lo reubica.
FIX_CAPTCHA_JS = r"""
(() => {
  const CSS = `
    div:has(> div > iframe[title*="recaptcha challenge"]),
    div:has(> iframe[title*="recaptcha challenge"]) {
      position: fixed !important;
      top: 6px !important; left: 6px !important;
      right: auto !important; bottom: auto !important;
      margin: 0 !important; max-height: none !important;
      transform: none !important; z-index: 2147483647 !important;
    }`;
  const poner = () => {
    if (!document.head) return;
    let s = document.getElementById('__fixcap');
    if (!s) { s = document.createElement('style'); s.id = '__fixcap';
      s.textContent = CSS; document.head.appendChild(s); }
  };
  if (document.readyState !== 'loading') poner();
  document.addEventListener('DOMContentLoaded', poner);
})();
"""


# ---------------------------------------------------------------- datos ---
@dataclass
class DatosConsulta:
    """Datos que digita el usuario una sola vez."""
    tipo_doc: str                      # CC | CE | TI | PA | NIT
    numero: str                        # solo digitos
    fecha_expedicion: str | None = None  # 'YYYY-MM-DD'
    nombre: str | None = None          # opcional, solo para nombrar el PDF
    # Solo los exige el certificado de delitos sexuales (Ley 1918/2018):
    # va dirigido a una entidad, que debe identificarse.
    entidad: str | None = None         # razon social de quien consulta
    nit_entidad: str | None = None     # NIT con digito de verificacion

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
    """
    Escribe `valor` en el primer selector visible de `candidatos` y VERIFICA
    que el dato haya quedado. Si el campo se quedo vacio (pasaba con Empresa y
    NIT de delitos sexuales), reintenta con otra tecnica antes de rendirse.
    """
    for sel in candidatos:
        if not await _visible(page, sel):
            continue
        loc = page.locator(sel).first
        try:
            await loc.scroll_into_view_if_needed(timeout=2500)
        except Exception:
            pass
        # Intento 1: fill (instantaneo y confiable para campos de formulario).
        try:
            await _click_robusto(page, loc)      # cierra calendarios que tapen
            await loc.fill("")
            await loc.fill(valor)
        except Exception as e:
            log(f"  fallo {etiqueta} en {sel}: {type(e).__name__}")
            continue

        if await _valor_ok(loc, valor):
            log(f"  OK {etiqueta} -> {sel}")
            return True

        # Intento 2: tecleo caracter por caracter (campos que ignoran fill).
        try:
            await _click_robusto(page, loc)
            await page.keyboard.press("Control+A")
            await page.keyboard.press("Backspace")
            await loc.type(valor, delay=45)
        except Exception:
            pass

        if await _valor_ok(loc, valor):
            log(f"  OK {etiqueta} -> {sel} (reintento)")
            return True
        log(f"  AVISO: '{etiqueta}' no quedo escrito en {sel}. Escribelo en pantalla.")
        return False

    log(f"  AVISO: no se ubico '{etiqueta}'. Diligencialo manualmente en pantalla.")
    return False


async def _valor_ok(loc, valor: str) -> bool:
    try:
        got = await loc.input_value(timeout=2000)
    except Exception:
        return False
    return got.strip() == valor.strip()


async def _click_robusto(page: Page, loc) -> None:
    """
    Hace clic en el campo aunque algo lo tape. El caso real: al llenar la fecha
    se abre un CALENDARIO que cubre los campos de abajo (Empresa, NIT), y el
    clic normal falla con TimeoutError. Se cierra el popup con Escape y se
    reintenta; como ultimo recurso se fuerza el clic.
    """
    try:
        await loc.click(timeout=config.TIMEOUT_ACCION_MS)
        return
    except Exception:
        pass
    for _ in range(2):
        try:
            await page.keyboard.press("Escape")
        except Exception:
            pass
        await asyncio.sleep(0.35)
        try:
            await loc.click(timeout=6000)
            return
        except Exception:
            continue
    await loc.click(timeout=6000, force=True)


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


# ------------------------------------------------ tipo de documento ---
# Cada portal escribe el tipo de documento a su manera ("CEDULA DE
# CIUDADANIA", "C.C.", "Cédula de ciudadanía"...). Adivinar por substring
# es peligroso: "cedula de extranjeria" TAMBIEN contiene "cedula", y por eso
# se colaba la opcion equivocada.
#
# Solucion: se leen las opciones REALES del <select> y cada una se evalua con
# patrones a favor y EN CONTRA. Una opcion solo gana si coincide con algo de
# 'si' y no coincide con nada de 'no'. Nada de suponer.
TIPOS_DOC: dict[str, dict[str, list[str]]] = {
    "CC": {
        "si": [r"ciudadan", r"^\s*c\.?\s*c\.?\s*$", r"^cc$"],
        "no": [r"extranjer", r"tarjeta", r"pasaporte", r"\bnit\b", r"comparendo",
               r"expediente", r"exterior"],
    },
    "CE": {
        "si": [r"extranjer", r"^\s*c\.?\s*e\.?\s*$", r"^ce$", r"^cx$"],
        "no": [r"ciudadan", r"tarjeta", r"pasaporte", r"\bnit\b"],
    },
    "TI": {
        "si": [r"tarjeta\s+de\s+identidad", r"^\s*t\.?\s*i\.?\s*$", r"^ti$"],
        "no": [r"\bnit\b"],
    },
    "PA": {
        "si": [r"pasaporte", r"^pa$", r"^ps$"],
        "no": [],
    },
    "NIT": {
        "si": [r"\bnit\b", r"^ni$", r"juridica"],
        "no": [r"ciudadan", r"extranjer", r"tarjeta", r"pasaporte"],
    },
}


def _sin_tildes(t: str) -> str:
    import unicodedata
    t = unicodedata.normalize("NFD", t or "")
    return "".join(c for c in t if unicodedata.category(c) != "Mn").lower().strip()


def escoger_opcion(opciones: list[tuple[str, str]], tipo: str) -> tuple[str, str] | None:
    """
    opciones: [(value, texto), ...] tal como estan en el DOM.
    Devuelve la (value, texto) que corresponde al tipo, o None.
    """
    reglas = TIPOS_DOC.get((tipo or "").upper())
    if not reglas:
        return None
    for value, texto in opciones:
        plano = _sin_tildes(texto)
        if not plano or plano.startswith("seleccione"):
            continue
        if any(re.search(n, plano) for n in reglas["no"]):
            continue          # descarta 'extranjeria' cuando se pidio 'ciudadania'
        if any(re.search(s, plano) for s in reglas["si"]):
            return value, texto.strip()
    return None


async def _leer_opciones(loc, intentos: int = 14, espera: float = 0.8) -> list:
    """
    Espera a que el <select> tenga opciones reales.

    Varios portales (Contraloria entre ellos) llenan la lista por JavaScript
    despues de cargar la pagina. Si se lee de una queda vacia y se pierde la
    seleccion — que fue exactamente lo que pasaba.
    """
    opciones: list = []
    for _ in range(intentos):
        try:
            opciones = await loc.evaluate(
                "s => Array.from(s.options).map(o => [o.value, o.textContent])")
        except Exception:
            opciones = []
        # Con una sola opcion normalmente es el "Seleccione..." de relleno.
        if len(opciones) > 1:
            return opciones
        await asyncio.sleep(espera)
    return opciones


async def elegir_tipo_doc(page: Page, candidatos: Iterable[str], tipo: str,
                          log: Log) -> bool:
    """Selecciona el tipo de documento leyendo las opciones reales del portal."""
    for sel in candidatos:
        try:
            if await page.locator(sel).count() == 0:
                continue
        except Exception:
            continue
        loc = page.locator(sel).first

        opciones = await _leer_opciones(loc)
        if len(opciones) <= 1:
            log(f"  AVISO: la lista de tipo de documento ({sel}) no cargo"
                f" opciones. Seleccionalo en pantalla.")
            continue

        elegida = escoger_opcion([(o[0], o[1]) for o in opciones], tipo)
        if not elegida:
            disponibles = ", ".join(o[1].strip() for o in opciones if o[1].strip())
            log(f"  AVISO: '{tipo}' no existe en este portal. Opciones: {disponibles}")
            return False

        value, texto = elegida
        try:
            await loc.select_option(value=value, timeout=6000)
        except Exception:
            try:
                await loc.select_option(label=texto, timeout=6000)
            except Exception:
                log(f"  AVISO: no se pudo seleccionar '{texto}'. Hazlo en pantalla.")
                return False

        # Verificacion: se confirma contra el DOM que quedo la opcion correcta.
        try:
            quedo = await loc.evaluate(
                "s => s.options[s.selectedIndex] ? s.options[s.selectedIndex].textContent : ''")
        except Exception:
            quedo = texto
        if _sin_tildes(quedo) != _sin_tildes(texto):
            log(f"  AVISO: se pidio '{texto}' pero quedo '{quedo.strip()}'."
                f" Corrigelo en pantalla.")
            return False

        log(f'  OK tipo de documento -> "{texto}" (value={value})')
        return True

    log("  AVISO: no se ubico la lista de tipo de documento."
        " Seleccionalo en pantalla.")
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
        # Se fuerza media 'screen', no 'print': varios portales del Estado
        # tienen CSS de impresion que esconde justo el recuadro del resultado.
        # Asi el PDF sale igual a lo que se ve en pantalla.
        try:
            await objetivo.emulate_media(media="screen")
        except Exception:
            pass
        return await objetivo.pdf(
            format="Letter", print_background=True, prefer_css_page_size=False,
            margin={"top": "10mm", "bottom": "10mm", "left": "8mm", "right": "8mm"},
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
