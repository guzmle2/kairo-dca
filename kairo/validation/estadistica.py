"""Estadística de validación sobre series de rendimientos de cualquier periodicidad.

Funciones puras y sin estado: reciben la periodicidad (``periodos_anio``) y el remuestreo en
``Remuestreo``, que sale de la configuración de cada prueba. No hay constantes de negocio aquí.
"""

from collections.abc import Callable
from dataclasses import dataclass
from statistics import NormalDist

import numpy as np

from kairo.constantes import PORCENTAJE

EULER = 0.5772156649  # constante de Euler-Mascheroni
NORMAL = NormalDist()
ITERACIONES_BISECCION = 60


@dataclass(frozen=True)
class Remuestreo:
    """Parámetros del bootstrap por bloques de una prueba."""

    bloque: int
    remuestreos: int
    semilla: int
    nivel_ic: float = 0.90


def sharpe(retornos: np.ndarray) -> float:
    """Sharpe por periodo (sin anualizar) con tasa libre de riesgo cero."""
    desviacion = retornos.std(ddof=1)
    return float(retornos.mean() / desviacion) if desviacion > 0 else 0.0


def sharpe_anual(retornos: np.ndarray, periodos_anio: int) -> float:
    return float(sharpe(retornos) * periodos_anio**0.5)


def cagr(retornos: np.ndarray, periodos_anio: int) -> float:
    return float(np.prod(1 + retornos) ** (periodos_anio / len(retornos)) - 1)


def volatilidad_anual(retornos: np.ndarray, periodos_anio: int) -> float:
    return float(retornos.std(ddof=1) * periodos_anio**0.5)


def drawdown_maximo(retornos: np.ndarray) -> float:
    """Caída máxima desde un máximo sobre la curva a precios de mercado."""
    curva = np.cumprod(1 + retornos)
    pico = np.maximum.accumulate(np.concatenate(([1.0], curva)))[1:]
    return float(np.max(1 - curva / pico))


def calmar(retornos: np.ndarray, periodos_anio: int) -> float:
    caida = drawdown_maximo(retornos)
    return cagr(retornos, periodos_anio) / caida if caida > 0 else float("inf")


def indices_remuestreo(n: int, m: Remuestreo) -> np.ndarray:
    """Índices de remuestreos por bloques de periodos consecutivos, iguales en cada llamada."""
    if n < m.bloque:
        raise ValueError("la serie es más corta que el bloque")
    rng = np.random.default_rng(m.semilla)
    inicios = rng.integers(0, n - m.bloque + 1, size=(m.remuestreos, n // m.bloque))
    return (inicios[:, :, None] + np.arange(m.bloque)).reshape(m.remuestreos, -1)


def bootstrap_pareado(
    a: np.ndarray,
    b: np.ndarray,
    m: Remuestreo,
    estadistico: Callable[[np.ndarray, np.ndarray], float],
) -> np.ndarray:
    """Distribución de ``estadistico(a, b)`` con los mismos bloques para las dos series."""
    if len(a) != len(b):
        raise ValueError("las series deben tener la misma longitud")
    indices = indices_remuestreo(len(a), m)
    return np.array([estadistico(a[i], b[i]) for i in indices])


def intervalo(valores: np.ndarray, m: Remuestreo) -> tuple[float, float]:
    """Intervalo percentil de nivel ``m.nivel_ic`` (por ejemplo 0,90 da los percentiles 5 y 95)."""
    cola = (1 - m.nivel_ic) / 2 * PORCENTAJE
    return float(np.percentile(valores, cola)), float(np.percentile(valores, PORCENTAJE - cola))


def peso_igual_volatilidad(
    base: np.ndarray, liquidez: np.ndarray, volatilidad_objetivo: float
) -> float:
    """Peso de ``base`` en una mezcla con ``liquidez`` que iguala la volatilidad objetivo.

    Devuelve un valor entre 0 y 1 (sin apalancamiento): 1 si la base ya es menos volátil.
    """

    def vol(w: float) -> float:
        return float((w * base + (1 - w) * liquidez).std(ddof=1))

    if vol(1.0) <= volatilidad_objetivo:
        return 1.0
    bajo, alto = 0.0, 1.0
    for _ in range(ITERACIONES_BISECCION):
        medio = (bajo + alto) / 2
        bajo, alto = (medio, alto) if vol(medio) < volatilidad_objetivo else (bajo, medio)
    return (bajo + alto) / 2


def deflated_sharpe(retornos: np.ndarray, sharpes_pruebas: list[float], n_pruebas: int) -> float:
    """DSR de Bailey y López de Prado (2014): P(Sharpe real > el esperado por azar).

    ``sharpes_pruebas`` son los Sharpe por periodo de las variantes probadas y ``n_pruebas`` el
    número total de pruebas (incluidas las que no se listan).
    """
    if retornos.std(ddof=1) == 0:
        return 0.0
    t = len(retornos)
    z = (retornos - retornos.mean()) / retornos.std(ddof=1)
    asimetria, curtosis = float((z**3).mean()), float((z**4).mean())
    sr = sharpe(retornos)
    varianza = float(np.var(sharpes_pruebas, ddof=1)) if len(sharpes_pruebas) > 1 else 0.0
    esperado = varianza**0.5 * (
        (1 - EULER) * NORMAL.inv_cdf(1 - 1 / n_pruebas)
        + EULER * NORMAL.inv_cdf(1 - 1 / (n_pruebas * np.e))
    )
    radicando = 1 - asimetria * sr + (curtosis - 1) / 4 * sr**2
    if radicando <= 0:
        return 0.0
    return NORMAL.cdf((sr - esperado) * (t - 1) ** 0.5 / radicando**0.5)
