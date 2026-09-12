"""Compatibility shim. Implementation: app/account/backtest/run_portfolio.py"""
import _boot_app  # noqa: F401
from account.backtest.run_portfolio import *  # noqa: F403
from account.backtest.run_portfolio import main
from account.propose import risk_pct_for  # noqa: F401
from account.settings import parse_symbols  # noqa: F401
from strategy.params import load_pair_params as _load_pair_params  # noqa: F401
from strategy.params import portfolio_params as _portfolio_params  # noqa: F401

if __name__ == "__main__":
    raise SystemExit(main())
