"""Compatibility shim."""
import sys
from pathlib import Path

_APP = Path(__file__).resolve().parents[2] / "app"
if str(_APP) not in sys.path:
    sys.path.insert(0, str(_APP))
from account.risk import *  # noqa: F403
