"""Registro de aportaciones en CSV de solo añadir, con importes en ``Decimal`` (R8).

El fichero vive fuera de git (contiene datos financieros personales). Nunca se reescribe una fila:
una corrección se anota como una fila nueva.
"""

import csv
import os
from dataclasses import dataclass, fields
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

from kairo.aportaciones.ajustes import Ajustes
from kairo.constantes import MESES_ANIO, PORCENTAJE

PERMISOS_DIRECTORIO = 0o700
PERMISOS_FICHERO = 0o600
DIVISA_PREDETERMINADA = "EUR"
CAMPOS_DECIMALES = ("importe", "unidades", "precio", "comision")


def decimal_finito(texto: str, campo: str) -> Decimal:
    try:
        valor = Decimal(texto)
    except InvalidOperation as error:
        raise ValueError(f"{campo} no es un número: {texto!r}") from error
    if not valor.is_finite():
        raise ValueError(f"{campo} debe ser un número finito")
    return valor


@dataclass(frozen=True)
class Aportacion:
    fecha: date
    isin: str
    importe: Decimal  # total cargado, comisión incluida
    unidades: Decimal
    precio: Decimal
    comision: Decimal
    divisa: str = DIVISA_PREDETERMINADA
    broker: str = ""  # cuenta en la que está el lote, para reconstruir el coste ante una mudanza

    def validar(self, a: Ajustes) -> None:
        if self.isin not in a.isin_permitidos:
            raise ValueError(f"instrumento fuera de la lista cerrada del perfil: {self.isin!r}")
        if not self.broker.strip():
            raise ValueError("el bróker de la cuenta es obligatorio")
        if self.divisa != a.divisa:
            raise ValueError(f"divisa {self.divisa!r} distinta de la del perfil {a.divisa!r}")
        if not all(getattr(self, c).is_finite() for c in CAMPOS_DECIMALES):
            raise ValueError("importe, unidades, precio y comisión deben ser números finitos")
        if min(self.importe, self.unidades, self.precio) <= 0 or self.comision < 0:
            raise ValueError(
                "importe, unidades y precio deben ser positivos y la comisión no negativa"
            )
        holgura = a.tolerancia_unidades * self.precio + a.tolerancia_importe
        if abs(self.importe - self.comision - self.unidades * self.precio) > holgura:
            raise ValueError("importe, unidades, precio y comisión no cuadran")

    def avisos(self, a: Ajustes, hoy: date) -> list[str]:
        avisos = []
        maxima = self.importe * a.comision_max_por_aportacion_pct / PORCENTAJE
        if self.comision > maxima:
            avisos.append(f"comisión {self.comision} EUR por encima del máximo ({maxima:.2f} EUR)")
        if self.fecha > hoy:
            avisos.append(f"fecha futura: {self.fecha}")
        return avisos

    def fila(self) -> dict[str, str]:
        return {c.name: str(getattr(self, c.name)) for c in fields(self)}


CAMPOS = tuple(c.name for c in fields(Aportacion))


def desde_fila(fila: dict[str, str]) -> Aportacion:
    try:
        return Aportacion(
            fecha=date.fromisoformat(fila["fecha"]),
            isin=fila["isin"].strip(),
            divisa=fila.get("divisa", DIVISA_PREDETERMINADA).strip(),
            broker=fila.get("broker", "").strip(),
            **{c: decimal_finito(fila[c], c) for c in CAMPOS_DECIMALES},
        )
    except (KeyError, TypeError) as error:
        raise ValueError(f"fila del CSV incompleta o corrupta: {fila!r}") from error


def leer(ruta: Path) -> list[Aportacion]:
    """Filas del CSV; un fichero ausente es un registro vacío."""
    if not ruta.exists():
        return []
    with ruta.open(newline="", encoding="utf-8") as f:
        return [desde_fila(fila) for fila in csv.DictReader(f)]


def anadir(ruta: Path, aportacion: Aportacion, a: Ajustes, hoy: date | None = None) -> list[str]:
    """Valida y añade una fila al final; devuelve los avisos (no bloquean un hecho ya ocurrido)."""
    aportacion.validar(a)
    avisos = aportacion.avisos(a, hoy or date.today())
    if aportacion in leer(ruta):
        avisos.append("posible duplicado: ya existe una fila idéntica")
    ruta.parent.mkdir(parents=True, exist_ok=True, mode=PERMISOS_DIRECTORIO)
    nuevo = not ruta.exists() or ruta.stat().st_size == 0
    with ruta.open("a", newline="", encoding="utf-8") as f:
        os.fchmod(f.fileno(), PERMISOS_FICHERO)
        escritor = csv.DictWriter(f, fieldnames=CAMPOS)
        if nuevo:
            escritor.writeheader()
        escritor.writerow(aportacion.fila())
    return avisos


def racha_de_meses(filas: list[Aportacion], hoy: date) -> int:
    """Meses seguidos con aportación hasta el mes en curso (o el anterior si aún no la hay)."""
    con_datos = {f.fecha.year * MESES_ANIO + f.fecha.month - 1 for f in filas}
    mes = hoy.year * MESES_ANIO + hoy.month - 1
    mes = mes if mes in con_datos else mes - 1
    racha = 0
    while mes in con_datos:
        racha, mes = racha + 1, mes - 1
    return racha


def meses_sin_aportacion(filas: list[Aportacion], hoy: date) -> list[tuple[int, int]]:
    """Meses naturales entre la primera aportación y el mes anterior a ``hoy`` sin ninguna fila."""
    if not filas:
        return []
    con_datos = {(f.fecha.year, f.fecha.month) for f in filas}
    primero = min(con_datos)
    ultimo = hoy.year * MESES_ANIO + hoy.month - 2
    desde = primero[0] * MESES_ANIO + primero[1] - 1
    meses = [(i // MESES_ANIO, i % MESES_ANIO + 1) for i in range(desde, ultimo + 1)]
    return [m for m in meses if m not in con_datos]
