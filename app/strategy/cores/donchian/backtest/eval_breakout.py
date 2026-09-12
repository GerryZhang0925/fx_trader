"""Breakout continuation overlays on adopted Donchian. Prefer keeping trade count."""

from __future__ import annotations

import numpy as np
import pandas as pd

from paths import boot

boot()

from strategy.cores.donchian.backtest.overlay_eval import gate_signals, run_overlay  # noqa: E402

FILTERS = ("baseline", "buffer_0p1atr", "body_0p3atr", "rvol", "flag_compact", "retest_6")


def attach_breakout(symbol: str, prepared: pd.DataFrame, data_dir) -> pd.DataFrame:
    out = prepared.copy()
    atr = out["atr"].replace(0, np.nan)
    out["break_buf"] = np.where(
        out["signal"] > 0,
        (out["close"] - out["donch_hi"]) / atr,
        np.where(out["signal"] < 0, (out["donch_lo"] - out["close"]) / atr, np.nan),
    )
    out["body_atr"] = (out["close"] - out["open"]).abs() / atr
    vol = out["volume"]
    out["rvol"] = vol / vol.rolling(20, min_periods=20).median()
    prior = (out["high"].shift(1).rolling(8, min_periods=8).max() - out["low"].shift(1).rolling(8, min_periods=8).min())
    impulse = (
        out["high"].shift(9).rolling(8, min_periods=8).max() - out["low"].shift(9).rolling(8, min_periods=8).min()
    )
    out["flag_compact"] = prior <= (0.7 * impulse)
    return out


def _retest(prepared: pd.DataFrame, look: int = 6) -> pd.DataFrame:
    sig = prepared["signal"].to_numpy(dtype=int)
    low = prepared["low"].to_numpy()
    high = prepared["high"].to_numpy()
    close = prepared["close"].to_numpy()
    donch_hi = prepared["donch_hi"].to_numpy()
    donch_lo = prepared["donch_lo"].to_numpy()
    out_sig = np.zeros(len(prepared), dtype=int)
    direction = 0
    bars_left = 0
    level = np.nan
    for i in range(len(prepared)):
        if direction == 1 and bars_left > 0:
            if low[i] <= level and close[i] > level:
                out_sig[i] = 1
                direction = 0
                bars_left = 0
            else:
                bars_left -= 1
        elif direction == -1 and bars_left > 0:
            if high[i] >= level and close[i] < level:
                out_sig[i] = -1
                direction = 0
                bars_left = 0
            else:
                bars_left -= 1
        if sig[i] == 1:
            direction = 1
            level = donch_hi[i]
            bars_left = look
        elif sig[i] == -1:
            direction = -1
            level = donch_lo[i]
            bars_left = look
    out = prepared.copy()
    out["signal"] = out_sig
    out.loc[out["signal"] == 0, "reason"] = ""
    return out


def apply_breakout(prepared: pd.DataFrame, name: str) -> pd.DataFrame:
    sig = prepared["signal"]
    if name == "baseline":
        return gate_signals(prepared, sig != 0)
    if name == "buffer_0p1atr":
        return gate_signals(prepared, (sig != 0) & (prepared["break_buf"] >= 0.1))
    if name == "body_0p3atr":
        return gate_signals(prepared, (sig != 0) & (prepared["body_atr"] >= 0.3))
    if name == "rvol":
        return gate_signals(prepared, (sig != 0) & (prepared["rvol"] >= 1.0))
    if name == "flag_compact":
        return gate_signals(prepared, (sig != 0) & prepared["flag_compact"].eq(True))
    if name == "retest_6":
        return _retest(prepared, 6)
    raise ValueError(f"unknown breakout filter {name!r}")


def main() -> int:
    return run_overlay(
        filters=FILTERS,
        attach=attach_breakout,
        apply_fn=apply_breakout,
        report_stem="breakout",
        title="Breakout continuation on adopted Donchian",
        note="Buffer / body / RVOL / flag compression / 6-bar retest. Prefer keeping trade count.",
    )


if __name__ == "__main__":
    raise SystemExit(main())
