"""Utilidades compartidas por los tests."""

from dataclasses import replace
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from kairo.aportaciones.ajustes import Ajustes, cargar
from kairo.aportaciones.registro import Aportacion, anadir


@pytest.fixture(scope="session")
def ajustes() -> Ajustes:
    return cargar()


@pytest.fixture
def isin(ajustes: Ajustes) -> str:
    return next(iter(ajustes.isin_permitidos))


@pytest.fixture
def crear(isin: str) -> Any:
    """Fábrica de aportaciones válidas con campos sustituibles."""

    def _crear(**cambios: Any) -> Aportacion:
        base = Aportacion(
            date(2024, 11, 1),
            isin,
            Decimal("300.00"),
            Decimal("2.0033"),
            Decimal("149.5"),
            Decimal("0.50"),
            "EUR",
            "Trade Republic",
        )
        return replace(base, **cambios)

    return _crear


@pytest.fixture
def escribir(ajustes: Ajustes) -> Any:
    def _escribir(ruta: Path, filas: list[Aportacion]) -> Path:
        for f in filas:
            anadir(ruta, f, ajustes, hoy=date(2030, 1, 1))
        return ruta

    return _escribir
