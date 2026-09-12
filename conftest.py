from pathlib import Path
import sys

APP = Path(__file__).resolve().parent / "app"
if str(APP) in sys.path:
    sys.path.remove(str(APP))
sys.path.insert(0, str(APP))

from paths import boot

boot()
