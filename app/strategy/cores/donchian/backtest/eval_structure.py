"""FVG / liquidity sweep / BOS / order-block proxies as Donchian filters."""

from __future__ import annotations

import pandas as pd

from paths import boot

boot()

from strategy.cores.donchian.backtest.overlay_eval import gate_signals, run_overlay  # noqa: E402
from strategy.common.indicators import bearish_fvg, bullish_fvg  # noqa: E402

FILTERS = ("baseline", "fvg", "bos", "sweep", "order_block")


def attach_structure(symbol: str, prepared: pd.DataFrame, data_dir) -> pd.DataFrame:
    out = prepared.copy()
    fvg_b = bullish_fvg(out).fillna(False)
    fvg_s = bearish_fvg(out).fillna(False)
    out["fvg_bull"] = fvg_b.rolling(8, min_periods=1).max().eq(True)
    out["fvg_bear"] = fvg_s.rolling(8, min_periods=1).max().eq(True)
    out["bos_bull"] = out["close"] > out["swing_high"]
    out["bos_bear"] = out["close"] < out["swing_low"]
    sl = out["swing_low"]
    sh = out["swing_high"]
    out["sweep_bull"] = (out["low"].shift(1) < sl.shift(1)) & (out["close"].shift(1) > sl.shift(1))
    out["sweep_bear"] = (out["high"].shift(1) > sh.shift(1)) & (out["close"].shift(1) < sh.shift(1))
    disp = (out["close"] - out["open"]).abs() >= (0.5 * out["atr"])
    out["ob_bull"] = (out["close"].shift(1) < out["open"].shift(1)) & (out["close"] > out["open"]) & disp
    out["ob_bear"] = (out["close"].shift(1) > out["open"].shift(1)) & (out["close"] < out["open"]) & disp
    return out


def apply_structure(prepared: pd.DataFrame, name: str) -> pd.DataFrame:
    sig = prepared["signal"]
    long_ = sig > 0
    short_ = sig < 0
    if name == "baseline":
        keep = sig != 0
    elif name == "fvg":
        keep = (long_ & prepared["fvg_bull"]) | (short_ & prepared["fvg_bear"])
    elif name == "bos":
        keep = (long_ & prepared["bos_bull"]) | (short_ & prepared["bos_bear"])
    elif name == "sweep":
        keep = (long_ & prepared["sweep_bull"]) | (short_ & prepared["sweep_bear"])
    elif name == "order_block":
        keep = (long_ & prepared["ob_bull"]) | (short_ & prepared["ob_bear"])
    else:
        raise ValueError(f"unknown structure filter {name!r}")
    return gate_signals(prepared, keep)


def main() -> int:
    return run_overlay(
        filters=FILTERS,
        attach=attach_structure,
        apply_fn=apply_structure,
        report_stem="structure",
        title="Structure filters on adopted Donchian",
        note="FVG in last 8 bars, swing BOS, prior-bar sweep, last opposite candle + displacement. Closed bar only.",
    )


if __name__ == "__main__":
    raise SystemExit(main())
