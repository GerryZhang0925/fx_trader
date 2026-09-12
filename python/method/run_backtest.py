"""Compatibility shim."""
import sys
from pathlib import Path

_APP = Path(__file__).resolve().parents[2] / "app"
if str(_APP) not in sys.path:
    sys.path.insert(0, str(_APP))
from account.backtest.run_backtest import *  # noqa: F403
from account.backtest.run_backtest import main
from account.settings import engine_from_config, load_config  # noqa: F401

if __name__ == "__main__":
    raise SystemExit(main())
