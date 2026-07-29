"""
Prueba del servidor completo (HTTP + WebSocket + PWA) contra el portal
simulado. Levanta uvicorn, crea la sesion, recibe frames, resuelve el
"captcha" por WebSocket y descarga el PDF consolidado.

    PORTAL_DEMO=1 python3 tests/e2e_ws.py
"""
import asyncio
import base64
import json
import os
import pathlib
import sys
import urllib.request

os.environ["PORTAL_DEMO"] = "1"
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import uvicorn
import websockets

PUERTO = 8099
BASE = f"http://127.0.0.1:{PUERTO}"


def _post(ruta: str, cuerpo: dict) -> dict:
    req = urllib.request.Request(
        BASE + ruta, data=json.dumps(cuerpo).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read())


def _get(ruta: str) -> tuple[int, bytes, str]:
    with urllib.request.urlopen(BASE + ruta, timeout=30) as r:
        return r.status, r.read(), r.headers.get("Content-Disposition", "")


# El servidor vive en este mismo event loop: toda peticion bloqueante debe
# salir a un hilo aparte o se auto-bloquea.
async def post(ruta: str, cuerpo: dict) -> dict:
    return await asyncio.to_thread(_post, ruta, cuerpo)


async def get(ruta: str) -> tuple[int, bytes, str]:
    return await asyncio.to_thread(_get, ruta)


async def main() -> int:
    from app.main import app
    cfg = uvicorn.Config(app, host="127.0.0.1", port=PUERTO, log_level="error")
    servidor = uvicorn.Server(cfg)
    tarea_srv = asyncio.create_task(servidor.serve())
    while not servidor.started:
        await asyncio.sleep(0.2)
    print(">> Servidor arriba")

    ses = await post("/api/sesion", {"tipo_doc": "CC", "numero": "1094123456",
                                     "fecha_expedicion": "2010-05-14",
                                     "nombre": "Juan Jose Ospina",
                                     "portales": ["demo"]})
    sid = ses["sid"]
    print(f">> Sesion {sid} | portales: {[p['id'] for p in ses['portales']]}")

    frames = 0
    fases = []
    fin = None

    async with websockets.connect(f"ws://127.0.0.1:{PUERTO}/ws/{sid}",
                                  max_size=12 * 1024 * 1024) as sock:
        while True:
            m = json.loads(await asyncio.wait_for(sock.recv(), timeout=90))
            t = m["t"]

            if t == "frame":
                frames += 1
                assert base64.b64decode(m["img"])[:2] == b"\xff\xd8", "frame no es JPEG"

            elif t == "log":
                print("   " + m["msg"])

            elif t == "estado":
                fases.append(m["fase"])
                print(f"  [{m['fase']}] {m.get('msg','')}")

                if m["fase"] == "captcha":
                    await asyncio.sleep(2.2)               # deja llegar frames
                    # coordenadas reales del campo, como si el dedo lo tocara
                    from app.sesion import SESIONES
                    caja = await SESIONES[sid].page.locator("#txtCodigo").bounding_box()
                    await sock.send(json.dumps(
                        {"t": "click", "x": caja["x"] + caja["width"] / 2,
                         "y": caja["y"] + caja["height"] / 2}))
                    await asyncio.sleep(0.5)
                    await sock.send(json.dumps({"t": "texto", "v": "7K4M9"}))
                    await asyncio.sleep(1.0)
                    valor = await SESIONES[sid].page.locator("#txtCodigo").input_value()
                    assert valor == "7K4M9", f"tecleo remoto fallido: {valor!r}"
                    print("  >> clic + teclado remotos OK")
                    await sock.send(json.dumps({"t": "continuar"}))

                elif m["fase"] == "revision":
                    await asyncio.sleep(1.2)
                    from app.sesion import SESIONES
                    cuerpo = await SESIONES[sid].page.inner_text("body")
                    assert "NO REGISTRA ANTECEDENTES" in cuerpo, \
                        "el formulario no se envio correctamente"
                    print("  >> resultado del portal OK")
                    await sock.send(json.dumps({"t": "continuar"}))

            elif t == "fin":
                fin = m
                break

            elif t == "error":
                raise AssertionError("error del motor: " + m["msg"])

    assert frames >= 2, f"streaming insuficiente ({frames} frames)"
    assert fin["resumen"][0]["ok"], f"el portal fallo: {fin['resumen']}"

    _, datos, disp = await get(fin["url"])
    assert datos[:4] == b"%PDF", "la descarga no es un PDF"

    ruta = pathlib.Path("/tmp") / fin["archivo"]
    ruta.write_bytes(datos)

    for u in ("/", "/app/app.js", "/app/styles.css", "/app/icono.svg",
              "/manifest.webmanifest", "/sw.js"):
        estado, _, _ = await get(u)
        assert estado == 200, u
    print(">> Estaticos de la PWA OK")

    print(f">> Frames: {frames} | Fases: {fases}")
    print(f">> PDF descargado: {ruta} ({len(datos)} bytes) | {disp}")
    print("\nE2E WS OK")

    servidor.should_exit = True
    await tarea_srv
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
