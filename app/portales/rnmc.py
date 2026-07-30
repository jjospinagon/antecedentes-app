"""
Policia Nacional - RNMC (Registro Nacional de Medidas Correctivas).

Verificado en vivo el 30-jul-2026, con el formulario ya desplegado:
  URL     https://srvcnpc.policia.gov.co/PSC/frm_cnp_consulta.aspx
  aviso   modal inicial -> #ctl00_ContentPlaceHolder3_PopMsg_ok
  tipo    #ctl00_ContentPlaceHolder3_ddlTipoDoc  (dispara postback)
  numero  #ctl00_ContentPlaceHolder3_txtExpediente
  fecha   #txtFechaexp   <- SOLO aparece despues de elegir el tipo de documento
  enviar  #ctl00_ContentPlaceHolder3_btnConsultar2  (es un <a>, la lupa)

Lo que fallaba antes: se buscaba un <input type=submit> que no existe, asi que
la consulta nunca se enviaba y el PDF capturado era el formulario en blanco.
"""
from playwright.async_api import Page

from .base import (DatosConsulta, Log, Portal, elegir_tipo_doc, escribir,
                   pulsar, reposar)

P = "#ctl00_ContentPlaceHolder3_"

CAMPO_NUM = [P + "txtExpediente", "input[id*='txtExpediente']"]
CAMPO_FECHA = ["#txtFechaexp", "input[id*='Fechaexp']", "input[id*='fechaExp']"]
BOTON = [P + "btnConsultar2", "a[id*='btnConsultar']", "a[id*='Consultar']"]


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
            [P + "PopMsg_ok", "input[id*='PopMsg_ok']",
             P + "btn_salir_modal", "input[type=submit][value='Ok']"],
            log, "aviso inicial (Ok)",
        )
        await reposar(page, 2000)

        # Elegir el tipo dispara un postback que despliega la fecha.
        await elegir_tipo_doc(
            page,
            [P + "ddlTipoDoc", "select[id*='ddlTipoDoc']", "select"],
            datos.tipo_doc, log,
        )
        await reposar(page, 2000)

        await escribir(page, CAMPO_NUM, datos.numero, log, "numero de documento")

        if datos.fecha_ddmmyyyy:
            await escribir(page, CAMPO_FECHA, datos.fecha_ddmmyyyy, log,
                           "fecha de expedicion")
        else:
            log("  AVISO: el RNMC exige fecha de expedicion (DD/MM/AAAA)."
                " Escribela en pantalla.")

        log("Revisa que los tres campos esten completos y pulsa CONTINUAR.")

    async def enviar(self, page: Page, log: Log) -> None:
        ok = await pulsar(page, BOTON, log, "boton Consultar (lupa)")
        if not ok:
            for sel in CAMPO_FECHA + CAMPO_NUM:
                try:
                    await page.locator(sel).first.press("Enter", timeout=4000)
                    log("  consulta enviada con Enter")
                    ok = True
                    break
                except Exception:
                    continue
        if not ok:
            log("  AVISO: no se pudo enviar. Toca la lupa en pantalla y luego"
                " CONTINUAR.")
        await reposar(page, 3500)
