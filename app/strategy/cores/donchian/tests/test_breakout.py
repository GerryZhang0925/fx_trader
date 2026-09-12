from __future__ import annotations

from feed.loader import make_synthetic
from strategy.cores.donchian.backtest.eval_breakout import apply_breakout, attach_breakout
from strategy.cores.donchian import DonchianStrategy


def test_breakout_filters_do_not_add_lookahead_on_gates():
    h4 = make_synthetic(n=600, freq="4h", seed=8, trend=0.00003)
    prepared = attach_breakout("EURUSD", DonchianStrategy().prepare(h4), data_dir=None)
    later = attach_breakout("EURUSD", DonchianStrategy().prepare(h4.iloc[:-20]), data_dir=None)
    overlap = later.index.intersection(prepared.index)
    for col in ("break_buf", "body_atr"):
        delta = (prepared.loc[overlap, col] - later.loc[overlap, col]).abs().max()
        assert not (delta > 1e-12)
    assert prepared.loc[overlap, "flag_compact"].equals(later.loc[overlap, "flag_compact"])


def test_breakout_gates_only_zero_except_retest():
    h4 = make_synthetic(n=600, freq="4h", seed=8, trend=0.00003)
    prepared = attach_breakout("EURUSD", DonchianStrategy().prepare(h4), data_dir=None)
    base_n = int((prepared["signal"] != 0).sum())
    for name in ("buffer_0p1atr", "body_0p3atr", "rvol", "flag_compact"):
        gated = apply_breakout(prepared, name)
        assert int((gated["signal"] != 0).sum()) <= base_n
        kept = gated["signal"] != 0
        assert (gated.loc[kept, "signal"] == prepared.loc[kept, "signal"]).all()
    retest = apply_breakout(prepared, "retest_6")
    assert int((retest["signal"] != 0).sum()) <= base_n
