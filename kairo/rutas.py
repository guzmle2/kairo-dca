"""Rutas del proyecto: un único punto de verdad para la raíz y la carpeta de configuración."""

import json
from pathlib import Path
from typing import Any

RAIZ = Path(__file__).resolve().parents[1]
CONFIG = RAIZ / "config"
DATOS = RAIZ / "datos"


def leer_json(ruta: Path) -> Any:
    return json.loads(ruta.read_text(encoding="utf-8"))
