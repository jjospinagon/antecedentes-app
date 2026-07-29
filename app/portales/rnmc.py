"""Policia Nacional - RNMC (Registro Nacional de Medidas Correctivas)."""
from playwright.async_api import Page

from .base import (DatosConsulta, Log, Portal, elegir, escribir,
                   marcar_checkboxes, pulsar, reposar)

TIPO_TXT = {
    "CC": ["c.?dula de ciudadan"],
    "CE": ["c.?dula de extranjer"],
    "TI": ["tarjeta de identidad"],
    "PA": ["pasaporte"],
}


class RNMC(Portal):
    id = "rnmc"
    nombre = "Medidas correctivas (RNMC)"
    entidad = "Policia Nacional - Codigo Nacional de Seguridad y Convivencia"
    url = "https://srvcnpc.policia.gov.co/PSC/frm_cnp_consulta.aspx"
    admite_nit = False
    nota = "Ley 1801 de 2016. Consulta de multas y medidas correctivas."

    async def preparar(self, page: Page, datos: DatosConsulta, log: Log) -> None:
        await self.abrir(page, log)
        await marcar_checkboxes(page, log)

        await elegir(
            page,
            ["#ddlTipoDocumento", "select[id*='TipoDoc']", "select[name*='tipo']",
             "select"],
            valores=["1"] if datos.tipo_doc.upper() == "CC" else [],
            etiquetas=TIPO_TXT.get(datos.tipo_doc.upper(), ["ciudadan"]),
            log=log, etiqueta="tipo de documento",
        )

        await escribir(
            page,
            ["#txtExpediente", "#txtNumeroDocumento", "input[id*='umeroDoc']",
             "input[id*='xpediente']", "input[type=text]:not([id*=aptcha])"],
            datos.numero, log, "numero de documento",
        )

        log("Resuelve el captcha en pantalla y pulsa CONTINUAR.")

    async def enviar(self, page: Page, log: Log) -> None:
        await pulsar(
            page,
            ["#btnConsultar", "input[value*='onsultar']",
             "button:has-text('Consultar')", "input[type=submit]"],
            log, "boton Consultar",
        )
        await reposar(page, 2500)
