"""Aportaciones: validación, registro de solo añadir, resumen, meses sin aportación y CLI."""

import csv
from dataclasses import replace
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from hypothesis import given
from hypothesis import strategies as st
from kairo.aportaciones import __main__ as cli
from kairo.aportaciones.ajustes import Ajustes, a_decimal, cargar
from kairo.aportaciones.registro import (
    Aportacion,
    anadir,
    desde_fila,
    leer,
    meses_sin_aportacion,
    racha_de_meses,
)

HOY = date(2024, 12, 31)


def test_la_aportacion_correcta_valida_sin_avisos(ajustes: Ajustes, crear: Any) -> None:
    a = crear()
    a.validar(ajustes)
    assert a.avisos(ajustes, HOY) == []


@pytest.mark.parametrize(
    ("cambios", "texto"),
    [
        ({"isin": "IE00B0M62Q58"}, "lista cerrada"),
        ({"isin": "ie00b4l5y983"}, "lista cerrada"),
        ({"importe": Decimal(0)}, "positivos"),
        ({"unidades": Decimal("-1")}, "positivos"),
        ({"comision": Decimal("-0.1")}, "positivos"),
        ({"unidades": Decimal("3.0000")}, "cuadran"),
        ({"precio": Decimal("Infinity")}, "finitos"),
        ({"importe": Decimal("NaN")}, "finitos"),
    ],
)
def test_una_aportacion_invalida_se_rechaza(
    ajustes: Ajustes, crear: Any, cambios: dict[str, object], texto: str
) -> None:
    with pytest.raises(ValueError, match=texto):
        crear(**cambios).validar(ajustes)


def test_los_avisos_cubren_comision_alta_y_fecha_futura(ajustes: Ajustes, crear: Any) -> None:
    cara = crear(comision=Decimal("1.25"), unidades=Decimal("1.9983"))
    assert len(cara.avisos(ajustes, HOY)) == 1
    assert "fecha futura" in crear(fecha=date(2025, 1, 1)).avisos(ajustes, HOY)[0]


def test_el_registro_solo_anade_y_conserva_las_filas_anteriores(
    ajustes: Ajustes, crear: Any, tmp_path: Path
) -> None:
    ruta = tmp_path / "r" / "aportaciones.csv"
    anadir(ruta, crear(), ajustes, hoy=HOY)
    primera = ruta.read_bytes()
    anadir(ruta, crear(fecha=date(2024, 12, 1)), ajustes, hoy=HOY)
    assert ruta.read_bytes().startswith(primera)
    assert [x.fecha for x in leer(ruta)] == [date(2024, 11, 1), date(2024, 12, 1)]
    assert ruta.read_text().count("fecha,isin") == 1


def test_una_fila_invalida_no_toca_el_fichero(ajustes: Ajustes, crear: Any, tmp_path: Path) -> None:
    ruta = tmp_path / "a.csv"
    with pytest.raises(ValueError, match="lista cerrada"):
        anadir(ruta, crear(isin="IE00B0M62Q58"), ajustes, hoy=HOY)
    assert not ruta.exists()


def test_un_fichero_vacio_recibe_la_cabecera(ajustes: Ajustes, crear: Any, tmp_path: Path) -> None:
    ruta = tmp_path / "a.csv"
    ruta.touch()
    anadir(ruta, crear(), ajustes, hoy=HOY)
    assert leer(ruta) == [crear()]


def test_el_duplicado_exacto_se_avisa_pero_se_anota(
    ajustes: Ajustes, crear: Any, tmp_path: Path
) -> None:
    ruta = tmp_path / "a.csv"
    anadir(ruta, crear(), ajustes, hoy=HOY)
    assert "duplicado" in anadir(ruta, crear(), ajustes, hoy=HOY)[0]
    assert len(leer(ruta)) == 2


def test_los_importes_se_leen_como_decimal_exacto(
    ajustes: Ajustes, crear: Any, tmp_path: Path
) -> None:
    ruta = tmp_path / "a.csv"
    anadir(ruta, crear(), ajustes, hoy=HOY)
    leido = leer(ruta)[0]
    assert isinstance(leido.importe, Decimal)
    assert leido == crear()


@pytest.mark.parametrize(
    "fila",
    [
        {"fecha": "2024-13-01"},
        {"fecha": "2024-11-01", "isin": "X", "importe": "abc"},
        {"fecha": "2024-11-01", "isin": "X", "importe": "NaN"},
        {"fecha": "2024-11-01", "isin": "X"},
    ],
)
def test_una_fila_corrupta_falla_en_voz_alta(fila: dict[str, str]) -> None:
    with pytest.raises(ValueError):
        desde_fila(fila)


def test_un_csv_con_columnas_faltantes_falla_al_leer(tmp_path: Path) -> None:
    ruta = tmp_path / "a.csv"
    with ruta.open("w", newline="") as f:
        csv.writer(f).writerows([["fecha", "isin"], ["2024-11-01", "IE00B4L5Y983"]])
    with pytest.raises(ValueError, match="incompleta"):
        leer(ruta)


