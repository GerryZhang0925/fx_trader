"""Incremental Dukascopy H1/H4 updates, gap fill, and retry. No broker orders."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from .loader import load_csv, resample_ohlcv
from .download import download_h1

OHLCV = ["open", "high", "low", "close", "volume"]
H4 = pd.Timedelta(hours=4)
WEEKEND_MAX = pd.Timedelta(hours=62)


class IncompleteBar(RuntimeError):
    """Feed does not yet include the last closed H4 bar."""


def utc_now() -> pd.Timestamp:
    return pd.Timestamp.now(tz="UTC")


def align_h4(ts: pd.Timestamp) -> pd.Timestamp:
    t = pd.Timestamp(ts)
    if t.tzinfo is None:
        t = t.tz_localize("UTC")
    else:
        t = t.tz_convert("UTC")
    t = t.floor("h")
    return t.replace(minute=0, second=0, microsecond=0) - pd.Timedelta(hours=t.hour % 4)


def is_fx_weekend(ts: pd.Timestamp | None = None) -> bool:
    """Spot FX is closed Saturday and Sunday (UTC calendar)."""
    t = ts if ts is not None else utc_now()
    t = pd.Timestamp(t)
    if t.tzinfo is None:
        t = t.tz_localize("UTC")
    else:
        t = t.tz_convert("UTC")
    return int(t.dayofweek) >= 5


def last_closed_h4_open(now: pd.Timestamp | None = None, lag: pd.Timedelta | None = None) -> pd.Timestamp:
    now = now if now is not None else utc_now()
    lag = lag if lag is not None else pd.Timedelta(minutes=3)
    slot = align_h4(now)
    cand = slot - H4 if now >= slot + lag else slot - 2 * H4
    while True:
        dow = int(cand.dayofweek)
        hour = int(cand.hour)
        if dow == 5 or (dow == 6 and hour < 20):
            cand = cand - H4
            continue
        return cand


def next_poll_time(now: pd.Timestamp | None = None, lag: pd.Timedelta | None = None) -> pd.Timestamp:
    now = now if now is not None else utc_now()
    lag = lag if lag is not None else pd.Timedelta(minutes=3)
    t = align_h4(now) + H4 + lag
    if t <= now:
        t = t + H4
    for _ in range(48):
        bar_open = t - lag - H4
        dow = int(bar_open.dayofweek)
        hour = int(bar_open.hour)
        if dow == 5 or (dow == 6 and hour < 20) or t <= now or is_fx_weekend(t):
            t = t + H4
            continue
        return t
    return t


def is_weekend_gap(prev: pd.Timestamp, nxt: pd.Timestamp) -> bool:
    delta = nxt - prev
    if delta <= H4:
        return False
    if delta > WEEKEND_MAX:
        return False
    return int(prev.dayofweek) >= 4 and int(nxt.dayofweek) in (5, 6, 0)


def find_h4_gaps(index: pd.DatetimeIndex, min_hole: pd.Timedelta | None = None) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    min_hole = min_hole if min_hole is not None else pd.Timedelta(hours=5)
    if index is None or len(index) < 2:
        return []
    idx = pd.DatetimeIndex(index).tz_convert("UTC").sort_values()
    gaps: list[tuple[pd.Timestamp, pd.Timestamp]] = []
    diffs = pd.Series(idx, index=idx).diff()
    for ts, delta in diffs.items():
        if pd.isna(delta) or delta <= min_hole:
            continue
        prev = ts - delta
        if is_weekend_gap(prev, ts):
            continue
        gaps.append((pd.Timestamp(prev), pd.Timestamp(ts)))
    return gaps


def merge_ohlcv(old: pd.DataFrame | None, new: pd.DataFrame | None) -> pd.DataFrame:
    frames = [f[OHLCV] for f in (old, new) if f is not None and not f.empty]
    if not frames:
        return pd.DataFrame(columns=OHLCV)
    out = pd.concat(frames).sort_index()
    out = out[~out.index.duplicated(keep="last")]
    return out.dropna(subset=["open", "high", "low", "close"])


def write_ohlcv(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    out = df[OHLCV].sort_index().copy()
    out.index.name = "timestamp"
    out.to_csv(path)


def load_optional(path: Path) -> pd.DataFrame:
    if not path.exists() or path.stat().st_size == 0:
        return pd.DataFrame(columns=OHLCV)
    return load_csv(path)


def retry_call(fn, *, attempts: int = 6, base_wait: float = 15.0, cap_wait: float = 300.0, sleeper=None, log=None):
    sleep = sleeper or __import__("time").sleep
    last_err: Exception | None = None
    for i in range(attempts):
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            wait = min(cap_wait, base_wait * (2**i))
            if log:
                log(f"retry {i + 1}/{attempts} in {wait:.0f}s: {exc}")
            if i + 1 < attempts:
                sleep(wait)
    raise RuntimeError(f"failed after {attempts} attempts: {last_err}") from last_err


def _iso(ts: pd.Timestamp) -> str:
    t = pd.Timestamp(ts)
    if t.tzinfo is not None:
        t = t.tz_convert("UTC").tz_localize(None)
    return t.strftime("%Y-%m-%dT%H:%M:%S")


def fetch_h1_window(symbol: str, start: pd.Timestamp, end: pd.Timestamp, cache_dir: Path | None, log=None) -> pd.DataFrame:
    def _log(msg: str) -> None:
        if log:
            log(msg)

    _log(f"{symbol} fetch H1 {_iso(start)} -> {_iso(end)}")
    return download_h1(
        symbol,
        start=_iso(start),
        end=_iso(end),
        cache_dir=cache_dir,
        quiet=True,
        use_cache=True,
    )


def update_symbol(
    symbol: str,
    data_dir: Path,
    *,
    closed_open: pd.Timestamp | None = None,
    overlap: pd.Timedelta | None = None,
    log=None,
) -> dict:
    """Download from last bar (and any holes) through the last closed H4, then save H1/H4."""
    overlap = overlap if overlap is not None else pd.Timedelta(days=2)
    closed_open = closed_open if closed_open is not None else last_closed_h4_open()
    h1_path = data_dir / f"{symbol.lower()}_h1.csv"
    h4_path = data_dir / f"{symbol.lower()}_h4.csv"
    cache_dir = data_dir / "cache"
    old_h1 = load_optional(h1_path)
    old_h4 = load_optional(h4_path)
    windows: list[tuple[pd.Timestamp, pd.Timestamp]] = []
    end = closed_open + H4 - pd.Timedelta(seconds=1)
    if old_h4.empty and old_h1.empty:
        windows.append((pd.Timestamp("2015-01-01", tz="UTC"), end))
    else:
        last = old_h1.index.max() if not old_h1.empty else old_h4.index.max()
        windows.append((pd.Timestamp(last) - overlap, end))
        for a, b in find_h4_gaps(old_h4.index):
            windows.append((a, b))

    fetched = []
    for start, stop in windows:
        if stop <= start:
            continue
        chunk = fetch_h1_window(symbol, start, stop, cache_dir, log=log)
        if chunk is not None and not chunk.empty:
            fetched.append(chunk)

    new_h1 = merge_ohlcv(old_h1, pd.concat(fetched) if fetched else None)
    if new_h1.empty:
        raise RuntimeError(f"{symbol}: download returned no H1 bars")
    new_h4 = resample_ohlcv(new_h1, "4h")
    remaining = find_h4_gaps(new_h4.index)
    extra = []
    for a, b in remaining:
        extra.append(fetch_h1_window(symbol, a, b, cache_dir, log=log))
    if extra:
        new_h1 = merge_ohlcv(new_h1, pd.concat(extra))
        new_h4 = resample_ohlcv(new_h1, "4h")
        remaining = find_h4_gaps(new_h4.index)

    if closed_open not in new_h4.index and utc_now() >= closed_open + H4:
        # Weekend: last closed may be Friday while closed_open is Saturday slot
        if closed_open.dayofweek < 5 and (new_h4.index.max() < closed_open):
            raise IncompleteBar(f"{symbol}: missing closed H4 {closed_open}")

    write_ohlcv(new_h1, h1_path)
    write_ohlcv(new_h4, h4_path)
    added = 0 if old_h4.empty else int((~new_h4.index.isin(old_h4.index)).sum())
    return {
        "symbol": symbol,
        "h1_bars": int(len(new_h1)),
        "h4_bars": int(len(new_h4)),
        "h4_start": str(new_h4.index.min()),
        "h4_end": str(new_h4.index.max()),
        "h4_added": added if not old_h4.empty else int(len(new_h4)),
        "gaps_left": [(str(a), str(b)) for a, b in remaining],
        "h1_path": str(h1_path),
        "h4_path": str(h4_path),
    }
