"""Ablate session / monthly MACD / BB vs pivot. Explore only."""

from __future__ import annotations

from account.settings import kit_data_dir, load_config
from feed.loader import load_csv
from strategy.backtest.explore_h1 import _print_m, _run
from strategy.cores.bb_squeeze_pivot import BbSqueezePivotParams, BbSqueezePivotStrategy
from strategy.cores.donchian.backtest.optimize_donchian import TEST_END, TRAIN_END
from strategy.cores.mtf_bb_pivot import MtfBbPivotParams, MtfBbPivotStrategy

SYMBOLS = ["EURUSD", "GBPUSD", "USDJPY", "USDCAD"]

VARIANTS = [
    (
        "BO overlap+12H+MACD (no squeeze)",
        lambda: BbSqueezePivotStrategy(BbSqueezePivotParams(require_squeeze=False)),
    ),
    (
        "BO squeeze+12H+overlap (no H1 MACD)",
        lambda: BbSqueezePivotStrategy(BbSqueezePivotParams(require_macd=False)),
    ),
    (
        "BO squeeze+12H+MACD (no session)",
        lambda: BbSqueezePivotStrategy(BbSqueezePivotParams(require_overlap=False)),
    ),
    (
        "MR daily BB±2σ + overlap",
        lambda: MtfBbPivotStrategy(
            MtfBbPivotParams(
                require_monthly=False,
                require_h4_bounce=False,
                require_h1_bb=False,
            )
        ),
    ),
    (
        "MR 4H pivot bounce + overlap",
        lambda: MtfBbPivotStrategy(
            MtfBbPivotParams(
                require_monthly=False,
                require_daily_bb=False,
                require_h4_bounce=True,
                require_h1_bb=False,
            )
        ),
    ),
    (
        "MR monthly MACD + daily BB + overlap",
        lambda: MtfBbPivotStrategy(
            MtfBbPivotParams(
                require_monthly=True,
                require_h4_bounce=False,
                require_h1_bb=False,
            )
        ),
    ),
]


def main() -> int:
    cfg = load_config()
    data_dir = kit_data_dir(cfg)
    print("Ablation: use 1-1/1-2/1-3 as separate filters, not a 5-TF AND.", flush=True)
    print("Session is DST overlap, not fixed 13-17 UTC. Asia is already off when overlap is on.", flush=True)
    for symbol in SYMBOLS:
        path = data_dir / f"{symbol.lower()}_h1.csv"
        if not path.exists():
            print(f"missing {path}", flush=True)
            continue
        h1 = load_csv(path)
        print(f"\n## {symbol}", flush=True)
        for title, factory in VARIANTS:
            prepared = factory().prepare(h1)
            n_sig = int((prepared["signal"] != 0).sum())
            print(f"  {title}  signal_bars={n_sig}", flush=True)
            train = prepared.index < TRAIN_END
            mid = (prepared.index >= TRAIN_END) & (prepared.index < TEST_END)
            for name, mask in (("train<2021", train), ("2021-2025", mid)):
                _, _, m = _run(prepared, cfg, symbol, mask)
                _print_m(name, m)
    print("\nAblation measurements. Not a live pin.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
