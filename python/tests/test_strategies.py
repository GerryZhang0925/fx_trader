from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from data_loader import make_synthetic, resample_ohlcv
from engine import EngineConfig, run_backtest
from strategies.confluence import ConfluenceStrategy
from strategies.confidence import apply_confidence
from strategies.donchian import DonchianStrategy
from strategies.ema_atr import EmaAtrStrategy
from strategies.engulfing_rvol import EngulfingRvolStrategy
from strategies.killzone import KillZoneStrategy


def test_each_strategy_prepares_and_backtests_synthetic():
    h4 = make_synthetic(n=800, freq="4h", seed=3)
    cfg = EngineConfig()
    for cls in (DonchianStrategy, EmaAtrStrategy, EngulfingRvolStrategy):
        prepared = cls().prepare(h4)
        assert set(["signal", "stop_dist", "atr"]).issubset(prepared.columns)
        eq, trades = run_backtest(prepared, cfg)
        assert len(eq) == len(h4)
        assert eq.iloc[-1] > 0


def test_killzone_on_m5_synthetic():
    m5 = make_synthetic(n=4000, freq="5min", seed=4, vol=0.0003)
    prepared = KillZoneStrategy().prepare(m5)
    assert "in_killzone" in prepared.columns
    assert prepared["score_long"].max() >= 0
    eq, _ = run_backtest(prepared, EngineConfig())
    assert len(eq) == len(m5)


def test_confluence_prefers_core_direction():
    h4 = make_synthetic(n=1200, freq="4h", seed=11, trend=0.00003)
    out = ConfluenceStrategy().prepare(h4)
    core = DonchianStrategy().prepare(h4)
    both = (core["signal"] != 0) & (out["signal"] != 0)
    if both.any():
        assert (out.loc[both, "signal"] == core.loc[both, "signal"]).all()


def test_confluence_m5_aligns_with_h4_bias():
    m5 = make_synthetic(n=5000, freq="5min", seed=9)
    h4 = resample_ohlcv(m5, "4h")
    out = ConfluenceStrategy().prepare_m5(m5, h4)
    fired = out["signal"] != 0
    if fired.any():
        assert (out.loc[fired, "signal"] == out.loc[fired, "h4_bias"]).all()


def test_confidence_scores_are_bounded():
    h4 = make_synthetic(n=800, freq="4h", seed=3)
    prepared = DonchianStrategy().prepare(h4)
    scored = apply_confidence(prepared, symbol="EURUSD")
    fired = scored["signal"] != 0
    assert fired.any()
    assert scored.loc[fired, "confidence"].between(0, 10).all()
    assert set(scored.loc[fired, "grade"]).issubset({"A+", "B", "C"})
    skipped = apply_confidence(prepared, symbol="EURUSD", skip_c=True)
    assert int((skipped["signal"] != 0).sum()) <= int(fired.sum())
