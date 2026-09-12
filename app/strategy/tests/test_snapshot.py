from __future__ import annotations

from feed.loader import make_synthetic
from strategy.donchian import DonchianParams, DonchianStrategy
from strategy.params import snapshot_pair


def test_snapshot_has_no_order_and_no_lots():
    h4 = make_synthetic(n=800, freq="4h", seed=3, trend=0.00004)
    params = DonchianParams(use_adx_filter=False, use_atr_filter=False)
    prepared = DonchianStrategy(params).prepare(h4)
    snap = snapshot_pair("EURUSD", prepared, params, lookback=5)
    assert snap["symbol"] == "EURUSD"
    assert snap["signal"] in (-1, 0, 1)
    assert "order" not in snap
    assert "lots" not in snap
    assert isinstance(snap["recent_signals"], list)
    assert len(snap["recent_signals"]) <= 5
