"""Contraloria General de la Republica - Certificado de antecedentes fiscales."""
from playwright.async_api import Page

from .base import DatosConsulta, Log, Portal, elegir, escribir, pulsar, reposar

TIPO_TXT = {
    "CC": ["c.?dula de ciudadan", "^cc$"],
    "CE": ["c.?dula de extranjer", "^ce$"],
    "TI": ["tarjeta de identidad"],
    "NIT": ["nit"],
    "PA": ["pasaporte"],
}


class Contraloria(Portal):
    id = "contraloria"
    nombre = "Antecedentes fiscales"
    entidad = "Contraloria General de la Republica"
    url = "https://apps.contraloria.gov.co/BDME/generarCertificado.php"
    admite_nit = True
    nota = "Boletin de Responsables Fiscales (Art. 60 Ley 610/2000)."

    async def preparar(self, page: Page, datos: DatosConsulta, log: Log) -> None:
        await self.abrir(page, log)

        await elegir(
            page,
            ["select[name*='tipo']", "#tipo_id", "#TipoID", "#cmbTipoID", "select"],
            valores=["1", "CC"] if datos.tipo_doc.upper() == "CC" else [datos.tipo_doc.upper()],
            etiquetas=TIPO_TXT.get(datos.tipo_doc.upper(), ["ciudadan"]),
            log=log, etiqueta="tipo de documento",
        )

        await escribir(
            page,
            ["#num_id", "#NumID", "input[name*='cedula']", "input[name*='num']",
             "input[name*='identificacion']", "input[type=text]:not([name*=cap])"],
            datos.numero, log, "numero de documento",
        )

        log("Resuelve el captcha en pantalla y pulsa CONTINUAR.")

    async def enviar(self, page: Page, log: Log) -> None:
        await pulsar(
            page,
            ["input[type=submit][value*='ertific']", "button:has-text('Generar')",
             "input[value*='Consultar']", "button:has-text('Consultar')",
             "input[type=submit]", "button[type=submit]"],
            log, "boton Generar certificado",
        )
        await reposar(page, 2500)
