"""Descripción en EUR de la bolsa, los bonos y el oro (no es una prueba de estrategia).

Usa las series de ``datos/`` (MSCI World neto en EUR, bono alemán a 10 años del Bundesbank y oro
convertido con el tipo de cambio mensual del BCE). Sirve para decidir la tolerancia a la caída,
no para elegir una regla: no suma a N. Uso: ``python -m kairo.validation.descriptivo_eur``.
"""

import json
import re
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from kairo.constantes import DECIMALES_INFORME, MESES_ANIO, PORCENTAJE
from kairo.rutas import CONFIG, DATOS, leer_json
from kairo.validation import estadistica as est


def configuracion() -> dict[str, Any]:
    cfg: dict[str, Any] = leer_json(CONFIG / "datos.json")
    return cfg


def ruta_fuente(nombre: str) -> Path:
    return Path(DATOS / str(configuracion()["fuentes"][nombre]["fichero"]))


def msci_eur() -> pd.Series:
    niveles = leer_json(ruta_fuente("msci_world_neto_eur"))
    filas = niveles["indexes"]["INDEX_LEVELS"]
    serie = pd.Series(
        [f["level_eod"] for f in filas],
        index=pd.PeriodIndex([str(f["calc_date"])[:6] for f in filas], freq="M"),
    )
    return serie.pct_change().dropna()


def eurusd() -> pd.Series:
    d = pd.read_csv(ruta_fuente("eurusd_bce"))
    return pd.Series(d["OBS_VALUE"].to_numpy(), index=pd.PeriodIndex(d["TIME_PERIOD"], freq="M"))


def rendimientos_bund() -> pd.Series:
    """Rendimiento (fracción) de fin de mes del bono alemán a 10 años."""
    texto = ruta_fuente("bund_10_anios_bundesbank").read_text(encoding="utf-8-sig")
    fechas: list[pd.Period] = []
    valores: list[float] = []
    for linea in texto.splitlines():
        campos = linea.split(";")
        if re.match(r"^\d{4}-\d{2}-\d{2}$", campos[0]) and re.match(
            r"^\d+,\d+$", campos[1].strip()
        ):
            fechas.append(pd.Period(campos[0], "M"))
            valores.append(float(campos[1].replace(",", ".")) / 100)
    return pd.Series(valores, index=pd.PeriodIndex(fechas)).groupby(level=0).last()


def retorno_bono_a_la_par(y_inicio: float, y_fin: float, vencimiento: float) -> float:
    """Retorno mensual de un bono a la par: cupón ``y_inicio``, venta al rendimiento ``y_fin``."""
    n = vencimiento - 1 / MESES_ANIO
    anualidad = (1 - (1 + y_fin) ** -n) / y_fin if y_fin > 0 else n
    precio = y_inicio * anualidad + (1 + y_fin) ** -n
    return float(precio - 1 + y_inicio / MESES_ANIO)


def bonos_eur(vencimiento: float) -> pd.Series:
    y = rendimientos_bund()
    return pd.Series(
        [
            retorno_bono_a_la_par(a, b, vencimiento)
            for a, b in zip(y.shift(1).dropna(), y.iloc[1:], strict=True)
        ],
        index=y.index[1:],
    )


def oro_usd() -> pd.Series:
    d = pd.read_csv(ruta_fuente("oro_mensual"))
    return (
        pd.Series(d["Price"].to_numpy(), index=pd.PeriodIndex(d["Date"], freq="M"))
        .pct_change()
        .dropna()
    )


def a_eur(rend_usd: pd.Series, cambio: pd.Series) -> pd.Series:
    """Rendimiento en EUR de un activo en USD sin cobertura de divisa."""
    previo = cambio.shift(1)
    return ((1 + rend_usd) * previo / cambio - 1).dropna()


def estadisticas(r: np.ndarray) -> dict[str, float]:
    doce = np.convolve(np.log1p(r), np.ones(MESES_ANIO), mode="valid")
    return {
        "meses": float(len(r)),
        "cagr": est.cagr(r, MESES_ANIO),
        "volatilidad": est.volatilidad_anual(r, MESES_ANIO),
        "caida_maxima": est.drawdown_maximo(r),
        "peor_12_meses": float(np.expm1(doce.min())),
    }


def main() -> int:
    ajustes = configuracion()["descriptivo"]
    peso_bolsa = ajustes["peso_bolsa"]
    cambio = eurusd()
    series: dict[str, pd.Series] = {
        "bolsa_msci_world_eur": msci_eur(),
        "bonos_alemania_10_anios_eur": bonos_eur(ajustes["vencimiento_bono_anios"]),
        "oro_en_eur": a_eur(oro_usd(), cambio),
    }
    comun = pd.concat(series, axis=1).dropna()
    pesos = f"{round(peso_bolsa * PORCENTAJE)}_{round((1 - peso_bolsa) * PORCENTAJE)}"
    etiqueta_cartera = f"cartera_{pesos}_bolsa_bonos"
    comun[etiqueta_cartera] = (
        peso_bolsa * comun["bolsa_msci_world_eur"]
        + (1 - peso_bolsa) * comun["bonos_alemania_10_anios_eur"]
    )
    salida: dict[str, Any] = {
        "periodo": [str(comun.index[0]), str(comun.index[-1])],
        "nota": (
            "rebalanceo mensual a pesos fijos; bono alemán a 10 años sintético "
            "a partir del rendimiento; "
            "sin comisiones ni impuestos"
        ),
        "series": {n: estadisticas(comun[n].to_numpy()) for n in comun},
    }
    sys.stdout.write(
        json.dumps(
            salida,
            indent=1,
            ensure_ascii=False,
            default=lambda x: round(float(x), DECIMALES_INFORME),
        )
        + "\n"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
