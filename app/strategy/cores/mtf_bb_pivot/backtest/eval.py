from strategy.backtest.explore_h1 import evaluate
from strategy.cores.mtf_bb_pivot import MtfBbPivotStrategy


def main() -> int:
    return evaluate(
        MtfBbPivotStrategy(),
        title="mtf_bb_pivot v4  (daily BB ±2σ + overlap, 1 per stretch, stop 2.5σ)",
    )


if __name__ == "__main__":
    raise SystemExit(main())
