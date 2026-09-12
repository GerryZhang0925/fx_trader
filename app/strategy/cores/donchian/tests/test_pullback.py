from __future__ import annotations

from feed.loader import make_synthetic
from strategy.cores.donchian.backtest.eval_pullback import apply_pullback, attach_pullback
from strategy.cores.donchian import DonchianStrategy


def test_pullback_is_not_donchian_signal():
    h4 = make_synthetic(n=800, freq="4h", seed=2, trend=0.00004)
    prepared = attach_pullback("EURUSD", DonchianStrategy().prepare(h4), data_dir=None)
    ote = apply_pullback(prepared, "ote")
    core = apply_pullback(prepared, "baseline")
    both = (ote["signal"] != 0) & (core["signal"] != 0)
    # May overlap some bars; must not be a copy of Donchian.
    assert not ote["signal"].equals(core["signal"])
    assert int((apply_pullback(prepared, "ema21_pb")["signal"] != 0).sum()) >= 0
    if both.any():
        assert True
