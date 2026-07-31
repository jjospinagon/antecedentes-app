"""
Motor de sesion: un navegador remoto por consulta, con pausa humana para
el captcha y streaming de pantalla hacia el celular.

Flujo por portal
----------------
 1. abrir + diligenciar campos            (automatico)
 2. PAUSA: el usuario resuelve el captcha (manual, desde el celular)
 3. enviar formulario                     (automatico)
 4. PAUSA de revision del resultado       (manual, opcional)
 5. capturar PDF y pasar al siguiente     (automatico)
"""
from __future__ import annotations

import asyncio
import base64
import time
import traceback
import uuid
from typing import Any

from playwright.async_api import Browser, Page, async_playwright

from . import config, pdf as pdfmod
from .portales import CATALOGO, POR_ID, CazadorPDF, DatosConsulta, Resultado
from .portales.base import FIX_CAPTCHA_JS

ARGS_CHROMIUM = [
    "--no-sandbox",
    "--disable-dev-shm-usage",
    "--disable-gpu",
    "--ignore-certificate-errors",
    "--disable-blink-features=AutomationControlled",
    "--window-size=1280,1000",
    "--lang=es-CO",
]
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")


class Sesion:
    def __init__(self, datos: DatosConsulta, portales: list[str]):
        self.sid = uuid.uuid4().hex[:12]
        self.datos = datos
        self.ids_portales = portales
        self.creada = time.time()

        self.salida: asyncio.Queue[dict] = asyncio.Queue(maxsize=64)
        self.continuar = asyncio.Event()
        self.saltar = asyncio.Event()
        self.cancelada = False

        self.lock = asyncio.Lock()
        self.page: Page | None = None
        self.streaming = False

        self.resultados: list[Resultado] = []
        self.pdf_final: bytes | None = None
        self.nombre_pdf: str = ""
        self.estado = "creada"
        self.tarea: asyncio.Task | None = None

    # ------------------------------------------------------------ salida --
    def emitir(self, msg: dict[str, Any]) -> None:
        try:
            self.salida.put_nowait(msg)
        except asyncio.QueueFull:
            try:
                self.salida.get_nowait()
                self.salida.put_nowait(msg)
            except Exception:
                pass

    def log(self, texto: str) -> None:
        self.emitir({"t": "log", "msg": texto})

    # -------------------------------------------------------- streaming ---
    async def _bucle_frames(self) -> None:
        intervalo = 1.0 / max(config.FPS_STREAM, 0.3)
        while self.streaming and not self.cancelada:
            page = self.page
            if page and not page.is_closed():
                try:
                    async with self.lock:
                        img = await page.screenshot(
                            type="jpeg", quality=config.JPEG_QUALITY, timeout=8000)
                    self.emitir({
                        "t": "frame",
                        "img": base64.b64encode(img).decode(),
                        "vw": config.VIEWPORT["width"],
                        "vh": config.VIEWPORT["height"],
                    })
                except Exception:
                    pass
            await asyncio.sleep(intervalo)

    async def _pausa_humana(self, fase: str, portal, indice: int, total: int,
                            mensaje: str) -> bool:
        """Devuelve True si el usuario decidio continuar, False si saltar."""
        self.continuar.clear()
        self.saltar.clear()
        self.emitir({
            "t": "estado", "fase": fase, "portal": portal.id,
            "nombre": portal.nombre, "entidad": portal.entidad,
            "idx": indice, "total": total, "msg": mensaje,
        })
        self.streaming = True
        tarea = asyncio.create_task(self._bucle_frames())
        try:
            esperar_cont = asyncio.create_task(self.continuar.wait())
            esperar_salt = asyncio.create_task(self.saltar.wait())
            hechos, pend = await asyncio.wait(
                {esperar_cont, esperar_salt},
                timeout=config.ESPERA_MAX_HUMANO_S,
                return_when=asyncio.FIRST_COMPLETED,
            )
            for t in pend:
                t.cancel()
            if not hechos:
                self.log("Tiempo de espera agotado en este portal.")
                return False
            return self.continuar.is_set()
        finally:
            self.streaming = False
            tarea.cancel()

    # ------------------------------------------------------ interaccion ---
    async def accion(self, msg: dict) -> None:
        """Aplica en el navegador remoto lo que el usuario toca en el celular."""
        t = msg.get("t")
        if t == "continuar":
            self.continuar.set()
            return
        if t == "saltar":
            self.saltar.set()
            return
        if t == "cancelar":
            self.cancelada = True
            self.saltar.set()
            self.continuar.set()
            return

        page = self.page
        if not page or page.is_closed():
            return
        try:
            async with self.lock:
                if t == "click":
                    await page.mouse.click(float(msg["x"]), float(msg["y"]))
                elif t == "texto":
                    await page.keyboard.type(str(msg.get("v", "")), delay=25)
                elif t == "reemplazar":
                    # El campo enfocado se vacia por completo y se reescribe con
                    # el texto que hay en el celular. Asi el espejo nunca se
                    # desincroniza: borrar o corregir un captcha siempre funciona
                    # y no arrastra la respuesta anterior.
                    await page.keyboard.press("Control+A")
                    await page.keyboard.press("Backspace")
                    v = str(msg.get("v", ""))
                    if v:
                        await page.keyboard.type(v, delay=15)
                elif t == "tecla":
                    await page.keyboard.press(str(msg.get("k", "Enter")))
                elif t == "scroll":
                    await page.mouse.wheel(0, float(msg.get("dy", 300)))
                elif t == "recargar":
                    await page.reload(timeout=config.TIMEOUT_NAV_MS)
        except Exception as e:
            self.log(f"Accion no aplicada: {type(e).__name__}")

    # ------------------------------------------------------- orquestador --
    def portales(self) -> list:
        # Sin 'or CATALOGO': si no se pidio ninguno, la lista queda vacia
        # (el usuario solo eligio certificados manuales tipo REDAM).
        elegidos = [POR_ID[i] for i in self.ids_portales if i in POR_ID]
        return [p for p in elegidos if p.aplica(self.datos)]

    def _resumen(self) -> list[dict]:
        return [{"portal": r.portal_nombre, "id": r.portal_id,
                 "ok": r.ok, "detalle": r.detalle} for r in self.resultados]

    def _rehacer_pdf(self) -> None:
        self.pdf_final = pdfmod.consolidar(self.datos, self.resultados)
        self.nombre_pdf = pdfmod.nombre_archivo(self.datos)

    def _emitir_fin(self) -> None:
        self.estado = "listo"
        self.emitir({"t": "fin", "archivo": self.nombre_pdf,
                     "url": f"/api/pdf/{self.sid}", "resumen": self._resumen()})

    def agregar_adjunto(self, etiqueta: str, pdf_bytes: bytes) -> dict:
        """Suma un PDF que el usuario descargo aparte (REDAM u otro) y rehace
        el consolidado. Devuelve el resumen actualizado."""
        self.resultados.append(Resultado(
            "adjunto", etiqueta or "Certificado adjuntado", True,
            pdf=pdf_bytes, detalle="Adjuntado por el usuario"))
        self._rehacer_pdf()
        return {"archivo": self.nombre_pdf, "url": f"/api/pdf/{self.sid}",
                "resumen": self._resumen()}

    async def ejecutar(self) -> None:
        self.estado = "corriendo"
        lista = self.portales()
        total = len(lista)

        # Solo certificados manuales (o ninguno automatico): se arma el PDF con
        # la caratula y se pasa directo a la pantalla de adjuntar.
        if total == 0:
            self._rehacer_pdf()
            self._emitir_fin()
            return

        OPC_CTX = dict(
            viewport=config.VIEWPORT,
            device_scale_factor=config.DEVICE_SCALE,
            user_agent=UA,
            locale="es-CO",
            timezone_id="America/Bogota",
            accept_downloads=True,
            ignore_https_errors=True,
        )

        navegador: Browser | None = None
        persistente = None
        try:
            async with async_playwright() as pw:
                if config.PERFIL_DIR:
                    # Un solo perfil persistente compartido por todos los portales:
                    # conserva cookies y reputacion entre consultas.
                    persistente = await pw.chromium.launch_persistent_context(
                        config.PERFIL_DIR, headless=config.HEADLESS,
                        args=ARGS_CHROMIUM, **OPC_CTX)
                    self.log("Navegador con perfil persistente"
                             + ("" if config.HEADLESS else " (con pantalla real)"))
                    for i, portal in enumerate(lista, start=1):
                        if self.cancelada:
                            break
                        await self._un_portal(persistente, False, portal, i, total)
                    await persistente.close()
                    persistente = None
                else:
                    navegador = await pw.chromium.launch(
                        headless=config.HEADLESS, args=ARGS_CHROMIUM)
                    self.log("Navegador listo"
                             + ("" if config.HEADLESS else " (con pantalla real)"))
                    for i, portal in enumerate(lista, start=1):
                        if self.cancelada:
                            break
                        ctx = await navegador.new_context(**OPC_CTX)
                        await self._un_portal(ctx, True, portal, i, total)
                    await navegador.close()

            self._rehacer_pdf()
            self._emitir_fin()
        except Exception as e:
            self.estado = "error"
            self.emitir({"t": "error", "msg": f"{type(e).__name__}: {e}"})
            self.log(traceback.format_exc()[-800:])
            for cerr in (persistente, navegador):
                if cerr:
                    try:
                        await cerr.close()
                    except Exception:
                        pass

    async def _un_portal(self, ctx, propia: bool, portal, idx: int, total: int) -> None:
        """`ctx` ya viene creado. `propia` indica si este contexto es exclusivo
        de este portal (se cierra al terminar) o es el perfil persistente
        compartido (solo se cierra la pagina)."""
        bitacora: list[str] = []

        def log(txt: str) -> None:
            bitacora.append(txt)
            self.log(txt)

        page = await ctx.new_page()
        page.set_default_timeout(config.TIMEOUT_ACCION_MS)
        # Fija el reto de reCAPTCHA dentro de la vista en cada pagina que cargue.
        try:
            await page.add_init_script(FIX_CAPTCHA_JS)
        except Exception:
            pass
        self.page = page
        cazador = CazadorPDF(ctx, log)
        cazador.enganchar(page)

        try:
            self.emitir({"t": "estado", "fase": "preparando", "portal": portal.id,
                         "nombre": portal.nombre, "entidad": portal.entidad,
                         "idx": idx, "total": total,
                         "msg": f"Abriendo {portal.entidad}..."})
            log(f"[{idx}/{total}] {portal.entidad} - {portal.nombre}")

            await portal.preparar(page, self.datos, log)

            sigue = await self._pausa_humana(
                "captcha", portal, idx, total,
                "Resuelve el captcha en la pantalla y pulsa CONTINUAR")
            if not sigue or self.cancelada:
                self.resultados.append(Resultado(
                    portal.id, portal.nombre, False,
                    detalle="Omitido por el usuario o tiempo agotado",
                    bitacora=bitacora))
                return

            self.emitir({"t": "estado", "fase": "enviando", "portal": portal.id,
                         "nombre": portal.nombre, "entidad": portal.entidad,
                         "idx": idx, "total": total, "msg": "Enviando consulta..."})
            await portal.enviar(page, log)

            if config.REVISION_MANUAL:
                sigue = await self._pausa_humana(
                    "revision", portal, idx, total,
                    "Verifica el resultado. Pulsa CONTINUAR para guardarlo en el PDF")
                if not sigue or self.cancelada:
                    self.resultados.append(Resultado(
                        portal.id, portal.nombre, False,
                        detalle="Resultado descartado por el usuario",
                        bitacora=bitacora))
                    return

            self.emitir({"t": "estado", "fase": "capturando", "portal": portal.id,
                         "nombre": portal.nombre, "entidad": portal.entidad,
                         "idx": idx, "total": total, "msg": "Generando PDF..."})
            datos_pdf = await cazador.resolver(page)
            ok = bool(datos_pdf) and datos_pdf[:4] == b"%PDF"
            self.resultados.append(Resultado(
                portal.id, portal.nombre, ok, pdf=datos_pdf if ok else None,
                detalle="Certificado capturado" if ok else "No se obtuvo un PDF valido",
                bitacora=bitacora))
            log("  Listo." if ok else "  No se obtuvo PDF.")

        except Exception as e:
            self.resultados.append(Resultado(
                portal.id, portal.nombre, False,
                detalle=f"{type(e).__name__}: {str(e)[:160]}", bitacora=bitacora))
            self.log(f"  ERROR en {portal.nombre}: {type(e).__name__}")
        finally:
            self.streaming = False
            try:
                if propia:
                    await ctx.close()          # contexto exclusivo del portal
                else:
                    await page.close()         # perfil persistente: solo la pagina
            except Exception:
                pass
            self.page = None


# --------------------------------------------------------------- registro --
SESIONES: dict[str, Sesion] = {}


def limpiar_expiradas() -> None:
    ahora = time.time()
    for sid in [s for s, v in SESIONES.items()
                if ahora - v.creada > config.TTL_SESION_S]:
        SESIONES.pop(sid, None)
