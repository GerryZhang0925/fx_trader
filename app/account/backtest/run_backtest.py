"""CLI: python run_backtest.py --strategy donchian --synthetic"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from paths import KIT_DIR, boot

boot()
ROOT = KIT_DIR  # kit root

from feed.loader import load_csv, load_h4, load_m5, make_synthetic, resample_ohlcv  # noqa: E402
from account.engine import run_backtest  # noqa: E402
from account.metrics import checklist, compute_metrics, format_report  # noqa: E402
from account.settings import engine_from_config, load_config  # noqa: E402
from output.reporting import envelope, notify, write_json  # noqa: E402
from strategy.catalog import STRATEGIES  # noqa: E402


def _drop_none(d: dict) -> dict:
    return {k: v for k, v in d.items() if v is not None}


def build_strategy(name: str, cfg: dict, **overrides):
    cls = STRATEGIES[name]
    section = dict(cfg.get(name if name != "engulfing" else "engulfing", {}))
    if name == "confluence":
        from strategy.confluence import ConfluenceParams
        from strategy.donchian import DonchianParams
        from strategy.engulfing_rvol import EngulfingParams
        from strategy.killzone import KillZoneParams

        params = ConfluenceParams(
            require_killzone=bool(section.get("require_killzone", False)),
            ranging_adx_max=float(section.get("ranging_adx_max", 20.0)),
            donchian_width_pct=float(section.get("donchian_width_pct", 0.012)),
            donchian=DonchianParams.from_dict(cfg.get("donchian", {})),
            engulfing=EngulfingParams(**_drop_none(cfg.get("engulfing", {}))),
            killzone=KillZoneParams(**_drop_none(cfg.get("killzone", {}))),
        )
        return cls(params)
    section.update(overrides)
    return cls(**_drop_none(section))


def load_frames(args, cfg: dict) -> tuple[pd.DataFrame, pd.DataFrame | None]:
    m5 = None
    if args.synthetic:
        freq = "5min" if args.strategy in {"killzone"} and not args.h4_only else "4h"
        n = 20000 if freq == "5min" else 5000
        df = make_synthetic(n=n, freq=freq, seed=args.seed)
        if freq == "5min":
            m5 = df
            df = resample_ohlcv(m5, "4h")
        return df, m5
    if args.m5_csv:
        m5 = load_m5(args.m5_csv)
    if args.csv:
        df = load_csv(args.csv)
        if args.strategy in {"killzone"} and m5 is None:
            return df, df
        return df, m5
    if args.yahoo:
        df = load_h4(yahoo=True, symbol=cfg.get("symbol", "EURUSD=X"))
        return df, m5
    raise SystemExit("Provide --csv, --yahoo, or --synthetic")


def prepare(name: str, strat, h4: pd.DataFrame, m5: pd.DataFrame | None, args) -> pd.DataFrame:
    if name == "killzone":
        src = m5 if m5 is not None else h4
        return strat.prepare(src)
    if name == "confluence":
        if args.m5_entries and m5 is not None:
            return strat.prepare_m5(m5, h4)
        return strat.prepare(h4, m5=m5 if not args.h4_only else None)
    return strat.prepare(h4 if m5 is None or args.strategy != "killzone" else m5)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="EURUSD research backtest (not live trading)")
    p.add_argument("--strategy", required=True, choices=sorted(STRATEGIES))
    p.add_argument("--config", type=Path, default=None)
    p.add_argument("--csv", type=Path, default=None)
    p.add_argument("--m5-csv", type=Path, default=None)
    p.add_argument("--yahoo", action="store_true")
    p.add_argument("--synthetic", action="store_true")
    p.add_argument("--h4-only", action="store_true")
    p.add_argument("--m5-entries", action="store_true", help="Confluence on M5 filtered by H4 bias")
    p.add_argument("--seed", type=int, default=7)
    p.add_argument("--out", type=Path, default=None)
    args = p.parse_args(argv)

    cfg = load_config(args.config)
    h4, m5 = load_frames(args, cfg)
    strat = build_strategy(args.strategy, cfg)
    prepared = prepare(args.strategy, strat, h4, m5, args)
    eq, trades = run_backtest(prepared, engine_from_config(cfg))
    metrics = compute_metrics(eq, trades, cfg.get("initial_equity", 100000))
    checks = checklist(metrics, cfg.get("targets", {}))
    report = format_report(metrics, checks, args.strategy)
    print(report)
    out_dir = args.out or (ROOT / "reports")
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = f"{args.strategy}_backtest"
    (out_dir / f"{stem}.md").write_text(report, encoding="utf-8")
    payload = envelope(
        {
            "metrics": metrics.to_dict(),
            "checklist": checks,
            "trades": len(trades),
        }
    )
    write_json(out_dir / f"{stem}.json", payload)
    hooked = notify(cfg, payload)
    if hooked:
        print(f"Webhook delivery: {hooked}")
    if not trades.empty:
        trades.to_csv(out_dir / f"{stem}_trades.csv", index=False)
    eq.to_csv(out_dir / f"{stem}_equity.csv", header=True)
    print(f"Wrote reports to {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
