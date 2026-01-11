"""Reglas fijas del modo avisador: funciones puras sobre registro, precios y configuración.

Ningún aviso ordena vender ni predice el mercado. El estado entre ejecuciones (último nivel de caída
avisado y último máximo avisado por ventana) es un diccionario de texto que el llamador guarda.
"""

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_FLOOR, Decimal, InvalidOperation

from kairo.aportaciones.registro import Aportacion, racha_de_meses
from kairo.avisos.ajustes import Avisos
from kairo.avisos.precios import Serie
from kairo.constantes import PORCENTAJE

Estado = dict[str, str]


@dataclass(frozen=True)
class Aviso:
    tipo: str
    texto: str


def hasta(precios: Serie, hoy: date) -> Serie:
    return [(f, p) for f, p in precios if f <= hoy]


def en_ventana(precios: Serie, hoy: date, dias: int) -> Serie:
    inicio = hoy - timedelta(days=dias)
    return [(f, p) for f, p in hasta(precios, hoy) if f > inicio]


def dias_sin_datos(precios: Serie, hoy: date) -> int | None:
    recientes = hasta(precios, hoy)
    return (hoy - recientes[-1][0]).days if recientes else None


def caida_pct(precios: Serie, hoy: date, dias: int) -> Decimal | None:
    """Caída (en %) del último precio frente al máximo de la ventana."""
    ventana = en_ventana(precios, hoy, dias)
    if not ventana:
        return None
    maximo = max(p for _, p in ventana)
    return (1 - ventana[-1][1] / maximo) * PORCENTAJE


def nivel(caida: Decimal, cada: Decimal) -> Decimal:
    """Múltiplo de ``cada`` inmediatamente inferior a la caída (con 33 y cada 10 da 30)."""
    return (caida / cada).to_integral_value(rounding=ROUND_FLOOR) * cada


def decimal_del_estado(estado: Estado, clave: str) -> Decimal:
    try:
        return Decimal(estado.get(clave, "0"))
    except InvalidOperation:
        raise ValueError(
            f"el fichero de estado está corrupto en {clave!r}: bórralo para rearmar"
        ) from None


def cobertura_suficiente(precios: Serie, hoy: date, ventana: int, cfg: Avisos) -> bool:
    """Hay datos desde, al menos, el porcentaje configurado de la ventana."""
    datos = hasta(precios, hoy)
    return (
        bool(datos) and (hoy - datos[0][0]).days >= ventana * cfg.cobertura_minima_pct / PORCENTAJE
    )


def evaluar_precios(
    precios: Serie, hoy: date, estado: Estado, cfg: Avisos
) -> tuple[list[Aviso], Estado]:
    """Avisos diarios de caída, nuevo máximo y falta de datos; devuelve también el estado nuevo."""
    nuevo = dict(estado)
    sin_datos = dias_sin_datos(precios, hoy)
    if sin_datos is None or sin_datos > cfg.dias_sin_datos_max:
        dias = "todos los" if sin_datos is None else str(sin_datos)
        return [Aviso("sin_datos", cfg.mensajes["sin_datos"].format(dias=dias))], nuevo
    avisos: list[Aviso] = []
    for ventana in cfg.ventanas_dias:
        caida = caida_pct(precios, hoy, ventana)
        if caida is None or not cobertura_suficiente(precios, hoy, ventana, cfg):
            continue
        clave_nivel, clave_maximo, clave_fecha = (
            f"nivel_{ventana}",
            f"maximo_{ventana}",
            f"fecha_maximo_{ventana}",
        )
        previo = decimal_del_estado(estado, clave_nivel)
        if caida >= cfg.umbral_caida_pct:
            actual = nivel(caida, cfg.reaviso_cada_puntos)
            if actual > previo:
                texto = cfg.mensajes["caida"].format(caida=f"{caida:.0f}", ventana=ventana)
                avisos.append(Aviso("caida", texto))
                nuevo[clave_nivel] = str(actual)
        elif caida < cfg.umbral_caida_pct - cfg.reaviso_cada_puntos:
            nuevo[clave_nivel] = "0"
        ultimo = en_ventana(precios, hoy, ventana)[-1][1]
        ultima_fecha = date.fromisoformat(estado[clave_fecha]) if clave_fecha in estado else None
        reciente = (
            ultima_fecha is not None and (hoy - ultima_fecha).days < cfg.nuevo_maximo_cada_dias
        )
        if caida == 0 and ultimo > decimal_del_estado(estado, clave_maximo) and not reciente:
            avisos.append(
                Aviso("nuevo_maximo", cfg.mensajes["nuevo_maximo"].format(ventana=ventana))
            )
            nuevo[clave_maximo], nuevo[clave_fecha] = str(ultimo), hoy.isoformat()
    return avisos, nuevo


def evaluar_calendario(
    hoy: date, filas: list[Aportacion], capital: Decimal | None, instrumento: str, cfg: Avisos
) -> list[Aviso]:
    """Recordatorio del día de aportación, aviso de registro que falta y revisiones por umbral."""
    avisos: list[Aviso] = []
    if hoy.day == cfg.dia_recordatorio:
        texto = cfg.mensajes["recordatorio"].format(
            instrumento=instrumento, racha=racha_de_meses(filas, hoy)
        )
        avisos.append(Aviso("recordatorio", texto))
        if capital is not None and capital >= cfg.capital_70_30:
            avisos.append(
                Aviso(
                    "revision_70_30",
                    cfg.mensajes["revision_70_30"],
                )
            )
        grande = cfg.aportacion_mensual >= cfg.aportacion_mensual_nivel_b
        if grande or (capital is not None and capital >= cfg.capital_nivel_b):
            avisos.append(Aviso("revision_nivel_b", cfg.mensajes["revision_nivel_b"]))
    if hoy.day == cfg.dia_aviso_falta_registro and not any(
        (f.fecha.year, f.fecha.month) == (hoy.year, hoy.month) for f in filas
    ):
        avisos.append(Aviso("falta_registro", cfg.mensajes["falta_registro"]))
    return avisos


def fuente_dudosa(calculado: Decimal, broker: Decimal, cfg: Avisos) -> Aviso | None:
    """Aviso si el valor calculado difiere del valor del bróker más del porcentaje configurado."""
    if broker <= 0:
        return None
    if abs(calculado - broker) / broker * PORCENTAJE > cfg.contraste_broker_pct:
        return Aviso(
            "fuente_dudosa", cfg.mensajes["fuente_dudosa"].format(pct=cfg.contraste_broker_pct)
        )
    return None
