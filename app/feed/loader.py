"""OHLCV loaders. M5 history of 5–10 years must come from CSV (Dukascopy/Histdata)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


OHLCV = ["open", "high", "low", "close", "volume"]


def _normalize(df: pd.DataFrame) -> pd.DataFrame:
    cols = {c.lower(): c for c in df.columns}
    rename = {}
    for name in OHLCV:
        if name in cols:
            rename[cols[name]] = name
        elif name.capitalize() in df.columns:
            rename[name.capitalize()] = name
    if "Adj Close" in df.columns and "close" not in (rename.values()):
        rename["Adj Close"] = "close"
    out = df.rename(columns=rename)
    missing = [c for c in ["open", "high", "low", "close"] if c not in out.columns]
    if missing:
        raise ValueError(f"Missing columns {missing}; have {list(df.columns)}")
    if "volume" not in out.columns:
        out["volume"] = 0.0
    if not isinstance(out.index, pd.DatetimeIndex):
        for cand in ("timestamp", "time", "datetime", "date", "Date"):
            if cand in out.columns:
                out.index = pd.to_datetime(out[cand], utc=True)
                break
        else:
            out.index = pd.to_datetime(out.index, utc=True)
    if out.index.tz is None:
        out.index = out.index.tz_localize("UTC")
    else:
        out.index = out.index.tz_convert("UTC")
    out = out[OHLCV].astype(float).sort_index()
    out = out[~out.index.duplicated(keep="last")]
    return out.dropna(subset=["open", "high", "low", "close"])


def load_csv(path: str | Path) -> pd.DataFrame:
    path = Path(path)
    df = pd.read_csv(path)
    return _normalize(df)


def resample_ohlcv(df: pd.DataFrame, rule: str) -> pd.DataFrame:
    agg = {
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum",
    }
    return df.resample(rule, label="left", closed="left").agg(agg).dropna()


def download_yahoo(symbol: str = "EURUSD=X", interval: str = "1h", period: str = "max") -> pd.DataFrame:
    import yfinance as yf

    raw = yf.download(
        symbol,
        interval=interval,
        period=period,
        auto_adjust=True,
        progress=False,
        threads=False,
    )
    if raw.empty:
        raise RuntimeError(f"yfinance returned no rows for {symbol} {interval}")
    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = [c[0] for c in raw.columns]
    return _normalize(raw)


def load_h4(
    csv_path: str | Path | None = None,
    yahoo: bool = False,
    symbol: str = "EURUSD=X",
) -> pd.DataFrame:
    if csv_path:
        df = load_csv(csv_path)
        inferred = pd.infer_freq(df.index[:50]) or ""
        if inferred and not inferred.lower().startswith("4h") and not inferred.lower().startswith("h4"):
            if df.index.to_series().diff().median() < pd.Timedelta("3h"):
                df = resample_ohlcv(df, "4h")
        return df
    if yahoo:
        hourly = download_yahoo(symbol, interval="1h", period="max")
        return resample_ohlcv(hourly, "4h")
    raise ValueError("Provide csv_path or yahoo=True")


def load_m5(csv_path: str | Path) -> pd.DataFrame:
    df = load_csv(csv_path)
    median = df.index.to_series().diff().median()
    if median and median > pd.Timedelta("6min"):
        raise ValueError(f"Expected M5-ish bars, median delta={median}")
    return df


def make_synthetic(
    n: int = 3000,
    start: str = "2018-01-01",
    freq: str = "4h",
    seed: int = 7,
    trend: float = 0.00002,
    vol: float = 0.0012,
) -> pd.DataFrame:
    """Random-walk OHLCV for unit tests and smoke backtests."""
    rng = np.random.default_rng(seed)
    idx = pd.date_range(start=start, periods=n, freq=freq, tz="UTC")
    noise = rng.normal(trend, vol, n)
    close = 1.10 + np.cumsum(noise)
    high = close + np.abs(rng.normal(0.0004, 0.0003, n))
    low = close - np.abs(rng.normal(0.0004, 0.0003, n))
    open_ = np.r_[close[0], close[:-1]]
    high = np.maximum.reduce([high, open_, close])
    low = np.minimum.reduce([low, open_, close])
    volume = rng.integers(800, 4000, n).astype(float)
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": volume},
        index=idx,
    )
