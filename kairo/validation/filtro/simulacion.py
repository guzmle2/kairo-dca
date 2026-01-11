"""Simulación del filtro (media de N meses y volatilidad objetivo) con comisión, TER e impuesto."""

from collections import deque
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from kairo.constantes import MESES_ANIO
from kairo.validation import estadistica as est

UNIDADES_MINIMAS = 1e-12
Config = dict[str, Any]


@dataclass(frozen=True)
class Variante:
    sma_meses: int
    vol_objetivo: float | None
    vol_ventana: int


@dataclass
class Cartera:
    efectivo: float
    lotes: deque[list[float]] = field(default_factory=deque)  # [unidades, coste unitario]
    ganancias: float = 0.0

    def unidades(self) -> float:
        return sum(lote[0] for lote in self.lotes)

    def valor(self, precio: float) -> float:
        return self.efectivo + self.unidades() * precio

    def reducir(self, fraccion: float) -> None:
        """Quita una fracción del valor (TER o impuesto) sin realizar ganancias."""
        self.efectivo *= 1 - fraccion
        for lote in self.lotes:
            lote[0] *= 1 - fraccion
            lote[1] /= 1 - fraccion


def cuota_irpf(base: float, tramos: list[dict[str, Any]]) -> float:
    cuota, previo = 0.0, 0.0
    for t in tramos:
        techo = float("inf") if t["hasta"] is None else float(t["hasta"])
        cuota += max(0.0, min(base, techo) - previo) * t["tipo"]
        previo = techo
    return cuota


def comprar(c: Cartera, euros: float, precio: float, comision: float) -> None:
    unidades = euros / (precio * (1 + comision))
    c.efectivo -= euros
    c.lotes.append([unidades, euros / unidades])


def vender(c: Cartera, euros: float, precio: float, comision: float) -> None:
    """Vende por FIFO el importe pedido a precio de mercado y anota la ganancia realizada."""
    pendiente = euros / precio
    while pendiente > UNIDADES_MINIMAS and c.lotes:
        lote = c.lotes[0]
        tomadas = min(pendiente, lote[0])
        neto = tomadas * precio * (1 - comision)
        c.efectivo += neto
        c.ganancias += neto - tomadas * lote[1]
        lote[0] -= tomadas
        pendiente -= tomadas
        if lote[0] <= UNIDADES_MINIMAS:
            c.lotes.popleft()


def peso_objetivo(r: np.ndarray, niveles: np.ndarray, t: int, v: Variante) -> float:
    """Peso en renta variable para el mes ``t`` con datos hasta el cierre de ``t - 1``."""
    if niveles[t - 1] <= niveles[t - v.sma_meses : t].mean():
        return 0.0
    if not v.vol_objetivo:
        return 1.0
    sigma = float(r[t - v.vol_ventana : t].std(ddof=1) * MESES_ANIO**0.5)
    return min(1.0, v.vol_objetivo / sigma) if sigma > 0 else 1.0


def simular(cfg: Config, datos: pd.DataFrame, v: Variante, calentamiento: int) -> dict[str, Any]:
    """Rendimiento neto mensual del filtro tras comisión, TER e impuesto anual por FIFO."""
    r, rf = datos["mercado"].to_numpy(), datos["rf"].to_numpy()
    niveles = np.cumprod(1 + r)
    comision, ter = cfg["costes"]["comision_pct"], cfg["costes"]["ter_anual"] / MESES_ANIO
    c = Cartera(efectivo=cfg["capital"])
    netos: list[float] = []
    pesos: list[float] = []
    for t in range(calentamiento, len(r)):
        precio = float(niveles[t - 1])
        inicio = c.valor(precio)
        diferencia = peso_objetivo(r, niveles, t, v) * inicio - c.unidades() * precio
        if diferencia > 0:
            comprar(c, diferencia, precio, comision)
        elif diferencia < 0:
            vender(c, -diferencia, precio, comision)
        pesos.append(c.unidades() * precio / c.valor(precio))
        c.efectivo *= 1 + rf[t]
        precio_fin = precio * (1 + r[t])
        c.reducir(ter * c.unidades() * precio_fin / c.valor(precio_fin))
        if datos.index[t].month == MESES_ANIO:
            impuesto = cuota_irpf(max(0.0, c.ganancias), cfg["costes"]["tramos"])
            c.reducir(min(1.0, impuesto / c.valor(precio_fin)) if impuesto else 0.0)
            c.ganancias = 0.0
        netos.append(c.valor(precio_fin) / inicio - 1)
    return {"neto": np.array(netos), "peso": np.array(pesos), "indice": datos.index[calentamiento:]}


def linea_base(mercado: np.ndarray, ter_anual: float) -> np.ndarray:
    """Comprar y mantener renta variable global con el mismo TER y sin vender."""
    return np.asarray((1 + mercado) * (1 - ter_anual / MESES_ANIO) - 1)


def comparador(
    mercado: np.ndarray, liquidez: np.ndarray, ter_anual: float, objetivo_vol: float
) -> np.ndarray:
    """Línea base mezclada con liquidez hasta igualar la volatilidad del filtro (con TER)."""
    w = est.peso_igual_volatilidad(mercado, liquidez, objetivo_vol)
    return np.asarray(w * mercado + (1 - w) * liquidez - ter_anual / MESES_ANIO * w)
