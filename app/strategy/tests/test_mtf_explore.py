from __future__ import annotations

import pandas as pd

from account.engine import EngineConfig, run_backtest
from account.risk import RiskConfig
from feed.loader import make_synthetic
from strategy.common.indicators import bollinger, floor_pivots, macd
from strategy.cores.bb_squeeze_pivot import BbSqueezePivotStrategy
from strategy.cores.mtf_bb_pivot import MtfBbPivotParams, MtfBbPivotStrategy


def test_floor_pivots_use_previous_bar():
    df = pd.DataFrame(
        {
            "high": [3.0, 5.0],
            "low": [1.0, 2.0],
            "close": [2.0, 4.0],
        }
    )
    p, r1, s1, r2, s2 = floor_pivots(df)
    assert pd.isna(p.iloc[0])
    assert p.iloc[1] == 2.0
    assert r1.iloc[1] == 3.0
    assert s1.iloc[1] == 1.0
    assert r2.iloc[1] == 4.0
    assert s2.iloc[1] == 0.0


def test_macd_and_bollinger_finite():
    close = pd.Series([1.0 + 0.001 * i for i in range(80)])
    line, sig, hist = macd(close)
    mid, up, lo = bollinger(close, 20, 2.0)
    assert line.notna().sum() > 20
    assert (up.dropna() >= mid.dropna()).all()
    assert (lo.dropna() <= mid.dropna()).all()
    assert hist.notna().any()


def _cfg() -> EngineConfig:
    return EngineConfig(risk=RiskConfig(max_trades_per_day=20, max_consecutive_losses=20))


def test_bb_squeeze_pivot_prepares_h1():
    h1 = make_synthetic(n=4000, freq="1h", seed=12, vol=0.0008)
    out = BbSqueezePivotStrategy().prepare(h1)
    assert {"signal", "stop_dist", "h4_squeeze", "h12_r1", "in_overlap", "tp_price"}.issubset(
        out.columns
    )
    eq, _ = run_backtest(out, _cfg())
    assert len(eq) == len(h1)
    assert eq.iloc[-1] > 0


def test_or_setup_fires_at_least_as_often_as_five_and():
    h1 = make_synthetic(n=4000, freq="1h", seed=14, vol=0.0008)
    five_and = MtfBbPivotStrategy(
        MtfBbPivotParams(
            require_monthly=True,
            require_h4_bounce=True,
            require_h1_bb=True,
            combine_bb_bounce="and",
        )
    ).prepare(h1)
    recommended = MtfBbPivotStrategy().prepare(h1)
    assert int((recommended["signal"] != 0).sum()) >= int((five_and["signal"] != 0).sum())


def test_mtf_bb_pivot_prepares_h1():
    h1 = make_synthetic(n=5000, freq="1h", seed=13, vol=0.0008)
    out = MtfBbPivotStrategy().prepare(h1)
    assert {"signal", "stop_dist", "m_macd", "d_bb_mid", "h4_s1", "h1_bb_lower"}.issubset(
        out.columns
    )
    fired = out["signal"] != 0
    if fired.any():
        assert out.loc[out["signal"] == 1, "in_overlap"].all()
        assert out.loc[out["signal"] == -1, "in_overlap"].all()
        assert out.loc[out["signal"] == 1, "d_os"].all()
        assert out.loc[out["signal"] == -1, "d_ob"].all()
    eq, _ = run_backtest(out, _cfg())
    assert len(eq) == len(h1)
    assert eq.iloc[-1] > 0


def test_once_per_stretch_caps_daily_bb_signals():
    h1 = make_synthetic(n=5000, freq="1h", seed=13, vol=0.0008)
    many = MtfBbPivotStrategy(MtfBbPivotParams(once_per_stretch=False)).prepare(h1)
    one = MtfBbPivotStrategy().prepare(h1)
    assert int((one["signal"] != 0).sum()) <= int((many["signal"] != 0).sum())
    os_run = one["d_os"].ne(one["d_os"].shift(1)).cumsum()
    ob_run = one["d_ob"].ne(one["d_ob"].shift(1)).cumsum()
    assert (one["signal"].eq(1).groupby(os_run).sum() <= 1).all()
    assert (one["signal"].eq(-1).groupby(ob_run).sum() <= 1).all()
