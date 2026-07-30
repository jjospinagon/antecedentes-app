import os

from .base import CazadorPDF, DatosConsulta, Portal, Resultado
from .contraloria import Contraloria
from .delitos_sexuales import DelitosSexuales
from .policia import PoliciaJudicial
from .procuraduria import Procuraduria
from .rnmc import RNMC

# Orden de ejecucion. Primero los que admiten NIT.
CATALOGO: list[Portal] = [Procuraduria(), Contraloria(), RNMC(),
                          PoliciaJudicial(), DelitosSexuales()]

# Portal simulado para probar la app sin consultar entidades reales.
if os.getenv("PORTAL_DEMO") == "1":
    from .demo import Demo
    CATALOGO.append(Demo())

POR_ID = {p.id: p for p in CATALOGO}

__all__ = [
    "CATALOGO", "POR_ID", "CazadorPDF", "DatosConsulta", "Portal", "Resultado",
    "Procuraduria", "Contraloria", "PoliciaJudicial", "RNMC",
]
