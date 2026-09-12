"""Run from fx_trader/: python download_data.py"""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent / "app"))
from feed.download import main

if __name__ == "__main__":
    raise SystemExit(main())
