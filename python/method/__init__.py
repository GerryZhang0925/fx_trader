"""Compatibility shim. Trading method now lives under app/strategy and app/account."""

import sys
from pathlib import Path

_APP = Path(__file__).resolve().parents[2] / "app"
if str(_APP) not in sys.path:
    sys.path.insert(0, str(_APP))

from account.settings import engine_from_config, load_config
from account.propose import risk_pct_for
from account.settings import parse_symbols
from strategy.donchian import DonchianParams, DonchianStrategy
from strategy.params import load_pair_params as _load_pair_params
from strategy.params import portfolio_params as _portfolio_params

__all__ = [
    "DonchianParams",
    "DonchianStrategy",
    "engine_from_config",
    "load_config",
    "parse_symbols",
    "risk_pct_for",
    "_load_pair_params",
    "_portfolio_params",
]
