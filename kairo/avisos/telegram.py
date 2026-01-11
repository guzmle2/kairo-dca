"""Envío de mensajes de salida por la API oficial de bots de Telegram (sin comandos ni TOTP).

El token y el identificador del chat salen de variables de entorno (R7) y nunca se escriben en
mensajes de error ni en logs. Telegram no cifra por defecto los chats con bots: sin secretos.
"""

import json
import os
import urllib.error
import urllib.request
from collections.abc import Callable
from typing import Any

URL = "https://api.telegram.org/bot{token}/sendMessage"
URL_CHAT = "https://api.telegram.org/bot{token}/getChat?chat_id={chat}"
TIEMPO_ESPERA_S = 30
LONGITUD_MAXIMA = 4096


class EnvioError(RuntimeError):
    """Fallo al enviar; su texto nunca incluye el token."""


def credenciales(token_var: str, chat_var: str) -> tuple[str, str]:
    token, chat = os.environ.get(token_var, ""), os.environ.get(chat_var, "")
    if not token or not chat:
        raise EnvioError(f"faltan las variables de entorno {token_var} y {chat_var}")
    return token, chat


def verificar_chat(
    token: str, chat: str, abrir: Callable[..., Any] = urllib.request.urlopen
) -> None:
    """Comprueba con getChat que el destino es un chat privado y que coincide con el configurado."""
    if not chat.lstrip("-").isdigit() or chat.startswith("-"):
        raise EnvioError("el identificador del chat debe ser un número positivo (chat privado)")
    peticion = urllib.request.Request(URL_CHAT.format(token=token, chat=chat))  # noqa: S310
    try:
        with abrir(peticion, timeout=TIEMPO_ESPERA_S) as respuesta:
            datos = json.loads(respuesta.read())
    except (urllib.error.URLError, TimeoutError, ValueError) as error:
        raise EnvioError(f"no se pudo verificar el chat ({type(error).__name__})") from None
    resultado = datos.get("result") or {}
    if (
        not datos.get("ok")
        or resultado.get("type") != "private"
        or str(resultado.get("id")) != chat
    ):
        raise EnvioError("el chat configurado no es un chat privado con el identificador esperado")


def enviar(
    texto: str,
    token: str,
    chat: str,
    abrir: Callable[..., Any] = urllib.request.urlopen,
) -> None:
    if len(texto) > LONGITUD_MAXIMA:
        raise EnvioError("el mensaje supera el máximo de Telegram")
    cuerpo = json.dumps({"chat_id": chat, "text": texto}).encode("utf-8")
    peticion = urllib.request.Request(  # noqa: S310
        URL.format(token=token), data=cuerpo, headers={"Content-Type": "application/json"}
    )
    try:
        with abrir(peticion, timeout=TIEMPO_ESPERA_S) as respuesta:
            datos = json.loads(respuesta.read())
    except (urllib.error.URLError, TimeoutError, ValueError) as error:
        raise EnvioError(f"no se pudo enviar el mensaje ({type(error).__name__})") from None
    if not datos.get("ok"):
        raise EnvioError("Telegram rechazó el mensaje")
