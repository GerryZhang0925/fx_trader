from strategy.backtest.explore_h1 import evaluate
from strategy.cores.bb_squeeze_pivot import BbSqueezePivotStrategy


def main() -> int:
    return evaluate(
        BbSqueezePivotStrategy(),
        title="bb_squeeze_pivot  (4H squeeze + 12H pivot break + H1 MACD)",
    )


if __name__ == "__main__":
    raise SystemExit(main())
