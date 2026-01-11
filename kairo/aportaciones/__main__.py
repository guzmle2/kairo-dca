"""Línea de órdenes: ``python -m kairo.aportaciones anadir|resumen``."""

import argparse
import sys
from datetime import date
from decimal import Decimal

from kairo.aportaciones.ajustes import ESTADO_ACTIVO, cargar
from kairo.aportaciones.registro import (
    CAMPOS_DECIMALES,
    Aportacion,
    anadir,
    decimal_finito,
    leer,
    meses_sin_aportacion,
    racha_de_meses,
)
from kairo.constantes import PORCENTAJE

CODIGO_ERROR = 2


def resumen(filas: list[Aportacion], hoy: date) -> str:
    if not filas:
        return "sin aportaciones registradas\n"
    importe = sum((f.importe for f in filas), Decimal(0))
    comision = sum((f.comision for f in filas), Decimal(0))
    unidades = sum((f.unidades for f in filas), Decimal(0))
    huecos = ", ".join(f"{a}-{m:02d}" for a, m in meses_sin_aportacion(filas, hoy)) or "ninguno"
    if importe <= 0 or unidades <= 0:
        return f"aportaciones: {len(filas)}\nimporte o unidades netos no positivos: revisa\n"
    return (
        f"aportaciones: {len(filas)}\naportado: {importe:.2f} EUR\n"
        f"comisiones: {comision:.2f} EUR ({comision / importe * PORCENTAJE:.2f} % del aportado)\n"
        f"unidades: {unidades}\ncoste medio por unidad: {importe / unidades:.4f} EUR\n"
        f"meses seguidos aportando: {racha_de_meses(filas, hoy)}\n"
        f"meses sin aportación: {huecos}\n"
    )


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="orden", required=True)
    nueva = sub.add_parser("anadir")
    nueva.add_argument("fecha", type=date.fromisoformat)
    nueva.add_argument("isin")
    for campo in CAMPOS_DECIMALES:
        nueva.add_argument(campo)
    nueva.add_argument("--broker", help="cuenta del lote; por defecto el bróker del perfil")
    sub.add_parser("resumen")
    args = p.parse_args(argv)
    ajustes = cargar()
    if ajustes.estado != ESTADO_ACTIVO:
        sys.stderr.write(
            f"AVISO: el perfil {ajustes.pais} está en {ajustes.estado}: datos sin verificar\n"
        )
    try:
        if args.orden == "anadir":
            aportacion = Aportacion(
                args.fecha,
                args.isin.strip(),
                importe=decimal_finito(args.importe, "importe"),
                unidades=decimal_finito(args.unidades, "unidades"),
                precio=decimal_finito(args.precio, "precio"),
                comision=decimal_finito(args.comision, "comision"),
                divisa=ajustes.divisa,
                broker=args.broker or ajustes.broker_predeterminado,
            )
            avisos = anadir(ajustes.registro, aportacion, ajustes)
            sys.stdout.write("".join(f"AVISO: {x}\n" for x in avisos) or "añadida\n")
        else:
            sys.stdout.write(resumen(leer(ajustes.registro), date.today()))
    except ValueError as error:
        sys.stderr.write(f"error: {error}\n")
        return CODIGO_ERROR
    return 0


if __name__ == "__main__":
    sys.exit(main())
