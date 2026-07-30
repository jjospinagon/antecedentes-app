"""API + servidor estatico de la PWA."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

from fastapi import (FastAPI, File, Form, HTTPException, UploadFile, WebSocket,
                     WebSocketDisconnect)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import config
from .portales import CATALOGO
from .sesion import SESIONES, Sesion, limpiar_expiradas
from .portales.base import DatosConsulta

RAIZ = Path(__file__).resolve().parent.parent
WEB = RAIZ / "web"

app = FastAPI(title="Certificados de Antecedentes", version="1.0.0")
app.add_middleware(
    CORSMiddleware, allow_origins=config.ORIGENES_CORS,
    allow_methods=["*"], allow_headers=["*"],
)


class SolicitudConsulta(BaseModel):
    tipo_doc: str = Field(default="CC")
    numero: str
    fecha_expedicion: str | None = None
    nombre: str | None = None
    entidad: str | None = None
    nit_entidad: str | None = None
    portales: list[str] = Field(default_factory=list)


@app.get("/api/salud")
async def salud():
    return {"ok": True, "sesiones": len(SESIONES)}


@app.get("/api/portales")
async def portales():
    return [{"id": p.id, "nombre": p.nombre, "entidad": p.entidad,
             "admite_nit": p.admite_nit, "nota": p.nota, "url": p.url}
            for p in CATALOGO]


@app.post("/api/sesion")
async def crear_sesion(req: SolicitudConsulta):
    limpiar_expiradas()
    numero = "".join(ch for ch in req.numero if ch.isdigit())
    if not numero:
        raise HTTPException(400, "El numero de documento debe contener digitos.")

    datos = DatosConsulta(
        tipo_doc=req.tipo_doc.upper(),
        numero=numero,
        fecha_expedicion=req.fecha_expedicion or None,
        nombre=(req.nombre or "").strip() or None,
        entidad=(req.entidad or "").strip() or None,
        nit_entidad=(req.nit_entidad or "").strip() or None,
    )
    # Se respeta la lista tal cual: vacia = solo certificados manuales (REDAM).
    s = Sesion(datos, req.portales)
    SESIONES[s.sid] = s
    return {"sid": s.sid,
            "portales": [{"id": p.id, "nombre": p.nombre, "entidad": p.entidad}
                         for p in s.portales()]}


MAX_ADJUNTO = 15 * 1024 * 1024   # 15 MB por PDF


@app.post("/api/sesion/{sid}/adjuntar")
async def adjuntar(sid: str,
                   archivo: UploadFile = File(...),
                   etiqueta: str = Form("Certificado adjuntado")):
    """Suma al consolidado un PDF que el usuario descargo por su cuenta
    (REDAM, o cualquier portal que hiciera manualmente)."""
    s = SESIONES.get(sid)
    if not s:
        raise HTTPException(404, "Sesion no encontrada o expirada.")
    datos = await archivo.read()
    if len(datos) > MAX_ADJUNTO:
        raise HTTPException(400, "El PDF supera el limite de 15 MB.")
    if datos[:4] != b"%PDF":
        raise HTTPException(400, "El archivo debe ser un PDF valido.")
    try:
        return {"ok": True, **s.agregar_adjunto(etiqueta.strip(), datos)}
    except Exception as e:
        raise HTTPException(400, f"No se pudo integrar el PDF: {type(e).__name__}")


@app.get("/api/pdf/{sid}")
async def descargar(sid: str):
    s = SESIONES.get(sid)
    if not s or not s.pdf_final:
        raise HTTPException(404, "PDF no disponible todavia.")
    return Response(
        content=s.pdf_final, media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{s.nombre_pdf}"'},
    )


@app.websocket("/ws/{sid}")
async def ws(sock: WebSocket, sid: str):
    await sock.accept()
    s = SESIONES.get(sid)
    if not s:
        await sock.send_text(json.dumps({"t": "error", "msg": "Sesion inexistente."}))
        await sock.close()
        return

    if s.tarea is None:
        s.tarea = asyncio.create_task(s.ejecutar())

    async def bombear():
        """Envia al celular todo lo que produce el motor."""
        while True:
            msg = await s.salida.get()
            await sock.send_text(json.dumps(msg))
            if msg.get("t") in ("fin", "error"):
                break

    tarea_salida = asyncio.create_task(bombear())
    try:
        while True:
            crudo = await sock.receive_text()
            try:
                await s.accion(json.loads(crudo))
            except json.JSONDecodeError:
                pass
            if tarea_salida.done():
                break
    except WebSocketDisconnect:
        pass
    finally:
        tarea_salida.cancel()


# --- PWA ----------------------------------------------------------------
if WEB.exists():
    app.mount("/app", StaticFiles(directory=str(WEB), html=True), name="web")

    @app.get("/")
    async def raiz():
        return FileResponse(WEB / "index.html")

    @app.get("/sw.js")
    async def sw():
        return FileResponse(WEB / "sw.js", media_type="application/javascript")

    @app.get("/manifest.webmanifest")
    async def manifest():
        return FileResponse(WEB / "manifest.webmanifest",
                            media_type="application/manifest+json")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=config.PUERTO)
