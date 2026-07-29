"""Policia Nacional - Consulta de antecedentes judiciales (WebJudicial, JSF)."""
from playwright.async_api import Page

from .base import (DatosConsulta, Log, Portal, escribir, marcar_checkboxes,
                   pulsar, reposar)


class PoliciaJudicial(Portal):
    id = "policia"
    nombre = "Antecedentes judiciales"
    entidad = "Policia Nacional de Colombia"
    url = "https://antecedentes.policia.gov.co:7005/WebJudicial/index.xhtml"
    admite_nit = False
    nota = "Consulta de antecedentes penales y requerimientos judiciales."

    async def preparar(self, page: Page, datos: DatosConsulta, log: Log) -> None:
        await self.abrir(page, log)

        # Paso 1: pantalla de terminos y condiciones.
        await marcar_checkboxes(page, log)
        if await pulsar(
            page,
            ["button:has-text('Enviar')", "input[value='Enviar']",
             "button:has-text('Aceptar')", "a:has-text('Continuar')",
             "span:has-text('Enviar')"],
            log, "aceptar terminos",
        ):
            await reposar(page, 2000)

        # Paso 2: formulario de consulta.
        await escribir(
            page,
            ["#continuar\\:nseccion", "input[id*='nseccion']",
             "input[id*='cedula']", "input[id*='Cedula']",
             "input[id*='documento']", "input[type=text]:not([id*=aptcha])"],
            datos.numero, log, "numero de cedula",
        )

        if datos.fecha_ddmmyyyy:
            await escribir(
                page,
                ["input[id*='fecha']", "input[type=date]", "input[id*='Fecha']"],
                datos.fecha_ddmmyyyy, log, "fecha de expedicion",
            )

        log("Resuelve el captcha en pantalla y pulsa CONTINUAR.")

    async def enviar(self, page: Page, log: Log) -> None:
        await pulsar(
            page,
            ["button:has-text('Consultar')", "input[value='Consultar']",
             "span:has-text('Consultar')", "button[type=submit]",
             "input[type=submit]"],
            log, "boton Consultar",
        )
        await reposar(page, 3000)

        # El resultado se imprime desde la propia pagina.
        await pulsar(page, ["a:has-text('Imprimir')", "button:has-text('Imprimir')"],
                     log, "boton Imprimir")
        await reposar(page, 1500)
