"""Ajustes de ``config/aportaciones.json``: ``Decimal`` (R8) y dentro de los límites de R4."""

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from functools import cache
from pathlib import Path
from typing import Any

from kairo.cartera import hard_limits as hl
from kairo.rutas import CONFIG, RAIZ, leer_json

FICHERO = CONFIG / "aportaciones.json"
ESTADO_ACTIVO = "activo"


@dataclass(frozen=True)
class Ajustes:
    registro: Path
    pais: str
    divisa: str
    estado: str
    instrumento_predeterminado: str
    broker_predeterminado: str
    isin_permitidos: frozenset[str]
    comision_max_por_aportacion_pct: Decimal
    tolerancia_importe: Decimal
    tolerancia_unidades: Decimal


def a_decimal(c: dict[str, Any], clave: str, techo: Decimal | None = None) -> Decimal:
    """Importe de la configuración: texto (no número JSON), finito, no negativo y bajo el techo."""
    bruto = c[clave]
    if not isinstance(bruto, str):
        raise ValueError(f"{clave} debe escribirse entre comillas para no perder exactitud (R8)")
    try:
        valor = Decimal(bruto)
    except InvalidOperation as error:
        raise ValueError(f"{clave} no es un número: {bruto!r}") from error
    if not valor.is_finite() or valor < 0 or (techo is not None and valor > techo):
        raise ValueError(f"{clave}={bruto} fuera del rango permitido")
    return valor


@cache
def cargar(fichero: Path = FICHERO) -> Ajustes:
    c = leer_json(fichero)
    ruta_perfil = CONFIG / f"perfil_{c['perfil']}.json"
    if not ruta_perfil.exists():
        raise ValueError(f"perfil no soportado: {c['perfil']!r}")
    perfil = leer_json(ruta_perfil)
    isin = frozenset(perfil["isin_permitidos"])
    if not isin:
        raise ValueError("la lista de ISIN permitidos del perfil no puede estar vacía")
    return Ajustes(
        registro=RAIZ / c["registro"],
        pais=perfil["pais"],
        divisa=perfil["divisa"],
        estado=perfil["estado"],
        instrumento_predeterminado=sorted(isin)[0],
        broker_predeterminado=perfil["broker"]["candidato"],
        isin_permitidos=isin,
        comision_max_por_aportacion_pct=a_decimal(
            perfil["umbrales_r12a"],
            "comision_max_por_aportacion_pct",
            hl.COMISION_MAX_POR_APORTACION_PCT,
        ),
        tolerancia_importe=a_decimal(c["tolerancias"], "importe_eur"),
        tolerancia_unidades=a_decimal(c["tolerancias"], "unidades"),
    )
