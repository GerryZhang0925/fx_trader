from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from data_loader import make_synthetic
from run_signals import snapshot_pair
from strategies.donchian import DonchianParams, DonchianStrategy


def test_snapshot_is_signal_only_and_bounded():
    h4 = make_synthetic(n=800, freq="4h", seed=3, trend=0.00004)
    params = DonchianParams(use_adx_filter=False, use_atr_filter=False)
    prepared = DonchianStrategy(params).prepare(h4)
    snap = snapshot_pair("EURUSD", prepared, params, risk_pct=5.5, lookback=5)
    assert snap["symbol"] == "EURUSD"
    assert snap["signal"] in (-1, 0, 1)
    assert snap["side"] in ("long", "short", "flat")
    assert snap["next_fill"].startswith("next_H4")
    assert "order" not in snap
    if snap["signal"] != 0:
        assert snap["stop_dist"] > 0
        assert snap["stop_price_if_filled_at_close"] is not None
    assert isinstance(snap["recent_signals"], list)
    assert len(snap["recent_signals"]) <= 5
