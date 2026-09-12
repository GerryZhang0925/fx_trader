"""Compatibility shim."""
import _boot_app  # noqa: F401
from strategy.backtest.optimize_donchian import main

if __name__ == "__main__":
    raise SystemExit(main())
