"""Walk-forward windows and ±20% parameter sensitivity."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd
import yaml

from paths import KIT_DIR, boot

boot()
ROOT = KIT_DIR  # kit root

from account.engine import run_backtest  # noqa: E402
from account.metrics import compute_metrics  # noqa: E402
from account.settings import engine_from_config, load_config  # noqa: E402
from account.backtest.run_backtest import build_strategy, load_frames, prepare  # noqa: E402
from strategy.cores.donchian import DonchianParams, DonchianStrategy  # noqa: E402


def iter_windows(index: pd.DatetimeIndex, train_years: int, test_years: int, step_years: int):
    start = index[0]
    end = index[-1]
    cursor = start
    while True:
        train_end = cursor + pd.DateOffset(years=train_years)
        test_end = train_end + pd.DateOffset(years=test_years)
        if test_end > end:
            break
        train_slice = (index >= cursor) & (index < train_end)
        test_slice = (index >= train_end) & (index < test_end)
        if train_slice.sum() > 200 and test_slice.sum() > 50:
            yield cursor, train_end, test_end, train_slice, test_slice
        cursor = cursor + pd.DateOffset(years=step_years)


def run_walkforward(prepared: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    wf = cfg.get("walkforward", {})
    engine = engine_from_config(cfg)
    rows = []
    for t0, t1, t2, tr, te in iter_windows(
        prepared.index,
        int(wf.get("train_years", 3)),
        int(wf.get("test_years", 1)),
        int(wf.get("step_years", 1)),
    ):
        eq, trades = run_backtest(prepared.loc[te], engine)
        m = compute_metrics(eq, trades, cfg.get("initial_equity", 100000))
        rows.append(
            {
                "train_start": str(t0),
                "test_start": str(t1),
                "test_end": str(t2),
                "trades": m.trades,
                "profit_factor": m.profit_factor,
                "max_drawdown_pct": m.max_drawdown_pct,
                "sharpe": m.sharpe,
                "return_pct": m.return_pct,
            }
        )
    return pd.DataFrame(rows)


def sensitivity_donchian(df: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    base = cfg.get("donchian", {})
    length = int(base.get("length", 55))
    atr_mult = float(base.get("atr_mult", 2.5))
    engine = engine_from_config(cfg)
    rows = []
    for l_mult in (0.8, 1.0, 1.2):
        for a_mult in (0.8, 1.0, 1.2):
            params = DonchianParams.from_dict(
                {
                    **base,
                    "length": max(10, int(round(length * l_mult))),
                    "atr_mult": round(atr_mult * a_mult, 4),
                }
            )
            prepared = DonchianStrategy(params).prepare(df)
            eq, trades = run_backtest(prepared, engine)
            m = compute_metrics(eq, trades, cfg.get("initial_equity", 100000))
            rows.append(
                {
                    "length": params.length,
                    "atr_mult": params.atr_mult,
                    "trades": m.trades,
                    "profit_factor": m.profit_factor,
                    "max_drawdown_pct": m.max_drawdown_pct,
                    "sharpe": m.sharpe,
                    "return_pct": m.return_pct,
                }
            )
    return pd.DataFrame(rows)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--strategy", default="donchian")
    p.add_argument("--config", type=Path, default=None)
    p.add_argument("--csv", type=Path, default=None)
    p.add_argument("--m5-csv", type=Path, default=None)
    p.add_argument("--yahoo", action="store_true")
    p.add_argument("--synthetic", action="store_true")
    p.add_argument("--h4-only", action="store_true")
    p.add_argument("--m5-entries", action="store_true")
    p.add_argument("--seed", type=int, default=7)
    p.add_argument("--out", type=Path, default=None)
    args = p.parse_args(argv)
    cfg = load_config(args.config)
    from output.status import tracked

    out_dir = args.out or (ROOT / "reports")
    with tracked("strategy", "walkforward", out_dir=out_dir, message=args.strategy):
        return _walk(args, cfg, out_dir)


def _walk(args, cfg, out_dir: Path) -> int:
    h4, m5 = load_frames(args, cfg)
    strat = build_strategy(args.strategy, cfg)
    prepared = prepare(args.strategy, strat, h4, m5, args)
    wf = run_walkforward(prepared, cfg)
    out_dir.mkdir(parents=True, exist_ok=True)
    wf_path = out_dir / f"{args.strategy}_walkforward.csv"
    wf.to_csv(wf_path, index=False)
    print(wf.to_string(index=False) if not wf.empty else "No walk-forward windows (need longer history).")
    extra = {}
    if args.strategy in {"donchian", "confluence"}:
        src = h4
        sens = sensitivity_donchian(src, cfg)
        sens.to_csv(out_dir / f"{args.strategy}_sensitivity.csv", index=False)
        extra["sensitivity"] = sens.to_dict(orient="records")
        print("\nSensitivity (Donchian length / ATR mult +/- 20%):")
        print(sens.to_string(index=False))
    payload = {"walkforward": wf.to_dict(orient="records"), **extra}
    (out_dir / f"{args.strategy}_walkforward.json").write_text(
        json.dumps(payload, indent=2, default=str), encoding="utf-8"
    )
    print(f"\nWrote {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
