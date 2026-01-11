"""Uso: ``python -m kairo.validation.filtro``. El hold-out solo se abre si el diseño cumple todo.

Cada tramo se evalúa solo con sus propios datos: el comparador, la línea base y el Sharpe de las
variantes del DSR se calculan dentro del tramo, de modo que el diseño nunca ve el hold-out.
"""

import json
import sys
from typing import Any

import numpy as np
import pandas as pd

from kairo.constantes import DECIMALES_INFORME, MESES_ANIO
from kairo.rutas import CONFIG, RAIZ, leer_json
from kairo.validation import estadistica as est
from kairo.validation.filtro.criterios import (
    Series,
    evaluar_basicos,
    evaluar_diseno,
    evaluar_holdout,
)
from kairo.validation.filtro.serie import cargar_serie
from kairo.validation.filtro.simulacion import Variante, comparador, linea_base, simular

VARIANTE_PRINCIPAL = "principal"


def mascara_tramo(indice: pd.PeriodIndex, inicio: str, fin: str) -> np.ndarray:
    return np.asarray(
        (indice >= pd.Period(inicio, "M")) & (indice <= pd.Period(fin, "M")), dtype=bool
    )


def calentamiento_meses(cfg: dict[str, Any]) -> int:
    ventanas = [(v["sma_meses"], v["vol_ventana"]) for v in cfg["variantes"].values()]
    return int(max(cfg["calentamiento_min_meses"], *(x for par in ventanas for x in par)))


def series_del_tramo(
    cfg: dict[str, Any], datos: pd.DataFrame, corridas: dict[str, Any], tramo: list[str]
) -> tuple[Series, list[float]]:
    """Series y Sharpe de las variantes restringidos a un tramo."""
    calentamiento = calentamiento_meses(cfg)
    principal = corridas[VARIANTE_PRINCIPAL]
    mascara = mascara_tramo(principal["indice"], *tramo)
    mercado = datos["mercado"].to_numpy()[calentamiento:][mascara]
    liquidez = datos["rf"].to_numpy()[calentamiento:][mascara]
    neto, ter = principal["neto"][mascara], cfg["costes"]["ter_anual"]
    series = Series(
        neto,
        comparador(mercado, liquidez, ter, float(neto.std(ddof=1))),
        linea_base(mercado, ter),
        principal["indice"][mascara],
        principal["peso"][mascara],
    )
    return series, [est.sharpe(c["neto"][mascara]) for c in corridas.values()]


def informe(cfg: dict[str, Any]) -> dict[str, Any]:
    datos = cargar_serie(cfg["series"])
    calentamiento = calentamiento_meses(cfg)
    corridas = {
        nombre: simular(cfg, datos, Variante(**p), calentamiento)
        for nombre, p in cfg["variantes"].items()
    }
    periodos = cfg["periodos"]
    diseno_series, sharpes = series_del_tramo(cfg, datos, corridas, periodos["diseno"])
    diseno = evaluar_diseno(cfg, diseno_series, sharpes)
    pasa_diseno = all(diseno["reglas"].values())
    holdout = None
    if pasa_diseno:
        holdout_series, _ = series_del_tramo(cfg, datos, corridas, periodos["holdout"])
        holdout = evaluar_holdout(cfg, holdout_series)
    mitades = []
    for tramo in periodos["mitades"]:
        m, _ = series_del_tramo(cfg, datos, corridas, tramo)
        mitades.append(
            {
                "tramo": tramo,
                "reglas": evaluar_basicos(m, cfg["criterios_vinculantes"]),
                "sharpe_filtro": est.sharpe_anual(m.filtro, MESES_ANIO),
                "sharpe_comparador": est.sharpe_anual(m.comparador, MESES_ANIO),
            }
        )
    aprobado = holdout is not None and holdout["pasa"]
    return {
        "diseno": diseno,
        "pasa_diseno": pasa_diseno,
        "holdout": holdout if holdout is not None else "no abierto",
        "mitades_informativas": mitades,
        "veredicto": "no refutado" if aprobado else "descartado: la línea base es el producto",
    }


def main() -> int:
    cfg = leer_json(CONFIG / "f2_15.json")
    res = informe(cfg)
    destino = RAIZ / cfg["informe"]
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(
        json.dumps(res, indent=1, ensure_ascii=False, default=float), encoding="utf-8"
    )
    redondeado = json.loads(
        json.dumps(res, default=float), parse_float=lambda x: round(float(x), DECIMALES_INFORME)
    )
    sys.stdout.write(json.dumps(redondeado, indent=1, ensure_ascii=False) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
