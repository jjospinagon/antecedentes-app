"""
Procuraduria General de la Nacion - Antecedentes disciplinarios.

Verificado en vivo el 29-jul-2026 sobre la pagina real:
  URL      https://apps.procuraduria.gov.co/webcert/Certificado.aspx
  campos   #ddlTipoID  #txtNumID  #rblTipoCert_0  #txtRespuestaPregunta  #txtEmail
  boton    #btnNuevaConsulta
  captcha  pregunta en imagen + respuesta escrita (NO es reCAPTCHA)
"""
from playwright.async_api import Page

from .base import (DatosConsulta, Log, Portal, elegir, escribir, pulsar,
                   reposar)

# Valores reales del <select> (leidos del DOM, no supuestos).
TIPO_DOC = {
    "CC": ["1"], "NIT": ["2"], "CE": ["5"], "PEP": ["0"], "PPT": ["10"],
}
TIPO_TXT = {
    "CC": ["c.?dula de ciudadan"],
    "NIT": ["^nit$", "nit"],
    "CE": ["c.?dula extranjer", "c.?dula de extranjer"],
    "PEP": ["^pep$"],
    "PPT": ["^ppt$"],
}


class Procuraduria(Portal):
    id = "procuraduria"
    nombre = "Antecedentes disciplinarios"
    entidad = "Procuraduria General de la Nacion"
    url = "https://apps.procuraduria.gov.co/webcert/Certificado.aspx"
    admite_nit = True
    nota = "Certificado ordinario de antecedentes disciplinarios (Ley 1952/2019)."

    async def preparar(self, page: Page, datos: DatosConsulta, log: Log) -> None:
        await self.abrir(page, log)

        tipo = datos.tipo_doc.upper()
        await elegir(
            page,
            ["#ddlTipoID", "select[name='ddlTipoID']", "select[id*='TipoID']"],
            valores=TIPO_DOC.get(tipo, ["1"]),
            etiquetas=TIPO_TXT.get(tipo, ["ciudadan"]),
            log=log, etiqueta="tipo de documento",
        )

        await escribir(
            page,
            ["#txtNumID", "input[name='txtNumID']", "input[id*='NumID']"],
            datos.numero, log, "numero de documento",
        )

        # Certificado ordinario (el especial exige elegir cargo al que se aspira).
        try:
            radio = page.locator("#rblTipoCert_0").first
            if await radio.is_visible(timeout=2000) and not await radio.is_checked():
                await radio.check(timeout=4000, force=True)
                log("  OK tipo de certificado -> Ordinario")
        except Exception:
            log("  AVISO: no se pudo marcar 'Ordinario'; marcalo en pantalla si hace falta.")

        log("La Procuraduria muestra una PREGUNTA en imagen: escribe la respuesta")
        log("en el campo de abajo y pulsa CONTINUAR.")

    async def enviar(self, page: Page, log: Log) -> None:
        await pulsar(
            page,
            ["#btnNuevaConsulta", "input[name='btnNuevaConsulta']",
             "input[type=submit]"],
            log, "boton Consultar",
        )
        await reposar(page, 3000)
