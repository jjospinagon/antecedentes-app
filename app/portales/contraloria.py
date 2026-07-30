"""
Contraloria General de la Republica - Certificado de antecedentes fiscales.

Verificado en vivo el 29-jul-2026. OJO: el dominio viejo
apps.contraloria.gov.co YA NO EXISTE (NXDOMAIN). El vigente es cfiscal:
  natural   https://cfiscal.contraloria.gov.co/certificados/certificadopersonanatural.aspx
  juridica  https://cfiscal.contraloria.gov.co/certificados/certificadopersonajuridica.aspx
  campos    #ddlTipoDocumento  #txtNumeroDocumento
  boton     #btnBuscar
  captcha   reCAPTCHA v2 "No soy un robot" -> lo resuelve el usuario en pantalla
"""
from playwright.async_api import Page

from .base import (DatosConsulta, Log, Portal, config, elegir, escribir,
                   pulsar, reposar)

BASE = "https://cfiscal.contraloria.gov.co/certificados/"
URL_NATURAL = BASE + "certificadopersonanatural.aspx"
URL_JURIDICA = BASE + "certificadopersonajuridica.aspx"

TIPO_TXT = {
    "CC": ["c.?dula de ciudadan", "^cc$"],
    "CE": ["c.?dula de extranjer", "^ce$"],
    "TI": ["tarjeta de identidad"],
    "PA": ["pasaporte"],
    "NIT": ["^nit$", "nit"],
}


class Contraloria(Portal):
    id = "contraloria"
    nombre = "Antecedentes fiscales"
    entidad = "Contraloria General de la Republica"
    url = URL_NATURAL
    admite_nit = True
    nota = "Boletin de Responsables Fiscales (Art. 60 Ley 610/2000)."

    async def preparar(self, page: Page, datos: DatosConsulta, log: Log) -> None:
        # La Contraloria separa persona natural de persona juridica.
        destino = URL_JURIDICA if datos.es_nit else URL_NATURAL
        log(f"Abriendo {destino}")
        await page.goto(destino, timeout=config.TIMEOUT_NAV_MS,
                        wait_until="domcontentloaded")
        await reposar(page, 1200)

        await elegir(
            page,
            ["#ddlTipoDocumento", "select[name='ddlTipoDocumento']",
             "select[id*='TipoDocumento']"],
            valores=[],
            etiquetas=TIPO_TXT.get(datos.tipo_doc.upper(), ["ciudadan"]),
            log=log, etiqueta="tipo de documento",
        )

        await escribir(
            page,
            ["#txtNumeroDocumento", "input[name='txtNumeroDocumento']",
             "input[id*='NumeroDocumento']"],
            datos.numero, log, "numero de documento",
        )

        log("Marca la casilla 'No soy un robot' en pantalla y pulsa CONTINUAR.")

    async def enviar(self, page: Page, log: Log) -> None:
        await pulsar(
            page,
            ["#btnBuscar", "input[name='btnBuscar']",
             "input[type=submit][value*='uscar']", "input[type=submit]"],
            log, "boton Buscar",
        )
        await reposar(page, 3000)
