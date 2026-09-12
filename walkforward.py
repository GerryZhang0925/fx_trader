"""Run from fx_trader/: python walkforward.py --strategy donchian --synthetic"""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent / "app"))
from strategy.backtest.walkforward import main

if __name__ == "__main__":
    raise SystemExit(main())
