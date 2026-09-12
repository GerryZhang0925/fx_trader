"""Pip size so strategy research helpers do not import feed."""


def pip_size(symbol: str) -> float:
    return 0.01 if symbol.upper().endswith("JPY") else 0.0001
