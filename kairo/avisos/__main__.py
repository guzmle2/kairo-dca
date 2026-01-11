"""Uso: ``python -m kairo.avisos [--hoy AAAA-MM-DD] [--valor-broker X] [--enviar]``.

Sin ``--enviar`` solo muestra los avisos y no cambia el estado: es un ensayo. Los textos no llevan
importes ni capital (Telegram no cifra por defecto los chats con bots).
"""

import argparse
import json
import os
import sys
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

from kairo.aportaciones.ajustes import cargar
from kairo.aportaciones.registro import leer
from kairo.avisos import telegram
from kairo.avisos.ajustes import Avisos, cargar_avisos
from kairo.avisos.precios import leer_precios
from kairo.avisos.reglas import (
    Aviso,
    Estado,
    dias_sin_datos,
    evaluar_calendario,
    evaluar_precios,
    fuente_dudosa,
    hasta,
)

CODIGO_ERROR = 2
CLAVE_ULTIMA = "ultima_ejecucion"
PERMISOS_FICHERO = 0o600
PERMISOS_DIRECTORIO = 0o700


def leer_estado_texto(texto: str) -> Estado:
    try:
        return dict(json.loads(texto))
    except (ValueError, TypeError) as error:
        raise ValueError("el fichero de estado está corrupto: bórralo para rearmar") from error


def leer_estado(ruta: Path) -> Estado:
    return leer_estado_texto(ruta.read_text(encoding="utf-8")) if ruta.exists() else {}


def escribir_estado(ruta: Path, estado: Estado) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True, mode=PERMISOS_DIRECTORIO)
    temporal = ruta.with_suffix(".tmp")
    descriptor = os.open(temporal, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, PERMISOS_FICHERO)
    with os.fdopen(descriptor, "w", encoding="utf-8") as f:
        f.write(json.dumps(estado, indent=1))
    temporal.replace(ruta)


def dias_del_calendario(hoy: date, estado: Estado, cfg: Avisos) -> list[date]:
    """Días a evaluar: el de hoy y los que se perdieron desde la última ejecución (con tope)."""
    if CLAVE_ULTIMA not in estado:
        return [hoy]
    ultima = date.fromisoformat(estado[CLAVE_ULTIMA])
    atraso = min((hoy - ultima).days, cfg.dias_atraso_max)
    return [hoy - timedelta(days=i) for i in range(atraso - 1, -1, -1)] or [hoy]


def calcular(hoy: date, valor_broker: Decimal | None, cfg: Avisos) -> tuple[list[Aviso], Estado]:
    perfil = cargar()
    filas = leer(perfil.registro)
    previo = leer_estado(cfg.estado)
    precios = hasta(leer_precios(cfg.precios), hoy)
    avisos, estado = evaluar_precios(precios, hoy, previo, cfg)
    sin_datos = dias_sin_datos(precios, hoy)
    fresco = sin_datos is not None and sin_datos <= cfg.dias_sin_datos_max
    unidades = sum((f.unidades for f in filas), Decimal(0))
    capital = unidades * precios[-1][1] if fresco else None
    for dia in dias_del_calendario(hoy, previo, cfg):
        avisos += evaluar_calendario(dia, filas, capital, perfil.instrumento_predeterminado, cfg)
    if CLAVE_ULTIMA in previo:
        parado = (hoy - date.fromisoformat(previo[CLAVE_ULTIMA])).days
        if parado > 1:
            avisos.append(
                Aviso("proceso_parado", cfg.mensajes["proceso_parado"].format(dias=parado))
            )
    if (
        valor_broker is not None
        and capital is not None
        and (dudoso := fuente_dudosa(capital, valor_broker, cfg))
    ):
        avisos.append(dudoso)
    estado[CLAVE_ULTIMA] = hoy.isoformat()
    return avisos, estado


def valor_positivo(texto: str) -> Decimal:
    valor = Decimal(texto)
    if not valor.is_finite() or valor <= 0:
        raise argparse.ArgumentTypeError("el valor debe ser un número finito y positivo")
    return valor


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--hoy", type=date.fromisoformat, default=None)
    p.add_argument("--valor-broker", type=valor_positivo, default=None)
    p.add_argument("--enviar", action="store_true")
    args = p.parse_args(argv)
    cfg = cargar_avisos()
    try:
        avisos, estado = calcular(args.hoy or date.today(), args.valor_broker, cfg)
        texto = "\n".join(a.texto for a in avisos) + "\n\n" + cfg.mensajes["aviso_fijo"]
        if avisos:
            sys.stdout.write(texto + "\n")
        else:
            sys.stdout.write("sin avisos\n")
        if args.enviar:
            if avisos:
                token, chat = telegram.credenciales(cfg.variable_token, cfg.variable_chat)
                telegram.verificar_chat(token, chat)
                telegram.enviar(texto, token, chat)
            escribir_estado(cfg.estado, estado)
    except (ValueError, telegram.EnvioError) as error:
        sys.stderr.write(f"error: {error}\n")
        return CODIGO_ERROR
    return 0


if __name__ == "__main__":
    sys.exit(main())
