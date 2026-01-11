"""Política de retiradas (cap. 0.13): importe mensual de la retirada planificada.

Kairo nunca retira ni mueve dinero (R1): calcula cuánto y la titular lo ejecuta. Las emergencias
salen del fondo de emergencia y no pasan por aquí. Nunca se vende para recuperar ni por miedo.
"""

from datetime import date
from decimal import ROUND_HALF_EVEN, Decimal

from kairo.avisos.ajustes import Retiradas
from kairo.constantes import PORCENTAJE

CENTIMO = Decimal("0.01")


def retirada_aplica(cfg: Retiradas, hoy: date, valor: Decimal) -> bool:
    """Exige estar activada, haber llegado a la fecha y haber alcanzado el capital objetivo."""
    if not cfg.activada or cfg.fecha_inicio is None or cfg.capital_objetivo is None:
        return False
    return hoy >= cfg.fecha_inicio and valor >= cfg.capital_objetivo


def retirada_mensual(
    cfg: Retiradas, hoy: date, valor: Decimal, valor_enero: Decimal, caida_pct: Decimal | None
) -> Decimal:
    """Un doceavo del porcentaje anual sobre el valor de enero, reducido con una caída fuerte."""
    if not retirada_aplica(cfg, hoy, valor):
        return Decimal(0)
    importe = valor_enero * cfg.porcentaje_anual / PORCENTAJE / cfg.meses
    if caida_pct is not None and caida_pct >= cfg.umbral_caida_pct:
        importe *= cfg.factor_en_caida
    return min(importe, valor).quantize(CENTIMO, rounding=ROUND_HALF_EVEN)
