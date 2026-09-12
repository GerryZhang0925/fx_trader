"""Compatibility shim. Implementation: app/strategy/"""
import sys
from pathlib import Path

_APP = Path(__file__).resolve().parents[2] / "app"
if str(_APP) not in sys.path:
    sys.path.insert(0, str(_APP))
from strategy.catalog import *  # noqa: F403
from strategy.catalog import STRATEGIES  # noqa: F401
from strategy.donchian import DonchianParams, DonchianStrategy  # noqa: F401
