"""
Procuraduria General de la Nacion - Antecedentes disciplinarios.

Verificado en vivo el 29-jul-2026 sobre la pagina real:
  URL      https://apps.procuraduria.gov.co/webcert/inicio.aspx
  campos   #ddlTipoID  #txtNumID  #txtRespuestaPregunta
  boton    #btnNuevaConsulta / input[type=submit] ("Consultar")
  captcha  pregunta escrita tipo "Cuanto es 3 X 3?" (NO es reCAPTCHA)

IMPORTANTE - por que inicio.aspx y no Certificado.aspx
-----------------------------------------------------
Certificado.aspx exige un token de un solo uso. Si se abre directo responde
"Falla la validacion del token" y la pregunta del captcha NUNCA carga (el
campo queda en blanco y es imposible continuar). inicio.aspx genera el token
y redirige solo a Certificado.aspx?t=<token>&tpo=1. Es la misma ruta que usa
la pagina oficial www.procuraduria.gov.co/Pages/consulta-de-antecedentes.aspx,
que embebe inicio.aspx en un iframe.
"""
from playwright.async_api import Page

from .base import (DatosConsulta, Log, Portal, elegir_tipo_doc, escribir,
                   pulsar, reposar)


class Procuraduria(Portal):
    id = "procuraduria"
    nombre = "Antecedentes disciplinarios"
    entidad = "Procuraduria General de la Nacion"
    url = "https://apps.procuraduria.gov.co/webcert/inicio.aspx"
    admite_nit = True
    nota = "Certificado ordinario de antecedentes disciplinarios (Ley 1952/2019)."

    async def preparar(self, page: Page, datos: DatosConsulta, log: Log) -> None:
        await self.abrir(page, log)

        await elegir_tipo_doc(
            page,
            ["#ddlTipoID", "select[name='ddlTipoID']", "select[id*='TipoID']"],
            datos.tipo_doc, log,
        )

        await escribir(
            page,
            ["#txtNumID", "input[name='txtNumID']", "input[id*='NumID']"],
            datos.numero, log, "numero de documento",
        )

        # Por inicio.aspx el certificado ya llega como ordinario (tpo=1) y no
        # aparece el radio; si alguna version lo muestra, se marca.
        try:
            radio = page.locator("#rblTipoCert_0").first
            if await radio.is_visible(timeout=1500) and not await radio.is_checked():
                await radio.check(timeout=4000, force=True)
                log("  OK tipo de certificado -> Ordinario")
        except Exception:
            pass

        log("La Procuraduria hace una PREGUNTA escrita (ej. 'Cuanto es 3 X 3?').")
        log("Escribe la respuesta en el campo de abajo y pulsa CONTINUAR.")

    async def enviar(self, page: Page, log: Log) -> None:
        await pulsar(
            page,
            ["input[type=submit][value*='onsultar']", "#btnNuevaConsulta",
             "input[name='btnNuevaConsulta']", "input[type=submit]"],
            log, "boton Consultar",
        )
        await reposar(page, 3000)
