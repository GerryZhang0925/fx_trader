"""FX pair specs for Dukascopy download and costing."""

from __future__ import annotations

PAIRS = {
    "EURUSD": {"pip_size": 0.0001, "point_value": 100000.0, "quote": "USD", "base": "EUR"},
    "GBPUSD": {"pip_size": 0.0001, "point_value": 100000.0, "quote": "USD", "base": "GBP"},
    "USDJPY": {"pip_size": 0.01, "point_value": 1000.0, "quote": "JPY", "base": "USD"},
    "AUDUSD": {"pip_size": 0.0001, "point_value": 100000.0, "quote": "USD", "base": "AUD"},
    "USDCAD": {"pip_size": 0.0001, "point_value": 100000.0, "quote": "CAD", "base": "USD"},
    "NZDUSD": {"pip_size": 0.0001, "point_value": 100000.0, "quote": "USD", "base": "NZD"},
    "USDCHF": {"pip_size": 0.0001, "point_value": 100000.0, "quote": "CHF", "base": "USD"},
}

CANDIDATES = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "NZDUSD", "USDCHF"]
RECOMMENDED = ["USDCAD", "USDJPY", "GBPUSD"]
KEEP_BOTH = {frozenset({"EURUSD", "GBPUSD"})}


def pip_size(symbol: str) -> float:
    return float(PAIRS[symbol.upper()]["pip_size"])


def quote_currency(symbol: str) -> str:
    return str(PAIRS[symbol.upper()]["quote"])


def base_currency(symbol: str) -> str:
    return str(PAIRS[symbol.upper()]["base"])
