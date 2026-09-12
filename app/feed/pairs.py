"""FX pair specs for Dukascopy download and costing."""

from __future__ import annotations

PAIRS = {
    "EURUSD": {"pip_size": 0.0001, "point_value": 100000.0},
    "GBPUSD": {"pip_size": 0.0001, "point_value": 100000.0},
    "USDJPY": {"pip_size": 0.01, "point_value": 1000.0},
    "AUDUSD": {"pip_size": 0.0001, "point_value": 100000.0},
    "USDCAD": {"pip_size": 0.0001, "point_value": 100000.0},
    "NZDUSD": {"pip_size": 0.0001, "point_value": 100000.0},
}

CANDIDATES = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "NZDUSD"]
RECOMMENDED = ["USDCAD", "USDJPY", "GBPUSD"]
KEEP_BOTH = {frozenset({"EURUSD", "GBPUSD"})}


def pip_size(symbol: str) -> float:
    return float(PAIRS[symbol.upper()]["pip_size"])
