"""
Portal simulado local. Se activa con PORTAL_DEMO=1 y sirve para probar la
app completa (streaming, captcha manual, captura de PDF) sin consultar
ningun portal del Estado. El codigo del captcha es 7K4M9.
"""
import pathlib

from .base import (DatosConsulta, Log, Portal, elegir_tipo_doc, escribir,
                   pulsar, reposar)

HTML = pathlib.Path(__file__).resolve().parents[2] / "tests" / "portal_demo.html"


class Demo(Portal):
    id = "demo"
    nombre = "Certificado de prueba (simulado)"
    entidad = "Portal local de pruebas"
    url = HTML.as_uri()
    admite_nit = True
    nota = "Solo para verificar que la app funciona. Captcha de prueba: 7K4M9."

    async def preparar(self, page, datos: DatosConsulta, log: Log) -> None:
        await self.abrir(page, log)
        await elegir_tipo_doc(page, ["#ddlTipoID"], datos.tipo_doc, log)
        await escribir(page, ["#txtNumID"], datos.numero, log, "numero")
        log("Captcha de prueba: escribe 7K4M9 y pulsa CONTINUAR.")

    async def enviar(self, page, log: Log) -> None:
        await pulsar(page, ["#btnConsultar"], log, "boton Consultar")
        await reposar(page, 800)
