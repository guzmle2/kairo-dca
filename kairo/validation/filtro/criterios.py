"""Criterios vinculantes de F2-15 (cap. 0.4): umbrales y listas salen de ``config/f2_15.json``."""

from dataclasses import dataclass
from typing import Any, Literal

import numpy as np
import pandas as pd

from kairo.constantes import MESES_ANIO
from kairo.validation import estadistica as est

Criterio = Literal["caida_vs_comparador", "caida_vs_base", "calmar", "cagr"]
Config = dict[str, Any]


@dataclass(frozen=True)
class Series:
    filtro: np.ndarray
    comparador: np.ndarray
    base: np.ndarray
    indice: pd.PeriodIndex
    peso: np.ndarray

    def recortar(self, mascara: np.ndarray) -> "Series":
        return Series(
            self.filtro[mascara],
            self.comparador[mascara],
            self.base[mascara],
            self.indice[mascara],
            self.peso[mascara],
        )


def evaluar_basicos(s: Series, k: Config) -> dict[Criterio, bool]:
    dd_f, dd_c, dd_b = (est.drawdown_maximo(x) for x in (s.filtro, s.comparador, s.base))
    return {
        "caida_vs_comparador": dd_f <= (1 - k["caida_menor_que_comparador_igual_vol"]) * dd_c,
        "caida_vs_base": dd_f < dd_b,
        "calmar": est.calmar(s.filtro, MESES_ANIO) >= est.calmar(s.comparador, MESES_ANIO),
        "cagr": est.cagr(s.filtro, MESES_ANIO)
        >= est.cagr(s.base, MESES_ANIO) - k["cagr_neto_dif_max_puntos"],
    }


def peor_crisis(s: Series, meses: int) -> np.ndarray:
    """Máscara de los ``meses`` consecutivos donde el filtro pierde más frente al comparador."""
    exceso = np.log1p(s.filtro) - np.log1p(s.comparador)
    acumulado = np.convolve(exceso, np.ones(meses), mode="valid")
    inicio = int(np.argmin(acumulado))
    mascara = np.zeros(len(s.filtro), dtype=bool)
    mascara[inicio : inicio + meses] = True
    return mascara


def mejor_anio(s: Series) -> np.ndarray:
    """Máscara de los meses del año natural con mayor rendimiento de la línea base."""
    por_anio = pd.Series(s.base, index=s.indice).groupby(s.indice.year)
    mejor = por_anio.apply(lambda x: float(np.prod(1 + x.to_numpy(dtype=float)))).idxmax()
    return np.asarray(s.indice.year == mejor, dtype=bool)


def evaluar_subperiodos(cfg: Config, s: Series) -> dict[str, bool]:
    """Los criterios elegidos siguen cumpliéndose sin el mejor año y sin la peor crisis."""
    k = cfg["criterios_vinculantes"]
    huecos = {
        "sin_el_mejor_anio": mejor_anio(s),
        "sin_la_peor_crisis": peor_crisis(s, k["sin_peor_crisis_meses"]),
    }
    reglas: dict[str, bool] = {}
    for ambito, mascara in huecos.items():
        basicos = evaluar_basicos(s.recortar(~mascara), k)
        reglas |= {f"{ambito}/{c}": basicos[c] for c in cfg["criterios_en_subperiodos"]}
    return reglas


def cambios_al_anio(s: Series) -> float:
    return float(np.abs(np.diff((s.peso > 0).astype(int))).sum()) / (len(s.filtro) / MESES_ANIO)


def reduccion_de_caida(x: np.ndarray, y: np.ndarray) -> float:
    """Reducción relativa de la caída máxima de ``x`` frente a ``y``."""
    dd = est.drawdown_maximo(y)
    return (dd - est.drawdown_maximo(x)) / dd if dd > 0 else 0.0


def calmar_mayor(x: np.ndarray, y: np.ndarray) -> float:
    return float(est.calmar(x, MESES_ANIO) > est.calmar(y, MESES_ANIO))


def evaluar_estadisticos(
    cfg: Config, s: Series, sharpes: list[float]
) -> tuple[dict[str, bool], dict[str, float]]:
    b = cfg["bootstrap"]
    m = est.Remuestreo(b["bloque_meses"], b["remuestreos"], b["semilla"], b["ic_nivel"])
    reduccion = est.bootstrap_pareado(s.filtro, s.comparador, m, reduccion_de_caida)
    ic_inferior = est.intervalo(reduccion, m)[0]
    p_calmar = float(np.mean(est.bootstrap_pareado(s.filtro, s.base, m, calmar_mayor)))
    dsr = est.deflated_sharpe(s.filtro, sharpes, cfg["n"]["total"])
    reglas = {
        "bootstrap/ic_inferior_reduccion_caida": ic_inferior > b["ic_inferior_reduccion_caida_min"],
        "bootstrap/p_calmar": p_calmar >= b["p_calmar_filtro_mayor_base_min"],
        "bootstrap/dsr": dsr >= b["dsr_min"],
    }
    extra = {
        "ic_inferior_reduccion_caida": ic_inferior,
        "p_calmar_filtro_mayor_base": p_calmar,
        "dsr": dsr,
    }
    return reglas, extra


def medidas(s: Series) -> dict[str, float]:
    return {
        "meses": float(len(s.filtro)),
        "cagr_filtro": est.cagr(s.filtro, MESES_ANIO),
        "cagr_base": est.cagr(s.base, MESES_ANIO),
        "cagr_comparador": est.cagr(s.comparador, MESES_ANIO),
        "caida_filtro": est.drawdown_maximo(s.filtro),
        "caida_comparador": est.drawdown_maximo(s.comparador),
        "caida_base": est.drawdown_maximo(s.base),
        "calmar_filtro": est.calmar(s.filtro, MESES_ANIO),
        "calmar_comparador": est.calmar(s.comparador, MESES_ANIO),
        "calmar_base": est.calmar(s.base, MESES_ANIO),
        "sharpe_filtro": est.sharpe_anual(s.filtro, MESES_ANIO),
        "sharpe_comparador": est.sharpe_anual(s.comparador, MESES_ANIO),
        "cambios_al_anio": cambios_al_anio(s),
        "meses_en_mercado": float(np.mean(s.peso > 0)),
    }


def evaluar_diseno(cfg: Config, s: Series, sharpes: list[float]) -> dict[str, Any]:
    k = cfg["criterios_vinculantes"]
    reglas: dict[str, bool] = {f"diseno/{c}": ok for c, ok in evaluar_basicos(s, k).items()}
    reglas |= evaluar_subperiodos(cfg, s)
    reglas["cambios_al_anio"] = cambios_al_anio(s) <= k["cambios_al_anio_max_suma_3_activos"]
    estadisticos, extra = evaluar_estadisticos(cfg, s, sharpes)
    return {
        "medidas": medidas(s) | extra,
        "reglas": {n: bool(v) for n, v in (reglas | estadisticos).items()},
    }


def evaluar_holdout(cfg: Config, s: Series) -> dict[str, Any]:
    basicos = evaluar_basicos(s, cfg["criterios_vinculantes"])
    reglas = {f"holdout/{c}": bool(basicos[c]) for c in cfg["criterios_en_subperiodos"]}
    return {"reglas": reglas, "pasa": all(reglas.values())}
