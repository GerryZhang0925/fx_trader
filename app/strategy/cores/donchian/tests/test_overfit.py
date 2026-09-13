from __future__ import annotations

import pandas as pd

from strategy.cores.donchian.backtest.eval_overfit import (
    deflated_sharpe,
    effective_trials,
    expected_max_z,
    n_eff_from_rho,
    pbo_proxy,
)
from strategy.cores.donchian.backtest.optimize_donchian import grid_params
from strategy.cores.donchian.backtest.select_grid import pf_floor_for, select_row


def _cell(length, atr, adx, filt, train_pf, test_pf, train_ret, test_ret, train_sr, test_sr, train_dd=5.0):
    return {
        "length": length,
        "atr_mult": atr,
        "adx_min": adx,
        "use_atr_filter": filt,
        "train_profit_factor": train_pf,
        "test_profit_factor": test_pf,
        "train_return_pct": train_ret,
        "test_return_pct": test_ret,
        "train_sharpe": train_sr,
        "test_sharpe": test_sr,
        "train_avg_r": train_pf / 10.0,
        "train_max_drawdown_pct": train_dd,
    }


def test_grid_counts():
    assert len(list(grid_params({}))) == 792
    assert len(list(grid_params({}, compact=True))) == 90


def test_expected_max_z_and_dsr_haircut():
    assert expected_max_z(1) == 0.0
    assert expected_max_z(792) > expected_max_z(20) > 0.0
    low_n = deflated_sharpe(1.0, 1, 6.0)["dsr"]
    high_n = deflated_sharpe(1.0, 792, 6.0)["dsr"]
    assert high_n < low_n


def test_n_eff_perfect_correlation_is_one_independent_level():
    assert n_eff_from_rho(11, 1.0) == 1.0
    assert n_eff_from_rho(11, 0.0) == 11.0


def test_n_eff_adx_collapses_when_sharpe_is_flat_along_adx():
    rows = []
    for adx in range(15, 26):
        for length in (20, 40, 60):
            rows.append(
                _cell(
                    length,
                    1.5,
                    float(adx),
                    False,
                    train_pf=1.2,
                    test_pf=1.1,
                    train_ret=10.0,
                    test_ret=8.0,
                    train_sr=0.5 + 0.1 * (length / 20.0),
                    test_sr=0.3,
                )
            )
    trials = effective_trials(pd.DataFrame(rows))
    adx = next(ax for ax in trials["axes"] if ax["dim"] == "adx_min")
    assert adx["n_eff"] == 1.0
    assert trials["n_eff"] < len(rows)


def test_pbo_proxy_flags_is_best_below_median_oos():
    grid = pd.DataFrame(
        [
            _cell(20, 1.5, 15, False, 2.0, 0.8, 20, 1, 1.5, -0.4),
            _cell(40, 1.5, 15, False, 1.1, 1.4, 8, 12, 0.4, 0.8),
            _cell(60, 1.5, 15, False, 1.0, 1.3, 7, 11, 0.3, 0.7),
        ]
    )
    selected = select_row(grid, test_pf_floor=0.0)
    assert int(selected["length"]) == 20
    proxy = pbo_proxy(grid, selected)
    assert proxy["below_median"] is True
    assert proxy["rank_pct"] < 0.5


def test_select_row_ignores_test_return():
    grid = pd.DataFrame(
        [
            _cell(20, 1.5, 25, True, 1.64, 1.59, 9.0, 7.1, 0.82, 0.81),
            _cell(25, 1.5, 15, False, 1.35, 1.85, 14.6, 31.0, 0.61, 1.25),
        ]
    )
    picked = select_row(grid, test_pf_floor=1.2)
    assert int(picked["length"]) == 20
    assert bool(picked["use_atr_filter"]) is True


def test_usdjpy_floor_is_stricter():
    assert pf_floor_for("USDJPY") == 1.2
    assert pf_floor_for("USDCAD") == 1.0
