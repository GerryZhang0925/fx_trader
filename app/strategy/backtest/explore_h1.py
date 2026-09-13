"""Standalone H1 explore eval. Not an add-on gate vs live Donchian."""

from __future__ import annotations

import pandas as pd

from account.engine import EngineConfig, run_backtest
from account.metrics import compute_metrics
from account.risk import RiskConfig
from account.settings import engine_from_config, kit_data_dir, load_config
from feed.loader import load_csv
from feed.pairs import pip_size
from strategy.cores.donchian.backtest.optimize_donchian import TEST_END, TRAIN_END

HOLDOUT_START = "2026-01-01"
SYMBOLS = ["EURUSD", "GBPUSD", "USDJPY", "USDCAD"]
RISK_PCT = 2.0


def _engine(cfg: dict, symbol: str) -> EngineConfig:
    base = engine_from_config(cfg, pip_size=pip_size(symbol), risk_pct=RISK_PCT)
    base.risk = RiskConfig(
        risk_pct=RISK_PCT,
        max_trades_per_day=8,
        max_consecutive_losses=10,
        max_daily_loss_r=4.0,
        lot_size=base.risk.lot_size,
    )
    return base


def _run(prepared, cfg, symbol, mask):
    frame = prepared.loc[mask]
    if frame.empty:
        return None, None, None
    eq, trades = run_backtest(frame, _engine(cfg, symbol))
    return eq, trades, compute_metrics(eq, trades, cfg.get("initial_equity", 100000))


def _print_m(label: str, m) -> None:
    if m is None:
        print(f"  {label:28} (no bars)", flush=True)
        return
    print(
        f"  {label:28} n={m.trades:4} PF={m.profit_factor:.3f} avgR={m.avg_r:.3f} "
        f"year={m.yearly_return_mean:.2%} CAGR={m.cagr:.2%} DD={m.max_drawdown_pct:.2f}% "
        f"Sharpe={m.sharpe:.2f}",
        flush=True,
    )


def evaluate(strategy, *, title: str, symbols: list[str] | None = None) -> int:
    cfg = load_config()
    data_dir = kit_data_dir(cfg)
    print(title, flush=True)
    print(f"Explore standalone  risk={RISK_PCT}%  next-bar  1pip+0.2  DST overlap", flush=True)
    any_ok = False
    for symbol in symbols or SYMBOLS:
        path = data_dir / f"{symbol.lower()}_h1.csv"
        if not path.exists():
            print(f"missing {path}", flush=True)
            continue
        any_ok = True
        h1 = load_csv(path)
        prepared = strategy.prepare(h1)
        n_sig = int((prepared["signal"] != 0).sum())
        print(f"\n{symbol}  bars={len(prepared)}  signal_bars={n_sig}", flush=True)
        train = prepared.index < TRAIN_END
        mid = (prepared.index >= TRAIN_END) & (prepared.index < TEST_END)
        hold = prepared.index >= HOLDOUT_START
        for name, mask in (
            ("train<2021", train),
            ("2021-2025", mid),
            ("2026-01..", hold),
        ):
            _, trades, m = _run(prepared, cfg, symbol, mask)
            _print_m(name, m)
            if trades is not None and not trades.empty:
                print(f"    exits {trades['exit_reason'].value_counts().to_dict()}", flush=True)
    if not any_ok:
        return 1
    print("\nStandalone explore. Not a live pin. Numbers are measurements, not targets.", flush=True)
    return 0
