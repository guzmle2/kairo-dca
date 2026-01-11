"""Datos históricos: manifiesto con hashes, conversión a EUR y estadísticas descriptivas."""

import io
import json
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from kairo.datos.descargar import (
    CONFIG,
    MANIFIESTO,
    comprobar,
    descomprimir,
    escribir_atomico,
    huella,
    leer,
    leer_limitado,
)
from kairo.rutas import DATOS
from kairo.validation.descriptivo_eur import a_eur, estadisticas, retorno_bono_a_la_par

MAX = 1_000_000
VENCIMIENTO = 10.0


@pytest.mark.skipif(
    not (DATOS / "manifiesto.json").exists(), reason="ejecuta primero kairo.datos.descargar"
)
def test_los_datos_descargados_coinciden_con_el_manifiesto() -> None:
    assert MANIFIESTO.exists()
    assert comprobar() == []


def test_huella_estable_y_zip_de_un_fichero() -> None:
    assert huella(b"abc") == huella(b"abc") != huella(b"abd")
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as z:
        z.writestr("a.csv", "x,y\n1,2\n")
    assert descomprimir(buffer.getvalue(), "https://x/a.zip", MAX) == b"x,y\n1,2\n"
    assert descomprimir(b"plano", "https://x/a.csv", MAX) == b"plano"


def test_un_activo_en_usd_pierde_si_el_dolar_se_deprecia_frente_al_euro() -> None:
    meses = pd.PeriodIndex(["2020-01", "2020-02"], freq="M")
    cambio = pd.Series([1.10, 1.21], index=meses)  # el euro sube un 10 %
    rend = pd.Series([0.0, 0.0], index=meses)
    assert a_eur(rend, cambio).iloc[0] == pytest.approx(1.10 / 1.21 - 1)


def test_estadisticas_de_una_serie_conocida() -> None:
    r = np.array([0.10, -0.20, 0.05] + [0.0] * 9)
    e = estadisticas(r)
    assert e["caida_maxima"] == pytest.approx(0.20)
    assert e["peor_12_meses"] == pytest.approx(1.10 * 0.80 * 1.05 - 1)


def test_un_bono_a_la_par_sin_cambio_de_rendimiento_rinde_su_cupon_mensual() -> None:
    assert retorno_bono_a_la_par(0.03, 0.03, VENCIMIENTO) == pytest.approx(0.03 / 12)


def test_si_baja_el_rendimiento_el_bono_gana_y_si_sube_pierde() -> None:
    assert retorno_bono_a_la_par(0.03, 0.02, VENCIMIENTO) > 0.03 / 12
    assert retorno_bono_a_la_par(0.03, 0.04, VENCIMIENTO) < 0.03 / 12


def test_la_descarga_rechaza_urls_sin_tls_y_respuestas_gigantes() -> None:
    ajustes = json.loads(CONFIG.read_text(encoding="utf-8"))["descarga"]
    with pytest.raises(ValueError, match="https"):
        leer("http://ejemplo.invalido/datos.csv", ajustes)
    with pytest.raises(ValueError, match="supera el máximo"):
        leer_limitado(io.BytesIO(b"x" * 11), 10)
    assert leer_limitado(io.BytesIO(b"x" * 10), 10) == b"x" * 10


def test_un_zip_con_un_fichero_enorme_se_rechaza() -> None:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as z:
        z.writestr("a.csv", "x" * 100)
    with pytest.raises(ValueError, match="supera el máximo"):
        descomprimir(buffer.getvalue(), "https://x/a.zip", 10)


def test_la_escritura_atomica_no_deja_temporales(tmp_path: Path) -> None:
    ruta = tmp_path / "d.csv"
    escribir_atomico(ruta, b"uno")
    escribir_atomico(ruta, b"dos")
    assert ruta.read_bytes() == b"dos"
    assert [p.name for p in tmp_path.iterdir()] == ["d.csv"]
