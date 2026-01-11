"""Serie de precios diarios del fondo en un CSV (fecha, precio) que escribe cualquier fuente."""

import csv
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

Serie = list[tuple[date, Decimal]]


def leer_precios(ruta: Path) -> Serie:
    """Precios ordenados por fecha; un fichero ausente es una serie vacía."""
    if not ruta.exists():
        return []
    with ruta.open(newline="", encoding="utf-8") as f:
        try:
            filas = [
                (date.fromisoformat(r["fecha"]), Decimal(r["precio"])) for r in csv.DictReader(f)
            ]
        except (KeyError, ValueError, InvalidOperation) as error:
            raise ValueError(f"fichero de precios corrupto: {ruta}") from error
    if any(not p.is_finite() or p <= 0 for _, p in filas):
        raise ValueError("los precios deben ser números finitos y positivos")
    return sorted(filas)
