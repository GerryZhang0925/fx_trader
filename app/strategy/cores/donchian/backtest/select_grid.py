"""Train-period grid selection. Test metrics are a floor, never a sort key."""

from __future__ import annotations

import pandas as pd

DEFAULT_TEST_PF_FLOOR = 1.0
JPY_TEST_PF_FLOOR = 1.2
TRAIN_DD_MAX = 20.0
SORT_TRAIN_ONLY = ("train_profit_factor", "train_avg_r", "train_sharpe")


def as_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and value in (0, 1):
        return bool(value)
    return str(value).strip().lower() in {"1", "true", "t", "yes"}


def pf_floor_for(symbol: str) -> float:
    return JPY_TEST_PF_FLOOR if str(symbol).upper() == "USDJPY" else DEFAULT_TEST_PF_FLOOR


def selection_label(test_pf_floor: float) -> str:
    return (
        f"max train PF among test PF>={test_pf_floor:g} and train DD<={TRAIN_DD_MAX:g}% "
        "(test not in sort)"
    )


def select_row(
    grid: pd.DataFrame,
    *,
    test_pf_floor: float = DEFAULT_TEST_PF_FLOOR,
    max_train_dd: float = TRAIN_DD_MAX,
) -> pd.Series:
    """Max train PF / avg R / Sharpe. Test PF is a filter only."""
    if grid.empty:
        raise ValueError("empty grid")
    robust = grid[
        (grid["test_profit_factor"] >= float(test_pf_floor))
        & (grid["train_max_drawdown_pct"] <= float(max_train_dd))
    ]
    pool = robust if len(robust) else grid
    return pool.sort_values(list(SORT_TRAIN_ONLY), ascending=False).iloc[0]


def select_row_legacy_jpy_return(grid: pd.DataFrame, *, test_pf_floor: float = JPY_TEST_PF_FLOOR) -> pd.Series:
    """Historical USDJPY override: max train+test return among test PF floor. Do not use for new picks."""
    pool = grid[grid["test_profit_factor"] >= float(test_pf_floor)].copy()
    if pool.empty:
        pool = grid.copy()
    pool = pool.copy()
    pool["_sum_return"] = pool["train_return_pct"] + pool["test_return_pct"]
    return pool.sort_values(["_sum_return", "test_profit_factor"], ascending=False).iloc[0]


def match_cell(
    grid: pd.DataFrame,
    *,
    length: int,
    atr_mult: float,
    adx_min: float,
    use_atr_filter: bool,
) -> pd.Series:
    hit = grid[
        (grid["length"].astype(int) == int(length))
        & (grid["atr_mult"].astype(float) == float(atr_mult))
        & (grid["adx_min"].astype(float) == float(adx_min))
        & (grid["use_atr_filter"].map(as_bool) == bool(use_atr_filter))
    ]
    if hit.empty:
        raise KeyError(
            f"no cell length={length} atr_mult={atr_mult} adx_min={adx_min} "
            f"use_atr_filter={use_atr_filter}"
        )
    return hit.iloc[0]


def cell_params(row: pd.Series) -> dict:
    return {
        "length": int(row["length"]),
        "atr_mult": float(row["atr_mult"]),
        "adx_min": float(row["adx_min"]),
        "use_atr_filter": as_bool(row["use_atr_filter"]),
    }
