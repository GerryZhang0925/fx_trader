"""Compatibility shim. Implementation: app/account/engine.py"""
import sys
from pathlib import Path

_APP = Path(__file__).resolve().parents[2] / "app"
if str(_APP) not in sys.path:
    sys.path.insert(0, str(_APP))
from account.engine import *  # noqa: F403
