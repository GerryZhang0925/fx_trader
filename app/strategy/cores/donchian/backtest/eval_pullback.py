"""Standalone pullback (EMA21 / OTE / Fib) vs adopted Donchian. Do not mix scores."""

from __future__ import annotations

import pandas as pd

from paths import boot

boot()

from strategy.cores.donchian.backtest.overlay_eval import run_overlay  # noqa: E402
from strategy.common.indicators import ema  # noqa: E402

FILTERS = ("baseline", "ema21_pb", "ote", "fib618")


def _rising(cond: pd.Series) -> pd.Series:
    prev = cond.shift(1).fillna(False)
    return cond & prev.eq(False)


def attach_pullback(symbol: str, prepared: pd.DataFrame, data_dir) -> pd.DataFrame:
    out = prepared.copy()
    out["core_signal"] = out["signal"].astype(int)
    close = out["close"]
    atr = out["atr"]
    ema21 = ema(close, 21)
    ema200 = out["ema_trend"]
    rng = (out["swing_high"] - out["swing_low"]).replace(0, pd.NA)
    ote_hi = out["swing_high"] - 0.618 * rng
    ote_lo = out["swing_high"] - 0.79 * rng
    ote_hi_s = out["swing_low"] + 0.618 * rng
    ote_lo_s = out["swing_low"] + 0.79 * rng
    fib_long = out["swing_high"] - 0.618 * rng
    fib_short = out["swing_low"] + 0.618 * rng
    tol = 0.25 * atr

    long_pb = (close > ema200) & (out["low"] <= ema21) & (close >= ema21) & (close > out["open"])
    short_pb = (close < ema200) & (out["high"] >= ema21) & (close <= ema21) & (close < out["open"])
    out["sig_ema21"] = 0
    out.loc[_rising(long_pb), "sig_ema21"] = 1
    out.loc[_rising(short_pb), "sig_ema21"] = -1

    long_ote = (close > ema200) & (close <= ote_hi) & (close >= ote_lo) & (close > out["open"])
    short_ote = (close < ema200) & (close >= ote_hi_s) & (close <= ote_lo_s) & (close < out["open"])
    out["sig_ote"] = 0
    out.loc[_rising(long_ote), "sig_ote"] = 1
    out.loc[_rising(short_ote), "sig_ote"] = -1

    long_fib = (close > ema200) & ((close - fib_long).abs() <= tol) & (close > out["open"])
    short_fib = (close < ema200) & ((close - fib_short).abs() <= tol) & (close < out["open"])
    out["sig_fib618"] = 0
    out.loc[_rising(long_fib), "sig_fib618"] = 1
    out.loc[_rising(short_fib), "sig_fib618"] = -1
    return out


def apply_pullback(prepared: pd.DataFrame, name: str) -> pd.DataFrame:
    out = prepared.copy()
    mapping = {
        "baseline": "core_signal",
        "ema21_pb": "sig_ema21",
        "ote": "sig_ote",
        "fib618": "sig_fib618",
    }
    if name not in mapping:
        raise ValueError(f"unknown pullback variant {name!r}")
    out["signal"] = out[mapping[name]].astype(int)
    out.loc[out["signal"] == 0, "reason"] = ""
    out.loc[out["signal"] != 0, "reason"] = name
    return out


def main() -> int:
    return run_overlay(
        filters=FILTERS,
        attach=attach_pullback,
        apply_fn=apply_pullback,
        report_stem="pullback",
        title="Standalone pullback vs adopted Donchian",
        note="EMA21 reclaim / OTE 62–79% / Fib 61.8%. Separate strategies, not mixed with Donchian scores.",
    )


if __name__ == "__main__":
    raise SystemExit(main())
