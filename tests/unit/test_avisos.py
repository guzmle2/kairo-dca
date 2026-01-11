"""Modo avisador: caídas, re-avisos, máximos, datos que faltan, calendario y retiradas."""

import io
import json
import urllib.error
from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from hypothesis import given
from hypothesis import strategies as st
from kairo.aportaciones.ajustes import Ajustes
from kairo.avisos import __main__ as cli
from kairo.avisos import telegram
from kairo.avisos.ajustes import Avisos, Retiradas, cargar_avisos, cargar_retiradas
from kairo.avisos.precios import Serie, leer_precios
from kairo.avisos.reglas import (
    caida_pct,
    dias_sin_datos,
    evaluar_calendario,
    evaluar_precios,
    fuente_dudosa,
    nivel,
)
from kairo.avisos.retiradas import retirada_aplica, retirada_mensual

CFG = cargar_avisos()
HOY = date(2025, 6, 30)


def serie(*precios: str, fin: date = HOY) -> Serie:
    """Un precio por día terminando en ``fin``."""
    n = len(precios)
    return [(fin - timedelta(days=n - 1 - i), Decimal(p)) for i, p in enumerate(precios)]


def larga(*cola: str, base: str = "100", dias: int = 400, fin: date = HOY) -> Serie:
    """Un historial plano de ``dias`` días a ``base`` seguido de los precios de ``cola``."""
    n = len(cola)
    plano = [(fin - timedelta(days=n + dias - i), Decimal(base)) for i in range(dias)]
    return plano + serie(*cola, fin=fin)


def test_la_configuracion_cumple_los_valores_del_dueno() -> None:
    assert CFG.ventanas_dias == (90, 365)
    assert (CFG.umbral_caida_pct, CFG.reaviso_cada_puntos) == (Decimal(30), Decimal(10))
    assert CFG.dias_sin_datos_max == 3
    assert all(isinstance(v, Decimal) for v in (CFG.aportacion_mensual, CFG.capital_70_30))


def test_la_caida_se_mide_frente_al_maximo_de_la_ventana() -> None:
    precios = serie("100", "80", "70")
    assert caida_pct(precios, HOY, 90) == Decimal(30)
    assert caida_pct([], HOY, 90) is None


def test_el_maximo_fuera_de_la_ventana_no_cuenta() -> None:
    antiguo = [(HOY - timedelta(days=200), Decimal(200))]
    reciente = serie("100", "95")
    assert caida_pct(antiguo + reciente, HOY, 90) == Decimal(5)
    assert caida_pct(antiguo + reciente, HOY, 365) == Decimal("52.5")


def test_el_nivel_es_el_multiplo_inferior() -> None:
    assert nivel(Decimal("33"), Decimal(10)) == Decimal(30)
    assert nivel(Decimal("49.9"), Decimal(10)) == Decimal(40)


def test_cae_un_30_por_ciento_y_avisa_una_vez_con_el_texto_fijo() -> None:
    precios = larga("69")
    avisos, estado = evaluar_precios(precios, HOY, {}, CFG)
    assert [a.tipo for a in avisos] == ["caida", "caida"]  # las dos ventanas
    assert "Solo seguir aportando" in avisos[0].texto
    assert "vender" not in avisos[0].texto.replace("ni para", "")
    de_nuevo, _ = evaluar_precios(precios, HOY, estado, CFG)
    assert de_nuevo == []


def test_vuelve_a_avisar_cada_diez_puntos_mas_y_se_rearma_al_recuperar() -> None:
    _, estado = evaluar_precios(larga("69"), HOY, {}, CFG)
    mas, estado = evaluar_precios(larga("59"), HOY, estado, CFG)
    assert [a.tipo for a in mas] == ["caida", "caida"]
    _, estado = evaluar_precios(larga("95"), HOY, estado, CFG)
    assert estado["nivel_90"] == "0"
    otra, _ = evaluar_precios(larga("69"), HOY, estado, CFG)
    assert len(otra) == 2


def test_una_caida_menor_al_umbral_no_avisa() -> None:
    avisos, _ = evaluar_precios(larga("75"), HOY, {}, CFG)
    assert avisos == []


def test_nuevo_maximo_es_informativo_y_no_se_repite() -> None:
    precios = larga("105", base="90")
    avisos, estado = evaluar_precios(precios, HOY, {}, CFG)
    assert {a.tipo for a in avisos} == {"nuevo_maximo"}
    assert "no es motivo para vender" in avisos[0].texto
    otra, _ = evaluar_precios(precios, HOY, estado, CFG)
    assert otra == []


