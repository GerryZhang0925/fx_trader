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
3. **Strategy** — `app/strategy/` writes `signal` / `stop_dist`. Shared helpers in `strategy/common/`. Adopted cores live in `strategy/cores/<name>/` (README there). No lots.
4. **Account** — `app/account/` estimated fill + size (`propose`) and next-bar PnL (`engine`).
5. **Output** — `app/output/` console, JSON, Telegram Bot API, local HTML on 127.0.0.1. No orders.
6. **Contracts** — `app/contracts.py` documents dict shapes.

Each module has `README.md`, `config.yaml`, `tests/`, and a `backtest/` folder. PnL research lives in `account/backtest`. Per-core grids and overlay evals live in `strategy/cores/<name>/backtest`. Cross-core scripts stay in `strategy/backtest`. CLI scripts there compose layers; they must not reimplement Sharpe or JSON envelopes.

Kit root keeps one launcher: `run.py` (`python run.py` / `python -m app`). Do not put download, optimize, walkforward, or portfolio CLIs next to it — those are `python -m feed.download`, `python -m strategy.backtest` (Donchian optimize), `python -m account.backtest`. Do not revive a `python/` shim tree.

## Rules

- Add fields to `Metrics` rather than ad-hoc dicts in each runner.
- JSON reports use envelope `id`, `type`, `api_version`, `time`, `data`.
- Run status is `reports/status.jsonl` (append-only). `output/web.py` renders it on the local page. Do not add a dashboard pipeline module.
- Webhooks and Telegram are outbound. A local HTML page on 127.0.0.1 may toggle `reports/cores.json` (core ON/OFF). Do not add login, order tickets, or a public bind.
- Secrets only via env (`FX_TRADER_WEBHOOK_SECRET`, `TELEGRAM_BOT_TOKEN`); never commit them.
- Tests cover formulas and rendering, not live URLs.
