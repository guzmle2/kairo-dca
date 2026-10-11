# kairo-dca

[Read in English](README.md)

Inversión periódica en ETF, aburrida y honesta. Un pequeño conjunto de herramientas en Python para quien invierte una cantidad fija cada mes en un único ETF global de acumulación y quiere disciplina, no predicciones.

> **No es asesoramiento financiero.** Software educativo y de uso personal. Nada de lo que hay aquí envía órdenes, guarda credenciales ni mueve dinero.

## Por qué existe

El proyecto empezó como un bot de trading. Toda estrategia probada con **criterios fijados de antemano** (escritos y guardados *antes* de ejecutar) fue incapaz de superar a comprar y mantener después de costes e impuestos, incluido un filtro de tendencia con media móvil de 10 meses y objetivo de volatilidad (pasó 5 de 12 reglas). El producto honesto es la línea base: comprar cada mes el mismo ETF global, registrarlo y recibir un aviso cuando algo requiere atención. Este repositorio conserva esa herramienta y el método de validación que descartó las alternativas.

Expectativas realistas: la bolsa global rindió alrededor de un 5,4 % anual en euros en 2001-2026, con una caída máxima del 49 %. Aportar 100 € al mes durante 30 años a un 6 % da aproximadamente 100.000 €. No hay atajos, y la documentación lo dice.

## Qué contiene

| Módulo | Qué hace |
|---|---|
| `kairo.aportaciones` | Registro de aportaciones de solo añadir (CSV, dinero en `Decimal`, permisos 600) con resumen: total aportado, comisiones, unidades, coste medio y meses sin aportación |
| `kairo.avisos` | Avisos por Telegram, solo de salida y con reglas fijas en `config/`: recordatorio mensual, aviso de registro que falta, "sigue aportando" ante caídas por ventana de 90 y 365 días, datos que faltan, calendario atrasado y una regla opcional de retirada planificada |
| `kairo.validation` | Sharpe, CAGR, caída máxima, bootstrap por bloques, Deflated Sharpe Ratio, comparador a igual volatilidad y la prueba preregistrada del filtro de tendencia como ejemplo |
| `kairo.datos` | Descarga de series públicas con un manifiesto de hashes para que los resultados se puedan reproducir |
| `config/perfil_<pais>.json` | El país como *ajuste*: moneda, ISIN permitidos, límites de coste y candidatos de bróker. España está activa; Alemania, EE. UU. y México son borradores (ver `document/perfiles/`) |

Reglas de diseño: sin valores de negocio escritos en el código, dinero como `Decimal`, secretos solo por variables de entorno y simulación por defecto.

## Notas de ingeniería

- Python 3.12, tipado completo (`mypy` estricto), `ruff` y más de 90 tests unitarios y de propiedades (`hypothesis`).
- El dinero es `Decimal` de principio a fin; el registro solo permite añadir, con escrituras atómicas y permisos restrictivos.
- Los valores de negocio viven en `config/*.json`; el código solo guarda techos absolutos. Los brókers y los países son configuración, no código.
- Las reglas de aviso son funciones puras sobre (precios, fecha, estado), así que cada regla se prueba sin red ni reloj.
- Los experimentos siguen una disciplina de preregistro: los criterios se guardan antes de ejecutar, toda prueba cuenta para el Deflated Sharpe Ratio y el tramo de hold-out no se abre hasta que el diseño pasa.

## Inicio rápido

```bash
uv sync
uv run pytest -q
uv run python -m kairo.aportaciones anadir 2026-11-01 IE00B4L5Y983 100.00 0.6667 150.00 0.00
uv run python -m kairo.aportaciones resumen
uv run python -m kairo.avisos            # simulación: muestra los avisos, no envía nada
```

Telegram: crea un bot con BotFather y define `KAIRO_TELEGRAM_BOT_TOKEN` y `KAIRO_TELEGRAM_OPERATOR_ID`; añade `--enviar` para enviar. La herramienta comprueba que el chat sea privado antes de enviar.

## Estado y límites

- El código, los identificadores y las notas de país están en español; se agradecen pull requests que traduzcan los identificadores al inglés.
- Los datos de mercado (MSCI, Fama-French, BCE, Bundesbank) los descarga `kairo.datos.descargar` y no se redistribuyen aquí; revisa las condiciones de cada proveedor.
- Los perfiles que no son el de España son borradores que necesitan verificación con un asesor fiscal local.

## Licencia

MIT, ver `LICENSE`.
