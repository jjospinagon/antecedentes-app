"""Procuraduria General de la Nacion - Antecedentes disciplinarios."""
from playwright.async_api import Page

from .base import DatosConsulta, Log, Portal, elegir, escribir, pulsar, reposar

# value del <select> de tipo de documento en el portal (webcert)
TIPO_DOC = {"CC": ["1"], "CE": ["2"], "TI": ["3"], "NIT": ["4"], "PA": ["5"]}
TIPO_TXT = {
    "CC": ["c.?dula de ciudadan"],
    "CE": ["c.?dula de extranjer"],
    "TI": ["tarjeta de identidad"],
    "NIT": ["nit"],
    "PA": ["pasaporte"],
}


class Procuraduria(Portal):
    id = "procuraduria"
    nombre = "Antecedentes disciplinarios"
    entidad = "Procuraduria General de la Nacion"
    url = "https://apps.procuraduria.gov.co/webcert/"
    admite_nit = True
    nota = "Certificado de Antecedentes Disciplinarios (Ley 1238/2008)."

    async def preparar(self, page: Page, datos: DatosConsulta, log: Log) -> None:
        await self.abrir(page, log)

        await elegir(
            page,
            ["#ddlTipoID", "select[name*='TipoID']", "select[id*='ipoDoc']",
             "select[name*='tipoDocumento']", "select"],
            valores=TIPO_DOC.get(datos.tipo_doc.upper(), ["1"]),
            etiquetas=TIPO_TXT.get(datos.tipo_doc.upper(), ["ciudadan"]),
            log=log, etiqueta="tipo de documento",
        )

        await escribir(
            page,
            ["#txtNumID", "input[name*='NumID']", "input[id*='umeroDoc']",
             "input[name*='numeroDocumento']", "input[type=text]:not([id*=aptcha])"],
            datos.numero, log, "numero de documento",
        )

        # Algunas versiones piden correo para enviar copia del certificado.
        await escribir(page, ["#txtEmail", "input[type=email]"],
                       "", log, "correo (opcional)")

        log("Resuelve el captcha en pantalla y pulsa CONTINUAR.")

    async def enviar(self, page: Page, log: Log) -> None:
        await pulsar(
            page,
            ["#btnConsultar", "input[type=submit][value*='onsult']",
             "button:has-text('Consultar')", "a:has-text('Consultar')",
             "input[type=submit]"],
            log, "boton Consultar",
        )
        await reposar(page, 2500)
