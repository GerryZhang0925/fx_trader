from strategy.backtest.explore_h1 import evaluate
from strategy.cores.h1_donchian import H1DonchianStrategy


def main() -> int:
    return evaluate(
        H1DonchianStrategy(),
        title="h1_donchian  (H1 20-bar channel + ATR×2.5 trail, no ADX)",
    )


if __name__ == "__main__":
    raise SystemExit(main())
