from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd


from feed.live import (
    find_h4_gaps,
    is_fx_weekend,
    last_closed_h4_open,
    merge_ohlcv,
    next_poll_time,
    retry_call,
)


def test_merge_prefers_new_duplicate():
    idx = pd.date_range("2024-01-01", periods=2, freq="4h", tz="UTC")
    old = pd.DataFrame(
        {"open": [1.0, 1.1], "high": [1.2, 1.2], "low": [0.9, 1.0], "close": [1.1, 1.15], "volume": [1.0, 1.0]},
        index=idx,
    )
    new = old.iloc[[1]].copy()
    new["close"] = 1.17
    out = merge_ohlcv(old, new)
    assert len(out) == 2
    assert float(out.iloc[-1]["close"]) == 1.17


def test_weekend_is_not_a_data_hole():
    idx = pd.to_datetime(
        ["2024-01-05 20:00", "2024-01-07 20:00", "2024-01-08 00:00"],
        utc=True,
    )
    gaps = find_h4_gaps(pd.DatetimeIndex(idx))
    assert gaps == []


def test_weekday_hole_is_a_gap():
    idx = pd.to_datetime(
        ["2024-01-08 00:00", "2024-01-08 04:00", "2024-01-08 12:00"],
        utc=True,
    )
    gaps = find_h4_gaps(pd.DatetimeIndex(idx))
    assert len(gaps) == 1
    assert gaps[0][0] == pd.Timestamp("2024-01-08 04:00", tz="UTC")
    assert gaps[0][1] == pd.Timestamp("2024-01-08 12:00", tz="UTC")


def test_retry_then_succeeds():
    n = {"i": 0}

    def flaky():
        n["i"] += 1
        if n["i"] < 3:
            raise RuntimeError("temp")
        return 7

    waits: list[float] = []
    assert retry_call(flaky, attempts=4, base_wait=1.0, sleeper=waits.append, log=None) == 7
    assert n["i"] == 3
    assert waits == [1.0, 2.0]


def test_last_closed_skips_saturday():
    now = pd.Timestamp("2024-01-06 10:00", tz="UTC")  # Saturday
    bar = last_closed_h4_open(now, lag=pd.Timedelta(minutes=3))
    assert bar.dayofweek == 4
    poll = next_poll_time(now, lag=pd.Timedelta(minutes=3))
    assert poll > now
    assert poll.dayofweek == 0
    assert not is_fx_weekend(poll)


def test_no_fetch_window_on_weekend():
    assert is_fx_weekend(pd.Timestamp("2024-01-06 10:00", tz="UTC"))
    assert is_fx_weekend(pd.Timestamp("2024-01-07 12:00", tz="UTC"))
    assert not is_fx_weekend(pd.Timestamp("2024-01-05 21:00", tz="UTC"))
    fri_night = pd.Timestamp("2024-01-05 21:00", tz="UTC")
    poll = next_poll_time(fri_night, lag=pd.Timedelta(minutes=3))
    assert poll.dayofweek == 0
    assert not is_fx_weekend(poll)
