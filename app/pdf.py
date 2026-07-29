"""Consolidacion de los certificados en un unico PDF con caratula."""
from __future__ import annotations

import io
from datetime import datetime

from pypdf import PdfReader, PdfWriter
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from .portales.base import DatosConsulta, Resultado

TIPO_LARGO = {
    "CC": "Cedula de ciudadania",
    "CE": "Cedula de extranjeria",
    "TI": "Tarjeta de identidad",
    "PA": "Pasaporte",
    "NIT": "NIT",
}


def _caratula(datos: DatosConsulta, resultados: list[Resultado]) -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    ancho, alto = letter
    y = alto - 30 * mm

    c.setFillColor(colors.HexColor("#0F2A44"))
    c.rect(0, alto - 22 * mm, ancho, 22 * mm, stroke=0, fill=1)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 15)
    c.drawString(20 * mm, alto - 14 * mm, "CERTIFICADOS DE ANTECEDENTES")

    c.setFillColor(colors.HexColor("#111111"))
    c.setFont("Helvetica-Bold", 11)
    y -= 6 * mm
    c.drawString(20 * mm, y, "Identificacion consultada")
    c.setFont("Helvetica", 10)

    filas = [
        ("Tipo de documento", TIPO_LARGO.get(datos.tipo_doc.upper(), datos.tipo_doc)),
        ("Numero", datos.numero),
        ("Fecha de expedicion", datos.fecha_expedicion or "No aplica"),
        ("Titular", datos.nombre or "No declarado"),
        ("Fecha de consulta", datetime.now().strftime("%d/%m/%Y %H:%M")),
    ]
    for k, v in filas:
        y -= 7 * mm
        c.setFillColor(colors.HexColor("#555555"))
        c.drawString(22 * mm, y, f"{k}:")
        c.setFillColor(colors.black)
        c.drawString(70 * mm, y, str(v))

    y -= 14 * mm
    c.setFont("Helvetica-Bold", 11)
    c.drawString(20 * mm, y, "Certificados incluidos")

    y -= 4 * mm
    c.setStrokeColor(colors.HexColor("#DDDDDD"))
    c.line(20 * mm, y, ancho - 20 * mm, y)

    c.setFont("Helvetica", 9.5)
    for r in resultados:
        y -= 8 * mm
        c.setFillColor(colors.HexColor("#1B7F3B") if r.ok else colors.HexColor("#B3261E"))
        c.drawString(22 * mm, y, "OK " if r.ok else "X  ")
        c.setFillColor(colors.black)
        c.drawString(30 * mm, y, f"{r.portal_nombre} - {r.portal_id.upper()}")
        if not r.ok:
            y -= 5 * mm
            c.setFillColor(colors.HexColor("#777777"))
            c.setFont("Helvetica-Oblique", 8)
            c.drawString(30 * mm, y, r.detalle[:110])
            c.setFont("Helvetica", 9.5)

    c.setFillColor(colors.HexColor("#777777"))
    c.setFont("Helvetica-Oblique", 7.5)
    c.drawString(20 * mm, 18 * mm,
                 "Documento consolidado automaticamente. La validez juridica de cada")
    c.drawString(20 * mm, 14.5 * mm,
                 "certificado la determina la entidad emisora mediante su codigo de verificacion.")
    c.showPage()
    c.save()
    return buf.getvalue()


def consolidar(datos: DatosConsulta, resultados: list[Resultado]) -> bytes:
    """Une caratula + todos los certificados obtenidos en un solo PDF."""
    salida = PdfWriter()
    salida.append(PdfReader(io.BytesIO(_caratula(datos, resultados))))

    for r in resultados:
        if not (r.ok and r.pdf):
            continue
        try:
            salida.append(PdfReader(io.BytesIO(r.pdf)))
        except Exception:
            continue

    buf = io.BytesIO()
    salida.write(buf)
    return buf.getvalue()


def nombre_archivo(datos: DatosConsulta) -> str:
    base = f"ANTECEDENTES_{datos.numero}"
    if datos.nombre:
        limpio = "".join(ch for ch in datos.nombre.upper()
                         if ch.isalnum() or ch == " ").strip().replace(" ", "_")
        base += f"_{limpio[:40]}"
    return f"{base}_{datetime.now():%Y%m%d}.pdf"
