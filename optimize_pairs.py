"""Run from fx_trader/: python optimize_pairs.py"""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent / "app"))
from strategy.backtest.optimize_pairs import main

if __name__ == "__main__":
    raise SystemExit(main())
