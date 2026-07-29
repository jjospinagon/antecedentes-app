"""
Prueba de extremo a extremo del motor, contra un portal simulado local.

Valida: apertura, autodiligenciamiento, pausa humana con streaming de
pantalla, reenvio de clics y teclado, envio del formulario, captura del PDF
y consolidacion final. No toca ningun portal del Estado.

    python3 tests/e2e_demo.py
"""
import asyncio
import base64
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from app import config
from app.portales.base import (DatosConsulta, Log, Portal, elegir, escribir,
                               pulsar, reposar)
from app.sesion import Sesion

DEMO = pathlib.Path(__file__).parent / "portal_demo.html"


class PortalDemo(Portal):
    id = "demo"
    nombre = "Certificado de prueba"
    entidad = "Portal simulado local"
    url = DEMO.as_uri()
    admite_nit = True

    async def preparar(self, page, datos: DatosConsulta, log: Log) -> None:
        await self.abrir(page, log)
        await elegir(page, ["#ddlTipoID"], valores=["1"], etiquetas=["ciudadan"],
                     log=log, etiqueta="tipo de documento")
        await escribir(page, ["#txtNumID"], datos.numero, log, "numero")

    async def enviar(self, page, log: Log) -> None:
        await pulsar(page, ["#btnConsultar"], log, "boton Consultar")
        await reposar(page, 800)


async def main() -> int:
    config.REVISION_MANUAL = True
    datos = DatosConsulta("CC", "1094123456", "2010-05-14", "Juan Jose Ospina")

    s = Sesion(datos, ["demo"])
    s.portales = lambda: [PortalDemo()]          # inyecta el portal simulado

    frames = 0
    fases = []
    fin = {}

    async def consumidor():
        nonlocal frames, fin
        while True:
            m = await s.salida.get()
            if m["t"] == "frame":
                frames += 1
            elif m["t"] == "estado":
                fases.append(m["fase"])
                print(f"  [estado] {m['fase']}: {m.get('msg','')}")
            elif m["t"] == "log":
                print(f"  {m['msg']}")
            elif m["t"] in ("fin", "error"):
                fin = m
                return

    tarea = asyncio.create_task(s.ejecutar())
    cons = asyncio.create_task(consumidor())

    # --- fase captcha: simula al humano tocando el campo y escribiendo ---
    print("\n>> Esperando fase de captcha...")
    for _ in range(120):
        if "captcha" in fases:
            break
        await asyncio.sleep(0.25)
    assert "captcha" in fases, "nunca llego la pausa de captcha"
    await asyncio.sleep(2.0)
    assert frames > 0, "no se recibio ningun frame de pantalla"
    print(f">> Streaming OK ({frames} frames recibidos)")

    # clic sobre el campo del codigo y tecleo remoto
    caja = await s.page.locator("#txtCodigo").bounding_box()
    await s.accion({"t": "click",
                    "x": caja["x"] + caja["width"] / 2,
                    "y": caja["y"] + caja["height"] / 2})
    await s.accion({"t": "texto", "v": "7K4M9"})
    valor = await s.page.locator("#txtCodigo").input_value()
    assert valor == "7K4M9", f"el tecleo remoto fallo: {valor!r}"
    print(">> Clic y teclado remotos OK")

    await s.accion({"t": "continuar"})

    # --- fase revision ---
    for _ in range(80):
        if "revision" in fases:
            break
        await asyncio.sleep(0.25)
    assert "revision" in fases, "nunca llego la fase de revision"
    texto = await s.page.inner_text("body")
    assert "NO REGISTRA ANTECEDENTES" in texto, "el formulario no se envio"
    print(">> Envio del formulario OK")
    await s.accion({"t": "continuar"})

    await asyncio.wait_for(tarea, timeout=90)
    await asyncio.wait_for(cons, timeout=15)

    assert fin.get("t") == "fin", f"termino con error: {fin}"
    assert s.pdf_final and s.pdf_final[:4] == b"%PDF", "PDF final invalido"
    salida = pathlib.Path("/tmp") / s.nombre_pdf
    salida.write_bytes(s.pdf_final)

    print(f"\n>> PDF consolidado: {salida} ({len(s.pdf_final)} bytes)")
    print(f">> Resumen: {fin['resumen']}")
    print(f">> Fases recorridas: {fases}")
    print("\nE2E DEMO OK")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
