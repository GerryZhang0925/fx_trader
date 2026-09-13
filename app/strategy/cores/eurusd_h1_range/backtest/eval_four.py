"""H1 RSI fade on 4 pairs, standalone. Same rule as EURUSD; no add-on, no grid."""

from __future__ import annotations

from paths import boot

boot()

from account.engine import run_backtest  # noqa: E402
from account.metrics import compute_metrics  # noqa: E402
from account.settings import engine_from_config, kit_data_dir, load_config  # noqa: E402
from feed.loader import load_csv  # noqa: E402
from feed.pairs import pip_size  # noqa: E402
from strategy.cores.donchian.backtest.optimize_donchian import TEST_END, TRAIN_END  # noqa: E402
from strategy.cores.eurusd_h1_range import EurusdH1RangeStrategy  # noqa: E402

HOLDOUT_START = "2026-01-01"
SYMBOLS = ["EURUSD", "GBPUSD", "USDJPY", "USDCAD"]
RISK_PCT = 2.0


def _run(prepared, cfg, symbol, mask):
    frame = prepared.loc[mask]
    if frame.empty:
        return None, None, None
    engine = engine_from_config(cfg, pip_size=pip_size(symbol), risk_pct=RISK_PCT)
    eq, trades = run_backtest(frame, engine)
    return eq, trades, compute_metrics(eq, trades, engine.initial_equity)


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


def main() -> int:
    cfg = load_config()
    data_dir = kit_data_dir(cfg)
    print(
        "H1 RSI fade  4-pair standalone  "
        f"risk={RISK_PCT}%  next-bar  1pip+0.2  "
        "H4 ADX<20  EMA50 side  DST overlap",
        flush=True,
    )
    print("Same rule as EURUSD lockbox. Not an add-on. PF 1.55 is not a target.", flush=True)
    any_ok = False
    for symbol in SYMBOLS:
        path = data_dir / f"{symbol.lower()}_h1.csv"
        if not path.exists():
            print(f"missing {path}", flush=True)
            continue
        any_ok = True
        h1 = load_csv(path)
        prepared = EurusdH1RangeStrategy().prepare(h1)
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


if __name__ == "__main__":
    raise SystemExit(main())
