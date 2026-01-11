"""Estadística de validación: métricas, bootstrap determinista y mezcla a igual volatilidad."""

import numpy as np
import pytest
from kairo.validation.estadistica import (
    Remuestreo,
    bootstrap_pareado,
    cagr,
    calmar,
    deflated_sharpe,
    drawdown_maximo,
    indices_remuestreo,
    peso_igual_volatilidad,
    sharpe_anual,
)

M = Remuestreo(bloque=12, remuestreos=200, semilla=7)


def serie(n: int = 240, media: float = 0.006, vol: float = 0.03, semilla: int = 1) -> np.ndarray:
    return np.random.default_rng(semilla).normal(media, vol, n)


def test_cagr_de_un_rendimiento_constante() -> None:
    assert cagr(np.full(12, 0.01), 12) == pytest.approx(1.01**12 - 1)


def test_drawdown_de_una_caida_conocida() -> None:
    assert drawdown_maximo(np.array([0.10, -0.20, 0.05])) == pytest.approx(0.20)
    assert drawdown_maximo(np.full(5, 0.01)) == 0.0


def test_calmar_sin_caida_es_infinito() -> None:
    assert calmar(np.full(12, 0.01), 12) == float("inf")


def test_sharpe_de_serie_degenerada_es_cero() -> None:
    assert sharpe_anual(np.zeros(24), 12) == 0.0


def test_remuestreo_es_determinista_y_respeta_el_bloque() -> None:
    a, b = indices_remuestreo(100, M), indices_remuestreo(100, M)
    assert (a == b).all()
    assert a.shape == (200, 96)
    assert (np.diff(a[:, :12], axis=1) == 1).all()


def test_remuestreo_rechaza_series_cortas() -> None:
    with pytest.raises(ValueError, match="más corta"):
        indices_remuestreo(5, M)


def test_bootstrap_pareado_usa_los_mismos_bloques() -> None:
    r = serie()
    diferencias = bootstrap_pareado(r, r, M, lambda x, y: float((x - y).sum()))
    assert (diferencias == 0).all()
    with pytest.raises(ValueError, match="misma longitud"):
        bootstrap_pareado(r, r[:-1], M, lambda x, y: 0.0)


def test_mezcla_a_igual_volatilidad_iguala_la_objetivo() -> None:
    base, liquidez = serie(vol=0.04), serie(vol=0.002, media=0.0003, semilla=2)
    objetivo = float(np.std(base, ddof=1)) / 2
    w = peso_igual_volatilidad(base, liquidez, objetivo)
    assert 0 < w < 1
    assert (w * base + (1 - w) * liquidez).std(ddof=1) == pytest.approx(objetivo, rel=1e-6)


def test_mezcla_no_apalanca_si_la_base_ya_es_menos_volatil() -> None:
    base, liquidez = serie(vol=0.01), serie(vol=0.001, semilla=2)
    assert peso_igual_volatilidad(base, liquidez, 0.05) == 1.0


def test_dsr_penaliza_mas_pruebas_y_es_cero_sin_variacion() -> None:
    r = serie(media=0.01)
    sharpes = [0.10, 0.12, 0.30, 0.05]
    pocas, muchas = deflated_sharpe(r, sharpes, 4), deflated_sharpe(r, sharpes, 100)
    assert muchas < pocas
    assert deflated_sharpe(np.zeros(50), sharpes, 4) == 0.0
