"""Kit and app directories. Entry points call boot() before other local imports."""

from __future__ import annotations

import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
KIT_DIR = APP_DIR.parent


def boot() -> None:
    """Put app/ first so `import run` is app/run.py, not the kit-root launcher."""
    app = str(APP_DIR)
    try:
        sys.path.remove(app)
    except ValueError:
        pass
    sys.path.insert(0, app)