def test_sin_precios_recientes_solo_avisa_de_que_faltan_datos_y_no_de_caidas() -> None:
    viejos = serie("100", "50", fin=HOY - timedelta(days=5))
    avisos, estado = evaluar_precios(viejos, HOY, {}, CFG)
    assert [a.tipo for a in avisos] == ["sin_datos"]
    assert estado == {}
    vacios, _ = evaluar_precios([], HOY, {}, CFG)
    assert vacios[0].tipo == "sin_datos"
    assert dias_sin_datos(viejos, HOY) == 5


def test_un_dia_sin_datos_dentro_del_margen_si_evalua() -> None:
    avisos, _ = evaluar_precios(larga("60", fin=HOY - timedelta(days=3)), HOY, {}, CFG)
    assert next(a.tipo for a in avisos) == "caida"


def aportacion_de(crear: Any, fecha: date) -> Any:
    return crear(fecha=fecha)


def test_el_dia_5_recuerda_la_aportacion_y_el_12_avisa_si_falta_el_registro(crear: Any) -> None:
    filas = [crear(fecha=date(2025, 4, 5)), crear(fecha=date(2025, 5, 5))]
    dia5 = evaluar_calendario(date(2025, 6, 5), filas, None, "IE00B4L5Y983", CFG)
    assert [a.tipo for a in dia5] == ["recordatorio"]
    assert "IE00B4L5Y983" in dia5[0].texto
    assert "EUR" not in dia5[0].texto
    dia12 = evaluar_calendario(date(2025, 6, 12), filas, None, "IE00B4L5Y983", CFG)
    assert [a.tipo for a in dia12] == ["falta_registro"]
    con_junio = [*filas, crear(fecha=date(2025, 6, 5))]
    assert evaluar_calendario(date(2025, 6, 12), con_junio, None, "IE00B4L5Y983", CFG) == []
    assert evaluar_calendario(date(2025, 6, 20), filas, None, "IE00B4L5Y983", CFG) == []


def test_las_revisiones_por_capital_y_por_aportacion(crear: Any) -> None:
    dia5 = date(2025, 6, 5)
    nada = evaluar_calendario(dia5, [], Decimal(5000), "X", CFG)
    assert [a.tipo for a in nada] == ["recordatorio"]
    setenta = evaluar_calendario(dia5, [], Decimal(10000), "X", CFG)
    assert "revision_70_30" in {a.tipo for a in setenta}
    nivel_b = evaluar_calendario(dia5, [], Decimal(20000), "X", CFG)
    assert {"revision_70_30", "revision_nivel_b"} <= {a.tipo for a in nivel_b}
    grande = replace(CFG, aportacion_mensual=Decimal(1000))
    assert "revision_nivel_b" in {a.tipo for a in evaluar_calendario(dia5, [], None, "X", grande)}


def test_fuente_dudosa_si_difiere_mas_del_uno_por_ciento() -> None:
    assert fuente_dudosa(Decimal("100"), Decimal("100.5"), CFG) is None
    assert fuente_dudosa(Decimal("100"), Decimal("103"), CFG) is not None
    assert fuente_dudosa(Decimal("100"), Decimal(0), CFG) is None


@given(st.lists(st.decimals(min_value="1", max_value="1000", places=2), min_size=2, max_size=40))
def test_la_caida_esta_siempre_entre_cero_y_cien(precios: list[Decimal]) -> None:
    datos = [(HOY - timedelta(days=len(precios) - 1 - i), p) for i, p in enumerate(precios)]
    caida = caida_pct(datos, HOY, 90)
    assert caida is not None
    assert 0 <= caida < 100


def test_los_precios_se_leen_en_orden_y_un_fichero_corrupto_falla(tmp_path: Path) -> None:
    ruta = tmp_path / "p.csv"
    ruta.write_text("fecha,precio\n2025-01-02,101.5\n2025-01-01,100\n")
    assert [p for _, p in leer_precios(ruta)] == [Decimal(100), Decimal("101.5")]
    ruta.write_text("fecha,precio\n2025-01-01,abc\n")
    with pytest.raises(ValueError, match="corrupto"):
        leer_precios(ruta)
    ruta.write_text("fecha,precio\n2025-01-01,-3\n")
    with pytest.raises(ValueError, match="positivos"):
        leer_precios(ruta)
    assert leer_precios(tmp_path / "no.csv") == []


# ---------- retiradas ----------


def plan(**cambios: Any) -> Retiradas:
    base = replace(
        cargar_retiradas(),
        activada=True,
        capital_objetivo=Decimal(100000),
        fecha_inicio=date(2030, 1, 1),
    )
    return replace(base, **cambios)


