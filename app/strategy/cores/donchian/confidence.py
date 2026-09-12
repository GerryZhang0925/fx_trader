"""H4 confidence score (max 10) used only to scale risk_mult, not to invent entries.

Score uses completed-bar data only. Kill Zone is scored by H4-bar overlap with
London/NY windows (M5 timestamps are not on disk).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from strategy.common.indicators import ema, in_session
from strategy.common.pips import pip_size as pair_pip


@dataclass
class ConfidenceParams:
    ema_fast: int = 20
    ema_mid: int = 50
    pullback_bars: int = 8
    near_atr: float = 0.25
    london_early: str = "07:00-09:00"
    london_late: str = "09:00-10:00"
    ny_early: str = "13:00-15:00"
    ny_late: str = "15:00-16:00"
    asia: str = "00:00-03:00"
    timezone: str = "UTC"
    rr_min: float = 2.0
    a_plus_mult: float = 2.0
    b_mult: float = 1.0
    c_mult: float = 0.5


def _split(window: str) -> tuple[str, str]:
    a, b = window.split("-")
    return a.strip(), b.strip()


def _bar_overlaps(index: pd.DatetimeIndex, start: str, end: str, tz: str, hours: float = 4.0) -> pd.Series:
    """True if [bar_open, bar_open+hours) overlaps [start, end) on the clock."""
    opens = in_session(index, start, end, tz)
    shifted = index + pd.Timedelta(hours=hours) - pd.Timedelta(seconds=1)
    insides = in_session(pd.DatetimeIndex(shifted), start, end, tz)
    insides.index = index
    return opens | insides


def _near(a: pd.Series, b: pd.Series, tol: pd.Series) -> pd.Series:
    return (a - b).abs() <= tol


def _round_level(close: pd.Series, pip: float) -> pd.Series:
    step = pip * 50.0
    return (close / step).round() * step


def apply_confidence(
    prepared: pd.DataFrame,
    *,
    symbol: str = "EURUSD",
    params: ConfidenceParams | None = None,
    skip_c: bool = False,
) -> pd.DataFrame:
    """Add score / grade / risk_mult. Optionally zero C-grade signals."""
    p = params or ConfidenceParams()
    out = prepared.copy()
    pip = pair_pip(symbol)
    close = out["close"]
    atr = out["atr"].replace(0, np.nan)
    tol = atr * p.near_atr
    ema20 = ema(close, p.ema_fast)
    ema50 = ema(close, p.ema_mid)
    ema200 = out["ema_trend"]
    out["ema20"] = ema20
    out["ema50"] = ema50

    sig = out["signal"].fillna(0).astype(int)
    long_s = sig > 0
    short_s = sig < 0

    perfect_long = (ema20 > ema50) & (ema50 > ema200)
    perfect_short = (ema20 < ema50) & (ema50 < ema200)
    look = max(int(p.pullback_bars), 1)
    pulled_long = out["low"].rolling(look, min_periods=1).min() <= (ema20 + 0.25 * atr)
    pulled_short = out["high"].rolling(look, min_periods=1).max() >= (ema20 - 0.25 * atr)
    cramped_long = (out["swing_high"] > close) & ((out["swing_high"] - close) < 0.5 * atr)
    cramped_short = (out["swing_low"] < close) & ((close - out["swing_low"]) < 0.5 * atr)

    trend = pd.Series(0, index=out.index, dtype=int)
    trend.loc[long_s & (close > ema200)] = 1
    trend.loc[short_s & (close < ema200)] = 1
    trend.loc[long_s & perfect_long & pulled_long & ~cramped_long] = 2
    trend.loc[short_s & perfect_short & pulled_short & ~cramped_short] = 2

    early = _bar_overlaps(out.index, *_split(p.london_early), p.timezone) | _bar_overlaps(
        out.index, *_split(p.ny_early), p.timezone
    )
    late = _bar_overlaps(out.index, *_split(p.london_late), p.timezone) | _bar_overlaps(
        out.index, *_split(p.ny_late), p.timezone
    )
    asia = _bar_overlaps(out.index, *_split(p.asia), p.timezone)
    kz = pd.Series(0, index=out.index, dtype=int)
    kz.loc[late | asia] = 1
    kz.loc[early] = 2

    rng = (out["swing_high"] - out["swing_low"]).replace(0, np.nan)
    fib_long = out["swing_high"] - 0.618 * rng
    fib_short = out["swing_low"] + 0.618 * rng
    near_level = pd.Series(False, index=out.index)
    near_level.loc[long_s] = _near(close, out["donch_hi"], tol)[long_s]
    near_level.loc[short_s] = _near(close, out["donch_lo"], tol)[short_s]
    near_fib = _near(close, fib_long, tol) | _near(close, fib_short, tol)
    near_ema = _near(close, ema20, tol)
    near_round = _near(close, _round_level(close, pip), pd.Series(5.0 * pip, index=out.index))
    conf_hits = (
        near_level.astype(int) + near_fib.astype(int) + near_ema.astype(int) + near_round.astype(int)
    )
    conf = conf_hits.clip(upper=3)

    body = (out["close"] - out["open"]).abs()
    body_top = out[["open", "close"]].max(axis=1)
    body_bot = out[["open", "close"]].min(axis=1)
    prev_top = body_top.shift(1)
    prev_bot = body_bot.shift(1)
    bull_eng = (out["close"] > out["open"]) & (out["close"].shift(1) < out["open"].shift(1))
    bull_eng = bull_eng & (body_bot <= prev_bot) & (body_top >= prev_top)
    bear_eng = (out["close"] < out["open"]) & (out["close"].shift(1) > out["open"].shift(1))
    bear_eng = bear_eng & (body_top >= prev_top) & (body_bot <= prev_bot)
    engulf = (long_s & bull_eng) | (short_s & bear_eng)
    eng_score = pd.Series(0, index=out.index, dtype=int)
    eng_score.loc[engulf] = 1
    eng_score.loc[engulf & (body >= atr)] = 2

    width = (out["donch_hi"] - out["donch_lo"]).clip(lower=0.5 * atr)
    target_long = close + width
    target_short = close - width
    room = pd.Series(0.0, index=out.index)
    room.loc[long_s] = (target_long - close)[long_s] / out["stop_dist"][long_s].replace(0, np.nan)
    room.loc[short_s] = (close - target_short)[short_s] / out["stop_dist"][short_s].replace(0, np.nan)
    rr = (room >= p.rr_min).astype(int)

    total = trend + kz + conf + eng_score + rr
    total = total.where(sig != 0, 0)
    grade = pd.Series("none", index=out.index)
    grade.loc[sig != 0] = "C"
    grade.loc[total >= 5] = "B"
    grade.loc[total >= 8] = "A+"
    risk_mult = pd.Series(1.0, index=out.index)
    risk_mult.loc[grade == "C"] = p.c_mult
    risk_mult.loc[grade == "B"] = p.b_mult
    risk_mult.loc[grade == "A+"] = p.a_plus_mult
    risk_mult.loc[sig == 0] = 1.0

    out["score_trend"] = trend
    out["score_kz"] = kz
    out["score_conf"] = conf
    out["score_engulf"] = eng_score
    out["score_rr"] = rr
    out["confidence"] = total
    out["grade"] = grade
    out["risk_mult"] = risk_mult
    if skip_c:
        skip = grade == "C"
        out.loc[skip, "signal"] = 0
        out.loc[skip, "risk_mult"] = 1.0
    return out
