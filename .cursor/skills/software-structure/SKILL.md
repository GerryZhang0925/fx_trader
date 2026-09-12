---
name: software-structure
description: >-
  Layered layout for the fx_trader research kit. Use when adding modules,
  JSON reports, webhooks, metrics, or refactoring app/ in this project.
paths: "fx_trader/app/**/*.py,fx_trader/app/**/*.yaml"
---

# Software structure (fx_trader)

Keep a thin pipeline. Do not turn this kit into a trading web app or a broker client.

## Layers

The top-level app calls modules in order. Modules do not import each other (backtest CLIs may compose them).

1. **App** — `app/run.py` orchestrates feed → strategy → account → output.
2. **Feed** — `app/feed/` downloads and resamples OHLCV into kit `data/`.
3. **Strategy** — `app/strategy/` writes `signal` / `stop_dist`. No lots.
4. **Account** — `app/account/` estimated fill + size (`propose`) and next-bar PnL (`engine`).
5. **Output** — `app/output/` console, JSON, Telegram Bot API, local HTML on 127.0.0.1. No orders.
6. **Contracts** — `app/contracts.py` documents dict shapes.

Each module has `README.md`, `config.yaml`, `tests/`, and a `backtest/` folder. PnL research lives in `account/backtest` and strategy grids in `strategy/backtest`.

Compatibility shims under `python/` re-export the new packages.

## Rules

- Add fields to `Metrics` rather than ad-hoc dicts in each runner.
- JSON reports use envelope `id`, `type`, `api_version`, `time`, `data`.
- Webhooks and Telegram are outbound. A local read-only HTML page is allowed; do not add login, order tickets, or a public server.
- Secrets only via env (`FX_TRADER_WEBHOOK_SECRET`, `TELEGRAM_BOT_TOKEN`); never commit them.
- Tests cover formulas and rendering, not live URLs.
