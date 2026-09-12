from __future__ import annotations

from feed.loader import make_synthetic
from strategy.cores.donchian.backtest.eval_regime import apply_regime, attach_regime
from strategy.cores.donchian import DonchianStrategy


def test_regime_features_are_closed_bar():
    h4 = make_synthetic(n=400, freq="4h", seed=7, trend=0.00004)
    prepared = attach_regime(DonchianStrategy().prepare(h4))
    assert {"ema50_slope_pct", "bb_width_pctl", "atr_ratio"}.issubset(prepared.columns)
    later = attach_regime(DonchianStrategy().prepare(h4.iloc[:-20]))
    overlap = later.index.intersection(prepared.index)
    cols = ["ema50_slope_pct", "bb_width", "atr_ratio"]
    assert (prepared.loc[overlap, cols] - later.loc[overlap, cols]).abs().max().max() < 1e-12


def test_regime_filters_only_zero_signals():
    h4 = make_synthetic(n=400, freq="4h", seed=7, trend=0.00004)
    prepared = attach_regime(DonchianStrategy().prepare(h4))
    base_n = int((prepared["signal"] != 0).sum())
    assert apply_regime(prepared, "baseline")["signal"].equals(prepared["signal"])
    for name in ("slope_agree", "not_squeeze", "atr_expand", "trend", "skip_chop"):
        gated = apply_regime(prepared, name)
        assert int((gated["signal"] != 0).sum()) <= base_n
        kept = gated["signal"] != 0
        assert (gated.loc[kept, "signal"] == prepared.loc[kept, "signal"]).all()