def test_meses_sin_aportacion_ignora_el_mes_en_curso_y_cruza_el_anio(crear: Any) -> None:
    filas = [crear(fecha=date(2024, 11, 5)), crear(fecha=date(2025, 2, 5))]
    assert meses_sin_aportacion(filas, date(2025, 3, 10)) == [(2024, 12), (2025, 1)]
    assert meses_sin_aportacion(filas, date(2025, 2, 20)) == [(2024, 12), (2025, 1)]
    assert meses_sin_aportacion([], date(2025, 3, 10)) == []


def test_la_racha_cuenta_meses_seguidos_y_se_corta_con_un_hueco(crear: Any) -> None:
    filas = [crear(fecha=date(2024, m, 5)) for m in (9, 11, 12)] + [crear(fecha=date(2025, 1, 5))]
    assert racha_de_meses(filas, date(2025, 1, 20)) == 3
    assert racha_de_meses(filas, date(2025, 2, 10)) == 3  # el mes en curso aún no tiene aportación
    assert racha_de_meses(filas, date(2025, 3, 10)) == 0
    assert racha_de_meses([], date(2025, 1, 1)) == 0


@given(st.lists(st.decimals(min_value="1", max_value="5000", places=2), min_size=1, max_size=12))
def test_el_total_aportado_es_la_suma_exacta_y_no_depende_del_orden(
    importes: list[Decimal],
) -> None:
    def fila(i: Decimal) -> Aportacion:
        precio = Decimal("149.5")
        return Aportacion(date(2024, 1, 1), "IE00B4L5Y983", i, i / precio, precio, Decimal(0))

    filas = [fila(i) for i in importes]
    a, b = cli.resumen(filas, HOY), cli.resumen(list(reversed(filas)), HOY)
    assert a.splitlines()[1] == b.splitlines()[1]
    assert f"{sum(importes, Decimal(0)):.2f}" in a


def test_el_resumen_con_importes_nulos_no_divide_por_cero(crear: Any) -> None:
    assert "revisa" in cli.resumen([crear(importe=Decimal(0), unidades=Decimal(0))], HOY)


def test_la_configuracion_exige_decimales_en_texto_y_dentro_de_los_limites() -> None:
    with pytest.raises(ValueError, match="comillas"):
        a_decimal({"x": 0.01}, "x")
    with pytest.raises(ValueError, match="rango"):
        a_decimal({"x": "NaN"}, "x")
    with pytest.raises(ValueError, match="rango"):
        a_decimal({"x": "0.6"}, "x", Decimal("0.5"))


def test_un_perfil_de_pais_no_soportado_falla_en_voz_alta(tmp_path: Path) -> None:
    ruta = tmp_path / "a.json"
    ruta.write_text('{"perfil": "xx", "registro": "r.csv", "tolerancias": {}}')
    with pytest.raises(ValueError, match="no soportado"):
        cargar(ruta)


@pytest.mark.parametrize("pais", ["de", "us", "mx"])
def test_los_perfiles_en_borrador_se_cargan_y_avisan_de_que_no_estan_verificados(
    tmp_path: Path, pais: str
) -> None:
    ruta = tmp_path / "a.json"
    tolerancias = '{"importe_eur": "0.01", "unidades": "0.0001"}'
    ruta.write_text(f'{{"perfil": "{pais}", "registro": "r.csv", "tolerancias": {tolerancias}}}')
    perfil = cargar(ruta)
    assert perfil.estado == "borrador"
    assert perfil.isin_permitidos


def test_la_linea_de_ordenes_avisa_si_el_perfil_esta_en_borrador(
    ajustes: Ajustes,
    isin: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        cli, "cargar", lambda: replace(ajustes, estado="borrador", registro=tmp_path / "r.csv")
    )
    assert cli.main(["resumen"]) == 0
    assert "datos sin verificar" in capsys.readouterr().err


def test_el_perfil_vigente_es_espana_en_euros(ajustes: Ajustes) -> None:
    assert (ajustes.pais, ajustes.divisa) == ("ES", "EUR")


def test_el_broker_es_obligatorio_y_se_conserva_al_leer(
    ajustes: Ajustes, crear: Any, tmp_path: Path
) -> None:
    with pytest.raises(ValueError, match="bróker"):
        crear(broker="  ").validar(ajustes)
    ruta = tmp_path / "a.csv"
    anadir(ruta, crear(), ajustes, hoy=HOY)
    assert leer(ruta)[0].broker == "Trade Republic"


def test_una_divisa_distinta_de_la_del_perfil_se_rechaza(ajustes: Ajustes, crear: Any) -> None:
    with pytest.raises(ValueError, match="divisa"):
        crear(divisa="USD").validar(ajustes)


def test_la_linea_de_ordenes_anade_resume_y_rechaza_importes_malos(
    ajustes: Ajustes,
    isin: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(cli, "cargar", lambda: replace(ajustes, registro=tmp_path / "r.csv"))
    assert cli.main(["anadir", "2024-11-01", isin, "300.00", "2.0033", "149.5", "0.50"]) == 0
    assert leer(tmp_path / "r.csv")[0].broker == ajustes.broker_predeterminado
    assert cli.main(["resumen"]) == 0
    assert "aportado: 300.00 EUR" in capsys.readouterr().out
    for malo in ("NaN", "Infinity", "-5", "abc"):
        assert cli.main(["anadir", "2024-11-02", isin, malo, "2.0033", "149.5", "0.50"]) == 2
    assert len(leer(tmp_path / "r.csv")) == 1
