"""Adopted Donchian 3-pair book on unused 2026-01..08. Frozen JSON. No retune."""

from __future__ import annotations

import pandas as pd

from paths import KIT_DIR, boot

boot()

from account.backtest.run_portfolio import _daily_pnl, _load_pair_params, _portfolio_params  # noqa: E402
from account.engine import run_backtest  # noqa: E402
from account.metrics import compute_metrics  # noqa: E402
from account.settings import engine_from_config, kit_data_dir, kit_params_dir, load_config  # noqa: E402
from feed.loader import load_csv  # noqa: E402
from feed.pairs import pip_size  # noqa: E402
from strategy.cores.donchian import DonchianStrategy  # noqa: E402
from strategy.cores.donchian.backtest.eval_regime import CORE  # noqa: E402

ROOT = KIT_DIR
HOLD_START = "2026-01-01"
HOLD_END = "2026-09-01"
DD_CAP = 15.0


def _run(prepared, cfg, symbol, risk, mask):
    frame = prepared.loc[mask]
    engine = engine_from_config(cfg, pip_size=pip_size(symbol), risk_pct=risk)
    eq, trades = run_backtest(frame, engine)
    return eq, trades, compute_metrics(eq, trades, engine.initial_equity)


def _print_m(label: str, m) -> None:
    print(
        f"  {label:12} n={m.trades:4} PF={m.profit_factor:.3f} avgR={m.avg_r:.3f} "
        f"WR={m.win_rate:.1%} year={m.yearly_return_mean:.2%} CAGR={m.cagr:.2%} "
        f"DD={m.max_drawdown_pct:.2f}% Sharpe={m.sharpe:.2f} span={m.years:.2f}y",
        flush=True,
    )


def main() -> int:
    cfg = load_config()
    data_dir = kit_data_dir(cfg)
    params_dir = kit_params_dir(cfg)
    risk = float((cfg.get("portfolio") or {}).get("risk_pct_per_pair", 5.0))
    initial = float(cfg.get("initial_equity", 100000))
    fallback = _portfolio_params(cfg)
    print(
        f"Adopted Donchian holdout {HOLD_START} <= t < {HOLD_END}  risk={risk}%  "
        "frozen JSON, one shot",
        flush=True,
    )
    pnls = {}
    trade_frames = []
    for symbol in CORE:
        params, _ = _load_pair_params(symbol, params_dir, fallback)
        h4 = load_csv(data_dir / f"{symbol.lower()}_h4.csv")
        prepared = DonchianStrategy(params).prepare(h4)
        mask = (prepared.index >= HOLD_START) & (prepared.index < HOLD_END)
        n_bars = int(mask.sum())
        print(
            f"prepare {symbol} L={params.length} ATR={params.atr_mult} "
            f"ADX={params.adx_min} filt={params.use_atr_filter} bars={n_bars}",
            flush=True,
        )
        eq, trades, m = _run(prepared, cfg, symbol, risk, mask)
        _print_m(symbol, m)
        pnls[symbol] = _daily_pnl(eq)
        if not trades.empty:
            trade_frames.append(trades.assign(symbol=symbol))
    pnl_sum = pd.concat(pnls, axis=1).fillna(0.0).sum(axis=1)
    eq = (initial + pnl_sum.cumsum()).rename("equity")
    trades = pd.concat(trade_frames, ignore_index=True) if trade_frames else pd.DataFrame()
    if not trades.empty:
        trades = trades.sort_values("exit_time")
    book = compute_metrics(eq, trades, initial)
    _print_m("BOOK", book)
    aligned = pd.concat(pnls, axis=1).dropna()
    if len(aligned) > 3:
        print("  strategy daily-PnL corr:\n" + aligned.corr().round(3).to_string(), flush=True)
    print(
        f"DD cap {DD_CAP:g}%. Small-n window; do not retune length/ATR/ADX/risk.",
        flush=True,
    )
    out = ROOT / "reports" / "holdout_2026.md"
    lines = [
        "# Adopted Donchian holdout 2026-01 to 2026-08",
        "",
        "Frozen pair JSON, 5% per pair, next-bar fill, 1 pip + 0.2. Window starts empty (no 2025 carry). One shot. Checklist, not a guarantee.",
        "",
        f"- Book n={book.trades} PF={book.profit_factor:.3f} avgR={book.avg_r:.3f} "
        f"year={book.yearly_return_mean:.2%} CAGR={book.cagr:.2%} DD={book.max_drawdown_pct:.2f}% "
        f"Sharpe={book.sharpe:.2f} years={book.years:.2f}",
        "",
        "Do not change live params from this window.",
        "",
        "Educational review — not financial advice.",
        "",
    ]
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {out}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
