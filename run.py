"""Kit-root launcher. Download / optimize / backtest CLIs live under app/."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_APP = Path(__file__).resolve().parent / "app"
_APP_RUN = _APP / "run.py"

if str(_APP) in sys.path:
    sys.path.remove(str(_APP))
sys.path.insert(0, str(_APP))


def _load_app_run():
    name = "_fx_trader_app_run"
    cached = sys.modules.get(name)
    if cached is not None:
        return cached
    spec = importlib.util.spec_from_file_location(name, _APP_RUN)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {_APP_RUN}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


_app_run = _load_app_run()
main = _app_run.main
collect_proposals = _app_run.collect_proposals

if __name__ == "__main__":
    raise SystemExit(main())
