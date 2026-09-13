"""OHLCV resample helper so strategy does not import feed."""

from __future__ import annotations

import pandas as pd


def resample_ohlcv(df: pd.DataFrame, rule: str) -> pd.DataFrame:
    agg = {
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum",
    }
    return df.resample(rule, label="left", closed="left").agg(agg).dropna()


def align_htf(series: pd.Series, index: pd.DatetimeIndex, *, lag: int = 1) -> pd.Series:
    """Map HTF values onto LTF bars. lag=1 uses only the last *closed* HTF bar."""
    s = series.shift(lag) if lag else series
    return s.reindex(index, method="ffill")


def nearer_target(close: pd.Series, direction: int, *levels: pd.Series) -> pd.Series:
    """Nearest level beyond price. NaN if none."""
    cols = [s for s in levels if s is not None]
    if not cols:
        return pd.Series(index=close.index, dtype=float)
    stacked = pd.concat(cols, axis=1)
    if direction > 0:
        return stacked.where(stacked.gt(close, axis=0)).min(axis=1)
    return stacked.where(stacked.lt(close, axis=0)).max(axis=1)
