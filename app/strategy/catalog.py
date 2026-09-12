from __future__ import annotations

from .confluence import ConfluenceStrategy
from .donchian import DonchianStrategy
from .ema_atr import EmaAtrStrategy
from .engulfing_rvol import EngulfingRvolStrategy
from .killzone import KillZoneStrategy

STRATEGIES = {
    "donchian": DonchianStrategy,
    "ema_atr": EmaAtrStrategy,
    "engulfing": EngulfingRvolStrategy,
    "killzone": KillZoneStrategy,
    "confluence": ConfluenceStrategy,
}

__all__ = [
    "DonchianStrategy",
    "EmaAtrStrategy",
    "EngulfingRvolStrategy",
    "KillZoneStrategy",
    "ConfluenceStrategy",
    "STRATEGIES",
]
