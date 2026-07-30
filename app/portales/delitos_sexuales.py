"""
Policia Nacional (DIJIN) - Consulta de inhabilidades por delitos sexuales
cometidos contra menores de edad. Ley 1918 de 2018.

Verificado en vivo el 30-jul-2026:
  URL     https://inhabilidades.policia.gov.co:8080/
  campos  #tipo (CC | CX | PA)  #nuip  #fechaExpNuip (DD/MM/AAAA)
          #nombreEmpresa  #nitEmpresa  #cbCondiciones (checkbox)
  boton   #btnConsultar
  captcha reCAPTCHA Enterprise v2 -> lo resuelve el usuario en pantalla

A diferencia de los demas, este certificado va DIRIGIDO a una entidad: exige
razon social y NIT (con digito de verificacion) de quien consulta. Esos dos
datos salen del formulario de la app y se guardan en el celular para no
volver a digitarlos.
"""
from playwright.async_api import Page

from .base import (DatosConsulta, Log, Portal, elegir, escribir, pulsar,
                   reposar)

# El portal usa CX para cedula de extranjeria, no CE.
TIPO_DOC = {"CC": ["CC"], "CE": ["CX"], "CX": ["CX"], "PA": ["PA"]}
TIPO_TXT = {
    "CC": ["c.?dula de ciudadan"],
    "CE": ["c.?dula de extranjer"],
    "CX": ["c.?dula de extranjer"],
    "PA": ["pasaporte"],
}


class DelitosSexuales(Portal):
    id = "delitos_sexuales"
    nombre = "Inhabilidades por delitos sexuales"
    entidad = "Policia Nacional - DIJIN (Ley 1918/2018)"
    url = "https://inhabilidades.policia.gov.co:8080/"
    admite_nit = False
    nota = ("Exige razon social y NIT (con digito de verificacion) de la "
            "entidad que consulta.")

    async def preparar(self, page: Page, datos: DatosConsulta, log: Log) -> None:
        await self.abrir(page, log)

        tipo = datos.tipo_doc.upper()
        await elegir(
            page,
            ["#tipo", "select[name='tipo']"],
            valores=TIPO_DOC.get(tipo, ["CC"]),
            etiquetas=TIPO_TXT.get(tipo, ["ciudadan"]),
            log=log, etiqueta="tipo de documento",
        )

        await escribir(page, ["#nuip", "input[name='nuip']"],
                       datos.numero, log, "numero de documento")

        if datos.fecha_ddmmyyyy:
            await escribir(page, ["#fechaExpNuip", "input[name='fechaExpNuip']"],
                           datos.fecha_ddmmyyyy, log, "fecha de expedicion")
        else:
            log("  AVISO: este portal EXIGE fecha de expedicion. Escribela en"
                " pantalla (formato DD/MM/AAAA).")

        if datos.entidad:
            await escribir(page, ["#nombreEmpresa", "input[name='nombreEmpresa']"],
                           datos.entidad, log, "entidad consultante")
        else:
            log("  AVISO: falta la entidad consultante. Escribela en pantalla.")

        if datos.nit_entidad:
            await escribir(page, ["#nitEmpresa", "input[name='nitEmpresa']"],
                           datos.nit_entidad, log, "NIT de la entidad")
        else:
            log("  AVISO: falta el NIT de la entidad. Escribelo en pantalla.")

        # Aceptacion de terminos y politica de datos.
        try:
            caja = page.locator("#cbCondiciones").first
            if await caja.is_visible(timeout=3000) and not await caja.is_checked():
                await caja.check(timeout=4000, force=True)
                log("  OK acepto terminos y politica de tratamiento de datos")
        except Exception:
            log("  AVISO: marca la casilla de terminos en pantalla.")

        log("Marca 'No soy un robot' en pantalla y pulsa CONTINUAR.")

    async def enviar(self, page: Page, log: Log) -> None:
        await pulsar(
            page,
            ["#btnConsultar", "button:has-text('CONSULTAR')",
             "button:has-text('Consultar')", "button[type=submit]"],
            log, "boton Consultar",
        )
        await reposar(page, 3500)
