---
name: software-structure
description: >-
  Layered layout for the fx_trader research kit. Use when adding modules,
  JSON reports, webhooks, metrics, venues, sleeves, or refactoring app/
  in this project.
paths: "fx_trader/app/**/*.py,fx_trader/app/**/*.yaml"
---

# Software structure (fx_trader)

Keep a thin pipeline. Do not turn this kit into a trading web app or a broker client.

## Layers

The top-level app calls modules in order. Modules do not import each other (backtest CLIs may compose them).

1. **App** — `app/run.py` orchestrates feed → strategy → account → output. Default: signals only, no orders.
2. **Feed** — `app/feed/` downloads and resamples OHLCV into kit `data/`. Instrument spec (`pip_size`, quote/base ccy) lives here.
3. **Strategy** — `app/strategy/` writes `signal` / `stop_dist` and declares stacking (ignore / reverse). Shared helpers in `strategy/common/`. Adopted cores live in `strategy/cores/<name>/`. No lots, no account currency, no connectors.
4. **Account** — `app/account/` is one module with three jobs (see `account/README.md`):
   - Research PnL: next-bar engine (`engine.py`) and overlay (`propose.py`). **Adopted fill math stays frozen.**
   - Book: venue account (kind + connector + login + currency + lot spec) and sleeve (capital slice). `books.py` `money.py` `intent.py`.
- Venue adapters: named by `connector`. OANDA Practice is read-only (`python -m account.venues`). `run.py` must not place orders.
5. **Output** — `app/output/` console, JSON, Telegram Bot API, local HTML on 127.0.0.1. Halt *messages* may originate here; halt *state* is the venue account. No orders.
6. **Contracts** — `app/contracts.py` documents dict shapes.

Each module has `README.md`, `config.yaml`, `tests/`, and a `backtest/` folder. PnL research lives in `account/backtest`. Per-core grids and overlay evals live in `strategy/cores/<name>/backtest`. Cross-core scripts stay in `strategy/backtest`. CLI scripts there compose layers; they must not reimplement Sharpe or JSON envelopes.

Kit root keeps one launcher: `run.py` (`python run.py` / `python -m app`). Do not put download, optimize, walkforward, or portfolio CLIs next to it — those are `python -m feed.download`, `python -m strategy.backtest` (Donchian optimize), `python -m account.backtest`. Do not revive a `python/` shim tree.

## Book vocabulary

Do not say 「仮想」 for both paper trading and capital slices.

- **Fill kind:** `paper` | `demo` | `live` (realism of the fill). Paper uses the same next-bar clock as the research engine, not signal-price immediate fills.
- **Connector:** the tool (e.g. `engine`, later `mt5`). Many demo tools allow one account each; live may attach several firms.
- **Venue account:** one login at one connector. Holds currency, lot step, halt flag.
- **Sleeve:** strategy capital inside one venue account. Does not cross connectors. Same symbol on two sleeves is a book refusal (not a strategy add).

Stacking intent is strategy spec; account executes it and maps tickets (netting vs hedge). Round lots **down**; skip if below min lot. Convert quote PnL into the venue account currency in `money.py` — do not change `engine.py` sizing for the adopted 11y reports.

Demo timing checks: compare upcoming `entry_time` (next H4 open, UTC) to demo tickets. Do not expect a broker tester to replay 2015–2026 onto the kit PF.

## Rules

- Add fields to `Metrics` rather than ad-hoc dicts in each runner.
- JSON reports use envelope `id`, `type`, `api_version`, `time`, `data`.
- Run status is `reports/status.jsonl` (append-only). `output/web.py` renders it on the local page. Do not add a dashboard pipeline module.
- Webhooks and Telegram are outbound. A local HTML page on 127.0.0.1 may toggle `reports/cores.json` (core ON/OFF). Do not add login, order tickets, or a public bind.
- Secrets only via env (`FX_TRADER_WEBHOOK_SECRET`, `TELEGRAM_BOT_TOKEN`, `OANDA_API_TOKEN`); never commit them.
- Tests cover formulas and rendering, not live URLs.
- Order of venue work: paper state matches engine → demo **read** → demo **write**. Live last. Do not cut H4 5% to fund a satellite sleeve.