def test_las_retiradas_vienen_apagadas_por_defecto() -> None:
    cfg = cargar_retiradas()
    assert cfg.activada is False
    assert retirada_mensual(cfg, date(2040, 1, 1), Decimal(10**6), Decimal(10**6), None) == 0


def test_caso_plan_un_doceavo_del_cuatro_por_ciento_sobre_el_valor_de_enero() -> None:
    importe = retirada_mensual(
        plan(), date(2030, 2, 1), Decimal(120000), Decimal(120000), Decimal(5)
    )
    assert importe == Decimal("400.00")


def test_caso_caida_reduce_la_retirada_a_la_mitad() -> None:
    importe = retirada_mensual(
        plan(), date(2030, 2, 1), Decimal(120000), Decimal(120000), Decimal(35)
    )
    assert importe == Decimal("200.00")


def test_caso_emergencia_no_pasa_por_la_politica_de_plan_y_exige_fecha_y_capital() -> None:
    cfg = plan()
    assert not retirada_aplica(cfg, date(2029, 12, 31), Decimal(120000))
    assert not retirada_aplica(cfg, date(2030, 2, 1), Decimal(99999))
    assert retirada_mensual(cfg, date(2029, 1, 1), Decimal(50000), Decimal(50000), None) == 0


def test_una_retirada_activada_sin_objetivo_ni_fecha_falla(tmp_path: Path) -> None:
    ruta = tmp_path / "r.json"
    texto = (Path(__file__).resolve().parents[2] / "config" / "retiradas.json").read_text()
    ruta.write_text(texto.replace('"activada": false', '"activada": true'))
    with pytest.raises(ValueError, match="necesita"):
        cargar_retiradas(ruta)


# ---------- Telegram ----------


class Respuesta(io.BytesIO):
    def __enter__(self) -> "Respuesta":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


def test_el_envio_usa_https_y_no_filtra_el_token_en_los_errores() -> None:
    vistas: list[Any] = []

    def abrir(peticion: Any, timeout: int) -> Respuesta:
        vistas.append((peticion.full_url, json.loads(peticion.data), timeout))
        return Respuesta(b'{"ok": true}')

    telegram.enviar("hola", "SECRETO", "42", abrir)
    assert vistas[0][0].startswith("https://api.telegram.org/bot")
    assert vistas[0][1] == {"chat_id": "42", "text": "hola"}

    def falla(*_: Any, **__: Any) -> Respuesta:
        raise urllib.error.URLError("fallo con SECRETO")

    with pytest.raises(telegram.EnvioError) as error:
        telegram.enviar("hola", "SECRETO", "42", falla)
    assert "SECRETO" not in str(error.value)

    def rechaza(*_: Any, **__: Any) -> Respuesta:
        return Respuesta(b'{"ok": false}')

    with pytest.raises(telegram.EnvioError, match="rechazó"):
        telegram.enviar("hola", "SECRETO", "42", rechaza)
    with pytest.raises(telegram.EnvioError, match="máximo"):
        telegram.enviar("x" * 5000, "SECRETO", "42", abrir)


