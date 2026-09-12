"""Compatibility shim. Implementation: app/strategy/backtest/optimize_pairs.py"""
import _boot_app  # noqa: F401
from strategy.backtest.optimize_pairs import main

if __name__ == "__main__":
    raise SystemExit(main())
