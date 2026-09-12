"""Kit and app directories. Entry points call boot() before other local imports."""

from __future__ import annotations

import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
KIT_DIR = APP_DIR.parent


def boot() -> None:
    for p in (str(APP_DIR), str(KIT_DIR)):
        if p not in sys.path:
            sys.path.insert(0, p)
