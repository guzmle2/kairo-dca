"""Filtro de tendencia: impuesto por tramos, FIFO, señal, simulación y recorte de periodos."""

import json

import numpy as np
import pandas as pd
import pytest
from kairo.rutas import CONFIG, DATOS
from kairo.validation.filtro.criterios import Series, peor_crisis
from kairo.validation.filtro.serie import cargar_serie
from kairo.validation.filtro.simulacion import (
    Cartera,
    Variante,
    comprar,
    cuota_irpf,
    peso_objetivo,
    simular,
    vender,
)

CFG = json.loads((CONFIG / "f2_15.json").read_text(encoding="utf-8"))
SIN_COSTES = {"comision_pct": 0.0, "ter_anual": 0.0, "tramos": CFG["costes"]["tramos"]}


def test_cuota_por_tramos() -> None:
    tramos = CFG["costes"]["tramos"]
    assert cuota_irpf(6000, tramos) == pytest.approx(1140)
    assert cuota_irpf(10000, tramos) == pytest.approx(1140 + 4000 * 0.21)
    assert cuota_irpf(0, tramos) == 0


@pytest.mark.skipif(
    not (DATOS / "manifiesto.json").exists(), reason="ejecuta primero kairo.datos.descargar"
)
def test_la_serie_coincide_con_el_hash_y_cubre_todo_el_periodo() -> None:
    datos = cargar_serie(CFG["series"])
    assert datos.index[0] == pd.Period("1990-07", "M")
    assert datos.index[-1] == pd.Period(CFG["periodos"]["holdout"][1], "M")
    assert datos.notna().all().all()


def test_la_venta_usa_el_lote_mas_antiguo_y_anota_la_ganancia() -> None:
    c = Cartera(efectivo=300.0)
    comprar(c, 100.0, 10.0, 0.0)
    comprar(c, 200.0, 20.0, 0.0)
    vender(c, 150.0, 30.0, 0.0)  # 5 unidades al lote de 10: ganancia 100
    assert c.ganancias == pytest.approx(100.0)
    assert c.unidades() == pytest.approx(10.0 + 5.0)
    assert c.efectivo == pytest.approx(150.0)


def test_la_comision_reduce_unidades_y_efectivo() -> None:
    c = Cartera(efectivo=100.0)
    comprar(c, 100.0, 10.0, 0.01)
    assert c.unidades() == pytest.approx(100.0 / 10.0 / 1.01)
    assert c.efectivo == 0.0


def test_la_senal_es_cero_bajo_la_media_y_uno_sobre_ella() -> None:
    sube = np.full(30, 0.01)
    niveles = np.cumprod(1 + sube)
    v = Variante(sma_meses=10, vol_objetivo=None, vol_ventana=12)
    assert peso_objetivo(sube, niveles, 20, v) == 1.0
    baja = np.concatenate((np.full(20, 0.01), np.full(10, -0.05)))
    assert peso_objetivo(baja, np.cumprod(1 + baja), 29, v) == 0.0


def test_la_volatilidad_objetivo_solo_recorta_y_nunca_apalanca() -> None:
    rng = np.random.default_rng(3)
    r = np.concatenate((np.full(12, 0.01), rng.normal(0.01, 0.05, 30)))
    niveles = np.cumprod(1 + r)
    alta = Variante(sma_meses=3, vol_objetivo=0.05, vol_ventana=12)
    baja = Variante(sma_meses=3, vol_objetivo=5.0, vol_ventana=12)
    assert 0 < peso_objetivo(r, niveles, 40, alta) < 1
    assert peso_objetivo(r, niveles, 40, baja) == 1.0


def test_el_filtro_sale_tras_la_caida_y_conserva_capital() -> None:
    n = 60
    r = np.concatenate((np.full(30, 0.01), np.full(30, -0.04)))
    datos = pd.DataFrame(
        {"mercado": r, "rf": np.full(n, 0.002)},
        index=pd.period_range("2000-01", periods=n, freq="M"),
    )
    cfg = {"capital": 10000.0, "costes": SIN_COSTES}
    res = simular(cfg, datos, Variante(sma_meses=10, vol_objetivo=None, vol_ventana=12), 12)
    assert res["peso"][-1] == 0.0
    assert len(res["neto"]) == n - 12
    curva = np.cumprod(1 + res["neto"])
    assert curva[-1] > np.cumprod(1 + r[12:])[-1]


def test_la_peor_crisis_marca_los_meses_consecutivos_pedidos() -> None:
    rng = np.random.default_rng(4)
    f, comp = rng.normal(0.005, 0.02, 120), rng.normal(0.005, 0.02, 120)
    f[50:74] -= 0.05
    indice = pd.period_range("2000-01", periods=120, freq="M")
    serie = Series(f, comp, comp, indice, np.ones(120))
    mascara = peor_crisis(serie, 24)
    assert mascara.sum() == 24
    assert mascara[52:72].all()


@pytest.mark.skipif(
    not (DATOS / "manifiesto.json").exists(), reason="ejecuta primero kairo.datos.descargar"
)
def test_sin_costes_ni_impuestos_coincide_con_la_implementacion_vectorizada() -> None:
    """Réplica independiente: el filtro con datos reales y sin fricciones es una fórmula simple."""
    datos = cargar_serie(CFG["series"])
    v = CFG["variantes"]["principal"]
    sim = simular(
        {"capital": 10000.0, "costes": SIN_COSTES | {"tramos": [{"hasta": None, "tipo": 0.0}]}},
        datos,
        Variante(**v),
        12,
    )
    r, rf = datos["mercado"], datos["rf"]
    niveles = (1 + r).cumprod()
    senal = (niveles.shift(1) > niveles.rolling(v["sma_meses"]).mean().shift(1)).astype(float)
    vol = r.rolling(v["vol_ventana"]).std().shift(1) * np.sqrt(12)
    peso = senal * np.minimum(1, v["vol_objetivo"] / vol)
    esperado = (peso * r + (1 - peso) * rf).dropna().loc[sim["indice"][0] :]
    assert np.allclose(sim["neto"], esperado.to_numpy(), atol=1e-12)
