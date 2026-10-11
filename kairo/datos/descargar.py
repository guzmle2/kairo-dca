"""Descarga las fuentes de ``config/datos.json`` y escribe ``datos/manifiesto.json`` con sus hashes.

Uso: ``python -m kairo.datos.descargar [id ...] [--forzar] [--comprobar]``. No sobrescribe un
fichero cuyo hash ya figure en el manifiesto sin ``--forzar``: las pruebas preregistradas dependen
de que los datos no cambien. El hash detecta cambios posteriores; no autentica la primera descarga,
por eso el manifiesto se versiona y cada ``--forzar`` se revisa en el diff.
"""

import argparse
import hashlib
import io
import json
import os
import sys
import urllib.request
import zipfile
from pathlib import Path
from typing import Any, BinaryIO

from kairo.rutas import CONFIG as CARPETA_CONFIG
from kairo.rutas import DATOS, leer_json

CONFIG = CARPETA_CONFIG / "datos.json"
MANIFIESTO = DATOS / "manifiesto.json"
TROZO_BYTES = 65536
PREFIJO_SEGURO = "https://"


def leer_limitado(flujo: BinaryIO, max_bytes: int) -> bytes:
    """Lee el flujo completo y falla si supera el máximo (defensa frente a respuestas gigantes)."""
    datos = flujo.read(max_bytes + 1)
    if len(datos) > max_bytes:
        raise ValueError(f"la descarga supera el máximo de {max_bytes} bytes")
    return datos


def leer(url: str, d: dict[str, Any]) -> bytes:
    if not url.startswith(PREFIJO_SEGURO):
        raise ValueError(f"solo se admiten URL https: {url}")
    peticion = urllib.request.Request(url, headers={"User-Agent": d["agente"]})  # noqa: S310
    with urllib.request.urlopen(peticion, timeout=d["tiempo_espera_s"]) as r:  # noqa: S310
        return leer_limitado(r, d["max_bytes"])


def descomprimir(contenido: bytes, url: str, max_bytes: int) -> bytes:
    """Si la fuente es un zip con un solo fichero, devuelve su contenido (con tope de tamaño)."""
    if not url.endswith(".zip"):
        return contenido
    with zipfile.ZipFile(io.BytesIO(contenido)) as z:
        entradas = z.infolist()
        if len(entradas) != 1:
            raise ValueError(f"se esperaba un fichero en el zip: {[e.filename for e in entradas]}")
        if entradas[0].file_size > max_bytes:
            raise ValueError("el fichero del zip supera el máximo permitido")
        return z.read(entradas[0])


def huella(contenido: bytes) -> str:
    return hashlib.sha256(contenido).hexdigest()


def escribir_atomico(ruta: Path, contenido: bytes) -> None:
    """Escribe en un temporal y lo renombra: una interrupción no deja un fichero a medias."""
    temporal = ruta.with_suffix(ruta.suffix + ".tmp")
    temporal.write_bytes(contenido)
    os.replace(temporal, ruta)


def leer_manifiesto() -> dict[str, Any]:
    manifiesto: dict[str, Any] = leer_json(MANIFIESTO) if MANIFIESTO.exists() else {}
    return manifiesto


def descargar(cfg: dict[str, Any], ids: list[str], forzar: bool) -> dict[str, Any]:
    DATOS.mkdir(exist_ok=True)
    manifiesto = leer_manifiesto()
    d = cfg["descarga"]
    for nombre in ids or list(cfg["fuentes"]):
        fuente = cfg["fuentes"][nombre]
        fichero = DATOS / fuente["fichero"]
        if fichero.exists() and nombre in manifiesto and not forzar:
            continue
        contenido = descomprimir(leer(fuente["url"], d), fuente["url"], d["max_bytes"])
        nueva = huella(contenido)
        previa = manifiesto.get(nombre, {}).get("sha256")
        if previa and previa != nueva and not forzar:
            raise ValueError(
                f"{nombre} ha cambiado respecto al manifiesto: usa --forzar si es intencionado"
            )
        escribir_atomico(fichero, contenido)
        manifiesto[nombre] = {
            "fichero": fuente["fichero"],
            "sha256": nueva,
            "bytes": len(contenido),
        }
    escribir_atomico(
        MANIFIESTO, (json.dumps(manifiesto, indent=1, ensure_ascii=False) + "\n").encode()
    )
    return manifiesto


def comprobar() -> list[str]:
    """Nombres de fuentes cuyo fichero falta o no coincide con el manifiesto."""
    return [
        nombre
        for nombre, datos in leer_manifiesto().items()
        if not (DATOS / datos["fichero"]).exists()
        or huella((DATOS / datos["fichero"]).read_bytes()) != datos["sha256"]
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("fuentes", nargs="*")
    parser.add_argument("--forzar", action="store_true")
    parser.add_argument("--comprobar", action="store_true")
    args = parser.parse_args(argv)
    cfg = leer_json(CONFIG)
    if args.comprobar:
        fallos = comprobar()
        sys.stdout.write(
            f"fuentes con fallo: {fallos}\n" if fallos else "datos coinciden con el manifiesto\n"
        )
        return 1 if fallos else 0
    manifiesto = descargar(cfg, args.fuentes, args.forzar)
    sys.stdout.write(
        "".join(f"{n}: {d['bytes']} bytes {d['sha256'][:12]}\n" for n, d in manifiesto.items())
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
