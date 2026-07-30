"""
Policia Nacional - Consulta de antecedentes judiciales (WebJudicial, JSF).

Verificado en vivo el 29-jul-2026. Son DOS pantallas:
  1) index.xhtml        radio input[id='aceptaOption:0'] (Acepto) + #continuarBtn
  2) antecedentes.xhtml #cedulaTipo  #cedulaInput  + boton Consultar (id volatil
                        tipo j_idt17) + reCAPTCHA Enterprise v2

El portal a veces no carga a la primera; por eso se reintenta la apertura.
"""
import asyncio

from playwright.async_api import Page

from .base import (DatosConsulta, Log, Portal, config, elegir_tipo_doc,
                   escribir, pulsar, reposar)


class PoliciaJudicial(Portal):
    id = "policia"
    nombre = "Antecedentes judiciales"
    entidad = "Policia Nacional de Colombia"
    url = "https://antecedentes.policia.gov.co:7005/WebJudicial/index.xhtml"
    admite_nit = False
    nota = "Antecedentes penales y requerimientos judiciales (Decreto 019/2012)."

    async def preparar(self, page: Page, datos: DatosConsulta, log: Log) -> None:
        # --- pantalla 1: terminos de uso ------------------------------------
        cargo = False
        for intento in (1, 2, 3):
            try:
                await page.goto(self.url, timeout=config.TIMEOUT_NAV_MS,
                                wait_until="domcontentloaded")
                await reposar(page, 1500)
                if await page.locator("input[id='aceptaOption:0']").first.is_visible(
                        timeout=6000):
                    cargo = True
                    break
            except Exception:
                pass
            log(f"  el portal no respondio (intento {intento}/3), reintentando...")
            await asyncio.sleep(3)

        if not cargo:
            log("  AVISO: la pantalla de terminos no cargo. Recarga con el boton"
                " Recargar o pulsa Saltar portal.")
            return

        try:
            await page.locator("input[id='aceptaOption:0']").first.check(
                timeout=6000, force=True)
            log("  OK acepto los terminos de uso")
        except Exception:
            log("  AVISO: marca 'Acepto' en pantalla.")

        await reposar(page, 800)
        await pulsar(
            page,
            ["#continuarBtn", "button[id='continuarBtn']",
             "button:has-text('Enviar')"],
            log, "boton Enviar",
        )
        await reposar(page, 2500)

        # --- pantalla 2: datos de la consulta -------------------------------
        await elegir_tipo_doc(
            page,
            ["#cedulaTipo", "select[id='cedulaTipo']", "select[id*='Tipo']"],
            datos.tipo_doc, log,
        )

        await escribir(
            page,
            ["#cedulaInput", "input[id='cedulaInput']", "input[type=text]"],
            datos.numero, log, "numero de documento",
        )

        log("Marca la casilla 'No soy un robot' en pantalla y pulsa CONTINUAR.")

    async def enviar(self, page: Page, log: Log) -> None:
        await pulsar(
            page,
            ["button:has-text('Consultar')", "input[value='Consultar']",
             "button[type=submit]", "input[type=submit]"],
            log, "boton Consultar",
        )
        await reposar(page, 3500)
