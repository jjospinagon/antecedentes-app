"""
Policia Nacional - RNMC (Registro Nacional de Medidas Correctivas).

Verificado en vivo el 29-jul-2026:
  URL     https://srvcnpc.policia.gov.co/PSC/frm_cnp_consulta.aspx
  aviso   modal inicial con boton #ctl00_ContentPlaceHolder3_PopMsg_ok
  campos  #ctl00_ContentPlaceHolder3_ddlTipoDoc
          #ctl00_ContentPlaceHolder3_txtExpediente
  boton   lupa al lado del campo (id volatil) -> se prueban candidatos y,
          si ninguno aparece, se envia con Enter
  El selector incluye NIT, asi que este portal si aplica a persona juridica.
"""
from playwright.async_api import Page

from .base import (DatosConsulta, Log, Portal, elegir, escribir, pulsar,
                   reposar)

PREFIJO = "#ctl00_ContentPlaceHolder3_"

TIPO_TXT = {
    "CC": ["cedula de ciudadania", "c.?dula de ciudadan"],
    "CE": ["c.?dula de extranjer", "cedula de extranjeria"],
    "TI": ["tarjeta de identidad"],
    "PA": ["pasaporte"],
    "NIT": ["nit"],
}

CAMPO_NUM = [PREFIJO + "txtExpediente",
             "input[id*='txtExpediente']",
             "input[id*='ContentPlaceHolder3'][type=text]"]


class RNMC(Portal):
    id = "rnmc"
    nombre = "Medidas correctivas (RNMC)"
    entidad = "Policia Nacional - Codigo Nacional de Seguridad y Convivencia"
    url = "https://srvcnpc.policia.gov.co/PSC/frm_cnp_consulta.aspx"
    admite_nit = True
    nota = "Ley 1801 de 2016. Comparendos y medidas correctivas."

    async def preparar(self, page: Page, datos: DatosConsulta, log: Log) -> None:
        await self.abrir(page, log)

        # Aviso modal de entrada.
        await pulsar(
            page,
            [PREFIJO + "PopMsg_ok", "input[id*='PopMsg_ok']",
             "input[type=submit][value='Ok']"],
            log, "aviso inicial (Ok)",
        )
        await reposar(page, 2000)

        await elegir(
            page,
            [PREFIJO + "ddlTipoDoc", "select[id*='ddlTipoDoc']", "select"],
            valores=[],
            etiquetas=TIPO_TXT.get(datos.tipo_doc.upper(), ["ciudadania"]),
            log=log, etiqueta="tipo de documento",
        )

        await escribir(page, CAMPO_NUM, datos.numero, log, "numero de documento")

        log("Si el portal pide validacion, resuelvela en pantalla. Luego CONTINUAR.")

    async def enviar(self, page: Page, log: Log) -> None:
        ok = await pulsar(
            page,
            [PREFIJO + "btnBuscar", "input[id*='btnBuscar']",
             "input[id*='ContentPlaceHolder3'][type=image]",
             "a[id*='Buscar']", "input[type=submit][value*='uscar']"],
            log, "boton Buscar",
        )
        if not ok:
            # La lupa cambia de id entre versiones: Enter en el campo tambien envia.
            for sel in CAMPO_NUM:
                try:
                    await page.locator(sel).first.press("Enter", timeout=4000)
                    log("  consulta enviada con Enter")
                    break
                except Exception:
                    continue
        await reposar(page, 3000)
