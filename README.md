# kairo-dca

Boring, honest ETF dollar-cost averaging. A small Python toolkit for people who invest a fixed amount every month into one global accumulating ETF and want discipline, not predictions.

> **Not financial advice.** Educational and personal-use software. Nothing here sends orders, holds credentials or moves money.

## Why it exists

The project started as a trading bot. Every strategy tested under **preregistered criteria** (written and committed *before* running) failed to beat buy-and-hold after costs and taxes, including a 10-month moving-average trend filter with volatility targeting (5 of 12 rules passed). The honest product is the baseline: buy the same global ETF every month, record it, and get alerted when something needs attention. This repo keeps that tool and the validation method that killed the alternatives.

Realistic expectations: global equities returned about 5.4 % a year in EUR over 2001-2026 with a 49 % maximum drawdown. 100 EUR a month for 30 years at 6 % is roughly 100,000 EUR. There is no shortcut here, and the docs say so.

## What is inside

| Module | What it does |
|---|---|
| `kairo.aportaciones` | Append-only contribution ledger (CSV, `Decimal` money, file mode 600) with summary: total contributed, fees, units, average cost, missed months |
| `kairo.avisos` | Telegram alert mode, outbound only, fixed rules in `config/`: monthly reminder, missing-record notice, "just keep contributing" alert on drops by 90/365-day window, stale-data and calendar catch-up alerts, optional planned-withdrawal rule |
| `kairo.validation` | Sharpe, CAGR, max drawdown, block bootstrap, Deflated Sharpe Ratio, equal-volatility comparator, and the preregistered trend-filter test as a worked example |
| `kairo.datos` | Public-series downloader with a hash manifest, so results are reproducible |
| `config/perfil_<country>.json` | Country as a *setting*: currency, allowed ISINs, cost limits, broker candidates. Spain is active; Germany, US and Mexico are drafts (see `document/perfiles/`, written in Spanish) |

Design rules: no hardcoded business values, money as `Decimal`, secrets only via environment variables, dry-run by default.

## Engineering notes

- Python 3.12, fully typed (`mypy` strict), `ruff`, 90+ unit and property-based tests (`hypothesis`).
- Money is `Decimal` end to end; the ledger is append-only with atomic writes and restrictive file permissions.
- Business values live in `config/*.json`; the code holds only hard ceilings. Brokers and countries are configuration, not code.
- Alert rules are pure functions over (prices, date, state), so every rule is tested without network or clock.
- Experiments follow a preregistration discipline: criteria are committed before the run, every trial counts toward the Deflated Sharpe Ratio, and the hold-out stays sealed until the design passes.

## Quick start

```bash
uv sync
uv run pytest -q
uv run python -m kairo.aportaciones anadir 2026-11-01 IE00B4L5Y983 100.00 0.6667 150.00 0.00
uv run python -m kairo.aportaciones resumen
uv run python -m kairo.avisos            # dry run: prints the alerts, sends nothing
```

Telegram: create a bot with BotFather and set `KAIRO_TELEGRAM_BOT_TOKEN` and `KAIRO_TELEGRAM_OPERATOR_ID`; add `--enviar` to send. The tool checks that the chat is private before sending.

## Status and limits

- Code, identifiers and country notes are in Spanish; English translation of identifiers is welcome as a pull request.
- Market data (MSCI, Fama-French, ECB, Bundesbank) is downloaded by `kairo.datos.descargar` and is not redistributed here; check each provider's terms.
- Country profiles other than Spain are drafts that need verification with a local tax adviser.

## License

MIT, see `LICENSE`.
