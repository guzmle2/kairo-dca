"""Carga de la serie mensual (Kenneth French, mercados desarrollados) con el hash comprobado."""

import hashlib
import re
from typing import Any

import pandas as pd

from kairo.constantes import PORCENTAJE
from kairo.rutas import RAIZ

DATO_AUSENTE = -99.99
PATRON_FILA = re.compile(r"^\d{6}\s*,")


def cargar_serie(series: dict[str, Any]) -> pd.DataFrame:
    """Rendimientos mensuales (fracción) del mercado y de la liquidez."""
    ruta = RAIZ / series["fichero"]
    huella = hashlib.sha256(ruta.read_bytes()).hexdigest()
    if huella != series["sha256"]:
        raise ValueError(f"el fichero de datos no coincide con la configuración: {huella}")
    filas = []
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        if PATRON_FILA.match(linea):
            fecha, exceso, _, _, liquidez = (x.strip() for x in linea.split(","))
            filas.append((pd.Period(fecha, "M"), float(exceso), float(liquidez)))
    datos = pd.DataFrame(filas, columns=["mes", "exceso", "rf"]).set_index("mes")
    if (datos == DATO_AUSENTE).any().any():
        raise ValueError("la serie tiene datos ausentes")
    return pd.DataFrame(
        {
            "mercado": (datos["exceso"] + datos["rf"]) / PORCENTAJE,
            "rf": datos["rf"] / PORCENTAJE,
        }
    )
