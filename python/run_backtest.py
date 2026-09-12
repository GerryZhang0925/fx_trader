"""Compatibility shim. Implementation: app/account/backtest/run_backtest.py"""
import _boot_app  # noqa: F401
from account.backtest.run_backtest import *  # noqa: F403
from account.backtest.run_backtest import main
from account.settings import engine_from_config, load_config  # noqa: F401

if __name__ == "__main__":
    raise SystemExit(main())