def test_las_credenciales_salen_del_entorno_y_su_ausencia_falla(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("T_VAR", raising=False)
    monkeypatch.delenv("C_VAR", raising=False)
    with pytest.raises(telegram.EnvioError, match="variables de entorno"):
        telegram.credenciales("T_VAR", "C_VAR")
    monkeypatch.setenv("T_VAR", "abc")
    monkeypatch.setenv("C_VAR", "7")
    assert telegram.credenciales("T_VAR", "C_VAR") == ("abc", "7")


# ---------- línea de órdenes ----------


def test_el_ensayo_muestra_los_avisos_y_no_cambia_el_estado(
    ajustes: Ajustes,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    precios = tmp_path / "p.csv"
    estado = tmp_path / "e.json"
    largo = "".join(f"{HOY - timedelta(days=i)},100\n" for i in range(400, 0, -1))
    precios.write_text("fecha,precio\n" + largo + f"{HOY},60\n")
    cfg: Avisos = replace(CFG, precios=precios, estado=estado)
    monkeypatch.setattr(cli, "cargar_avisos", lambda: cfg)
    monkeypatch.setattr(cli, "cargar", lambda: replace(ajustes, registro=tmp_path / "r.csv"))
    assert cli.main(["--hoy", "2025-06-30"]) == 0
    salida = capsys.readouterr().out
    assert "Solo seguir aportando" in salida
    assert "Aviso automático de una herramienta personal" in salida
    assert not estado.exists()


def test_con_pocos_datos_no_hay_avisos_de_caida_de_una_ventana_que_no_cubren() -> None:
    corto = serie("100", "60")
    avisos, _ = evaluar_precios(corto, HOY, {}, CFG)
    assert avisos == []


def test_el_nuevo_maximo_no_avisa_a_diario_en_una_tendencia_alcista() -> None:
    base = larga("105", base="90")
    primero, estado = evaluar_precios(base, HOY, {}, CFG)
    assert {a.tipo for a in primero} == {"nuevo_maximo"}
    manana = [*base, (HOY + timedelta(days=1), Decimal(106))]
    segundo, _ = evaluar_precios(manana, HOY + timedelta(days=1), estado, CFG)
    assert segundo == []
    pasada_la_semana = [*base, (HOY + timedelta(days=8), Decimal(107))]
    tercero, _ = evaluar_precios(pasada_la_semana, HOY + timedelta(days=8), estado, CFG)
    assert {a.tipo for a in tercero} == {"nuevo_maximo"}


def test_un_estado_corrupto_falla_con_un_mensaje_claro() -> None:
    with pytest.raises(ValueError, match="corrupto"):
        evaluar_precios(larga("69"), HOY, {"nivel_90": "abc"}, CFG)
    with pytest.raises(ValueError, match="corrupto"):
        cli.leer_estado_texto("{no es json")


def test_los_textos_de_los_avisos_no_llevan_importes_ni_capital(crear: Any) -> None:
    dia5 = evaluar_calendario(date(2025, 6, 5), [], Decimal(25000), "X", CFG)
    texto = " ".join(a.texto for a in dia5)
    assert "25000" not in texto
    assert "EUR" not in texto


def test_el_calendario_atrasado_recupera_los_dias_perdidos(crear: Any) -> None:
    estado = {cli.CLAVE_ULTIMA: "2025-06-03"}
    dias = cli.dias_del_calendario(date(2025, 6, 6), estado, CFG)
    assert dias == [date(2025, 6, 4), date(2025, 6, 5), date(2025, 6, 6)]
    assert cli.dias_del_calendario(date(2025, 6, 6), {}, CFG) == [date(2025, 6, 6)]
    lejos = cli.dias_del_calendario(date(2025, 6, 30), {cli.CLAVE_ULTIMA: "2025-01-01"}, CFG)
    assert len(lejos) == CFG.dias_atraso_max


def test_el_estado_se_guarda_con_permisos_restrictivos(tmp_path: Path) -> None:
    ruta = tmp_path / "nuevo" / "e.json"
    cli.escribir_estado(ruta, {"nivel_90": "0"})
    assert ruta.stat().st_mode & 0o777 == 0o600
    assert ruta.parent.stat().st_mode & 0o777 == 0o700


def test_el_chat_debe_ser_privado_positivo_y_coincidir() -> None:
    def privado(*_: Any, **__: Any) -> Respuesta:
        return Respuesta(b'{"ok": true, "result": {"id": 42, "type": "private"}}')

    telegram.verificar_chat("T", "42", privado)

    def grupo(*_: Any, **__: Any) -> Respuesta:
        return Respuesta(b'{"ok": true, "result": {"id": 42, "type": "group"}}')

    with pytest.raises(telegram.EnvioError, match="chat privado"):
        telegram.verificar_chat("T", "42", grupo)
    with pytest.raises(telegram.EnvioError, match="número positivo"):
        telegram.verificar_chat("T", "-100123", privado)

    def otro(*_: Any, **__: Any) -> Respuesta:
        return Respuesta(b'{"ok": true, "result": {"id": 99, "type": "private"}}')

    with pytest.raises(telegram.EnvioError, match="chat privado"):
        telegram.verificar_chat("T", "42", otro)


def test_la_retirada_nunca_supera_el_valor_y_valida_la_configuracion(tmp_path: Path) -> None:
    importe = retirada_mensual(plan(), date(2030, 2, 1), Decimal(100000), Decimal(10**9), None)
    assert importe == Decimal("100000.00")
    texto = (Path(__file__).resolve().parents[2] / "config" / "retiradas.json").read_text()
    for cambio, error in (
        ('"activada": false', '"activada": "false"'),
        ('"meses": 12', '"meses": 0'),
        ('"factor_en_caida": "0.5"', '"factor_en_caida": "2"'),
    ):
        ruta = tmp_path / "r.json"
        ruta.write_text(texto.replace(cambio, error))
        with pytest.raises(ValueError):
            cargar_retiradas(ruta)
