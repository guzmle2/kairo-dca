"""Ajustes de ``config/avisos.json`` y ``config/retiradas.json``; importes en ``Decimal`` (R8)."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

from kairo.constantes import DIA_MAX_MES, PORCENTAJE
from kairo.rutas import CONFIG, RAIZ, leer_json


def decimal(texto: Any, campo: str) -> Decimal:
    if not isinstance(texto, str):
        raise ValueError(f"{campo} debe escribirse entre comillas para no perder exactitud (R8)")
    valor = Decimal(texto)
    if not valor.is_finite() or valor < 0:
        raise ValueError(f"{campo} debe ser un número finito no negativo")
    return valor


@dataclass(frozen=True)
class Avisos:
    precios: Path
    estado: Path
    ventanas_dias: tuple[int, ...]
    umbral_caida_pct: Decimal
    reaviso_cada_puntos: Decimal
    dias_sin_datos_max: int
    dia_recordatorio: int
    dia_aviso_falta_registro: int
    aportacion_mensual: Decimal
    capital_70_30: Decimal
    aportacion_mensual_nivel_b: Decimal
    capital_nivel_b: Decimal
    contraste_broker_pct: Decimal
    cobertura_minima_pct: Decimal
    nuevo_maximo_cada_dias: int
    dias_atraso_max: int
    variable_token: str
    variable_chat: str
    mensajes: dict[str, str]


@dataclass(frozen=True)
class Retiradas:
    activada: bool
    capital_objetivo: Decimal | None
    fecha_inicio: date | None
    porcentaje_anual: Decimal
    factor_en_caida: Decimal
    umbral_caida_pct: Decimal
    ventana_caida_dias: int
    meses: int


def cargar_avisos(fichero: Path = CONFIG / "avisos.json") -> Avisos:
    c = leer_json(fichero)
    r = c["revision"]
    dias = (c["dia_recordatorio"], c["dia_aviso_falta_registro"])
    if not all(1 <= d <= DIA_MAX_MES for d in dias):
        raise ValueError("los días de aviso deben estar entre 1 y 28")
    return Avisos(
        precios=RAIZ / c["precios"],
        estado=RAIZ / c["estado"],
        ventanas_dias=tuple(int(v) for v in c["ventanas_dias"]),
        umbral_caida_pct=decimal(c["umbral_caida_pct"], "umbral_caida_pct"),
        reaviso_cada_puntos=decimal(c["reaviso_cada_puntos"], "reaviso_cada_puntos"),
        dias_sin_datos_max=int(c["dias_sin_datos_max"]),
        dia_recordatorio=int(c["dia_recordatorio"]),
        dia_aviso_falta_registro=int(c["dia_aviso_falta_registro"]),
        aportacion_mensual=decimal(c["aportacion_mensual"], "aportacion_mensual"),
        capital_70_30=decimal(r["capital_70_30"], "capital_70_30"),
        aportacion_mensual_nivel_b=decimal(r["aportacion_mensual_nivel_b"], "aportacion_nivel_b"),
        capital_nivel_b=decimal(r["capital_nivel_b"], "capital_nivel_b"),
        contraste_broker_pct=decimal(c["contraste_broker_pct"], "contraste_broker_pct"),
        cobertura_minima_pct=decimal(c["cobertura_minima_pct"], "cobertura_minima_pct"),
        nuevo_maximo_cada_dias=int(c["nuevo_maximo_cada_dias"]),
        dias_atraso_max=int(c["dias_atraso_max"]),
        variable_token=c["variables_entorno"]["token"],
        variable_chat=c["variables_entorno"]["chat"],
        mensajes=dict(c["mensajes"]),
    )


def cargar_retiradas(fichero: Path = CONFIG / "retiradas.json") -> Retiradas:
    c = leer_json(fichero)
    if not isinstance(c["activada"], bool):
        raise ValueError("activada debe ser true o false")
    objetivo, inicio = c["capital_objetivo"], c["fecha_inicio"]
    if c["activada"] and (objetivo is None or inicio is None):
        raise ValueError("una retirada activada necesita capital_objetivo y fecha_inicio")
    r = Retiradas(
        activada=c["activada"],
        capital_objetivo=None if objetivo is None else decimal(objetivo, "capital_objetivo"),
        fecha_inicio=None if inicio is None else date.fromisoformat(inicio),
        porcentaje_anual=decimal(c["porcentaje_anual"], "porcentaje_anual"),
        factor_en_caida=decimal(c["factor_en_caida"], "factor_en_caida"),
        umbral_caida_pct=decimal(c["umbral_caida_pct"], "umbral_caida_pct"),
        ventana_caida_dias=int(c["ventana_caida_dias"]),
        meses=int(c["meses"]),
    )
    if r.meses < 1 or r.porcentaje_anual > PORCENTAJE or r.factor_en_caida > 1:
        raise ValueError("meses >= 1, porcentaje_anual <= 100 y factor_en_caida <= 1")
    return r
