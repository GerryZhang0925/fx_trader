"""Pine-compatible moving averages and volatility."""

from __future__ import annotations

import numpy as np
import pandas as pd


def ema(series: pd.Series, length: int) -> pd.Series:
    return series.ewm(span=length, adjust=False).mean()


def sma(series: pd.Series, length: int) -> pd.Series:
    return series.rolling(length, min_periods=length).mean()


def rma(series: pd.Series, length: int) -> pd.Series:
    """Wilder moving average (Pine ta.rma / ta.atr)."""
    return series.ewm(alpha=1.0 / length, adjust=False).mean()


def true_range(df: pd.DataFrame) -> pd.Series:
    prev_close = df["close"].shift(1)
    ranges = pd.concat(
        [
            df["high"] - df["low"],
            (df["high"] - prev_close).abs(),
            (df["low"] - prev_close).abs(),
        ],
        axis=1,
    )
    return ranges.max(axis=1)


def atr(df: pd.DataFrame, length: int = 14) -> pd.Series:
    return rma(true_range(df), length)


def donchian_prev(df: pd.DataFrame, length: int) -> tuple[pd.Series, pd.Series]:
    """Pine `ta.highest(high, length)[1]` / `ta.lowest(low, length)[1]`."""
    upper = df["high"].shift(1).rolling(length, min_periods=length).max()
    lower = df["low"].shift(1).rolling(length, min_periods=length).min()
    return upper, lower


def adx(df: pd.DataFrame, length: int = 14) -> pd.Series:
    up = df["high"].diff()
    down = -df["low"].diff()
    plus_dm = np.where((up > down) & (up > 0), up, 0.0)
    minus_dm = np.where((down > up) & (down > 0), down, 0.0)
    tr_rma = rma(true_range(df), length)
    plus_di = 100 * rma(pd.Series(plus_dm, index=df.index), length) / tr_rma
    minus_di = 100 * rma(pd.Series(minus_dm, index=df.index), length) / tr_rma
    dx = (100 * (plus_di - minus_di).abs() / (plus_di + minus_di)).replace(
        [np.inf, -np.inf], np.nan
    )
    return rma(dx, length)


def swing_points(df: pd.DataFrame, length: int = 5) -> tuple[pd.Series, pd.Series]:
    """Confirmed pivots lagged by `length` bars (no lookahead)."""
    high = df["high"]
    low = df["low"]
    win = 2 * length + 1
    is_sh = high == high.rolling(win, center=True).max()
    is_sl = low == low.rolling(win, center=True).min()
    sh = high.where(is_sh).shift(length)
    sl = low.where(is_sl).shift(length)
    return sh.ffill(), sl.ffill()


def bullish_fvg(df: pd.DataFrame) -> pd.Series:
    return df["low"] > df["high"].shift(2)


def bearish_fvg(df: pd.DataFrame) -> pd.Series:
    return df["high"] < df["low"].shift(2)


def in_session(index: pd.DatetimeIndex, start: str, end: str, tz: str = "UTC") -> pd.Series:
    """Inclusive start, exclusive end, clock times HH:MM in `tz`."""
    if index.tz is None:
        localized = index.tz_localize("UTC").tz_convert(tz)
    else:
        localized = index.tz_convert(tz)
    t = localized.time
    sh, sm = (int(x) for x in start.split(":"))
    eh, em = (int(x) for x in end.split(":"))
    start_m = sh * 60 + sm
    end_m = eh * 60 + em
    minutes = np.array([x.hour * 60 + x.minute for x in t])
    if start_m <= end_m:
        mask = (minutes >= start_m) & (minutes < end_m)
    else:
        mask = (minutes >= start_m) | (minutes < end_m)
    return pd.Series(mask, index=index)
