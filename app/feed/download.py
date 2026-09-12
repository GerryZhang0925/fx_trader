"""Download ~10 years of EURUSD H1 from Dukascopy and compile H4 CSV.

Uses the public datafeed (no API key). Prices are bid OHLC; the backtest engine
still applies spread/slippage, so costs are slightly conservative.
"""

from __future__ import annotations

import argparse
import lzma
import struct
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from .loader import resample_ohlcv

CANDLE_FMT = ">IIIIIf"
CANDLE_SIZE = struct.calcsize(CANDLE_FMT)
POINT_VALUE = {
    "EURUSD": 100000.0,
    "GBPUSD": 100000.0,
    "AUDUSD": 100000.0,
    "NZDUSD": 100000.0,
    "USDCAD": 100000.0,
    "USDCHF": 100000.0,
    "USDJPY": 1000.0,
    "XAUUSD": 1000.0,
}
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.dukascopy.com/",
    "Accept": "*/*",
}


def month_url(symbol: str, year: int, month0: int, price: str = "BID") -> str:
    # Month in the path is 0-indexed (January = 00). HTTP avoids TLS 503s seen on https.
    return (
        f"http://datafeed.dukascopy.com/datafeed/{symbol}/{year}/"
        f"{month0:02d}/{price}_candles_hour_1.bi5"
    )


def fetch_bytes(url: str, retries: int = 8, timeout: int = 60) -> bytes:
    last_err: Exception | None = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except urllib.error.HTTPError as exc:
            last_err = exc
            if exc.code in {404, 400}:
                return b""
            time.sleep(min(30.0, 2.0 ** attempt))
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            time.sleep(min(30.0, 2.0 ** attempt))
    raise RuntimeError(f"Failed {url}: {last_err}")


def parse_h1_month(blob: bytes, year: int, month1: int, point_value: float) -> pd.DataFrame:
    if not blob:
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
    raw = lzma.decompress(blob)
    if len(raw) % CANDLE_SIZE != 0:
        raise ValueError(f"Unexpected bi5 size {len(raw)} for {year}-{month1:02d}")
    month_start = datetime(year, month1, 1, tzinfo=timezone.utc)
    rows = []
    for offset in range(0, len(raw), CANDLE_SIZE):
        sec, o, h, l, c, vol = struct.unpack_from(CANDLE_FMT, raw, offset)
        ts = pd.Timestamp(month_start) + pd.Timedelta(seconds=int(sec))
        rows.append(
            (
                ts,
                o / point_value,
                h / point_value,
                l / point_value,
                c / point_value,
                float(vol),
            )
        )
    df = pd.DataFrame(rows, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df = df.set_index("timestamp").sort_index()
    # Weekend / holiday placeholders are flat with zero volume
    live = (df["volume"] > 0) | (df["high"] > df["low"])
    return df.loc[live]


def month_iter(start: datetime, end: datetime):
    y, m = start.year, start.month
    while datetime(y, m, 1) <= datetime(end.year, end.month, 1):
        yield y, m
        m += 1
        if m == 13:
            y, m = y + 1, 1


def download_h1(
    symbol: str = "EURUSD",
    start: str = "2016-01-01",
    end: str | None = None,
    price: str = "BID",
    cache_dir: Path | None = None,
    *,
    quiet: bool = False,
    use_cache: bool = True,
) -> pd.DataFrame:
    def log(msg: str) -> None:
        if not quiet:
            print(msg, flush=True)

    start_dt = datetime.fromisoformat(start) if isinstance(start, str) else start
    if getattr(start_dt, "tzinfo", None) is not None:
        start_dt = start_dt.replace(tzinfo=None)
    if end is None:
        end_dt = datetime.now(timezone.utc).replace(tzinfo=None)
    elif isinstance(end, str):
        end_dt = datetime.fromisoformat(end)
        if end_dt.tzinfo is not None:
            end_dt = end_dt.replace(tzinfo=None)
    else:
        end_dt = end.replace(tzinfo=None) if getattr(end, "tzinfo", None) else end
    pv = POINT_VALUE.get(symbol.upper(), 100000.0)
    frames = []
    months = list(month_iter(start_dt, end_dt))
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    if cache_dir:
        cache_dir.mkdir(parents=True, exist_ok=True)
    for i, (year, month1) in enumerate(months, start=1):
        url = month_url(symbol.upper(), year, month1 - 1, price)
        cache_path = None
        if cache_dir:
            cache_path = cache_dir / f"{symbol.upper()}_{price}_{year}{month1:02d}.bi5"
        recent = (year, month1) >= (now.year, now.month) or (
            now.month == 1 and year == now.year - 1 and month1 == 12
        ) or (year == now.year and month1 == now.month - 1)
        allow_cache = bool(use_cache and cache_path is not None and not recent)
        log(f"[{i}/{len(months)}] {year}-{month1:02d}")
        if allow_cache and cache_path.exists() and cache_path.stat().st_size > 0:
            blob = cache_path.read_bytes()
            log(f"  cache {cache_path.name} ({len(blob)} bytes)")
            from_cache = True
        else:
            blob = fetch_bytes(url)
            from_cache = False
            if cache_path is not None and blob and allow_cache:
                cache_path.write_bytes(blob)
        month_df = parse_h1_month(blob, year, month1, pv)
        if month_df.empty:
            log(f"  empty ({len(blob)} bytes)")
        else:
            log(f"  {len(month_df)} H1 bars")
            frames.append(month_df)
        time.sleep(0.05 if from_cache else 0.25)
    if not frames:
        raise RuntimeError("No H1 bars downloaded")
    h1 = pd.concat(frames).sort_index()
    h1 = h1[~h1.index.duplicated(keep="last")]
    start_ts = pd.Timestamp(start_dt).tz_localize("UTC")
    end_ts = pd.Timestamp(end_dt)
    if end_ts.tzinfo is None:
        end_ts = end_ts.tz_localize("UTC")
    return h1.loc[(h1.index >= start_ts) & (h1.index <= end_ts)]


def main(argv: list[str] | None = None) -> int:
    root = Path(__file__).resolve().parents[2]
    p = argparse.ArgumentParser(description="Download FX H1 from Dukascopy and write H4 CSV")
    p.add_argument("--symbol", default="EURUSD")
    p.add_argument("--symbols", default=None, help="Comma-separated list, overrides --symbol")
    p.add_argument("--start", default="2015-01-01")
    p.add_argument("--end", default=None)
    p.add_argument("--out-h1", type=Path, default=None)
    p.add_argument("--out-h4", type=Path, default=None)
    args = p.parse_args(argv)

    data_dir = root / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    symbols = [s.strip().upper() for s in (args.symbols or args.symbol).split(",") if s.strip()]
    from output.status import tracked

    with tracked("feed", "download", out_dir=root / "reports", message=",".join(symbols)):
        for symbol in symbols:
            h1_path = args.out_h1 or (data_dir / f"{symbol.lower()}_h1.csv")
            h4_path = args.out_h4 or (data_dir / f"{symbol.lower()}_h4.csv")
            print(f"=== {symbol} ===", flush=True)
            h1 = download_h1(symbol, args.start, args.end, cache_dir=data_dir / "cache")
            h4 = resample_ohlcv(h1, "4h")
            h1.to_csv(h1_path, index_label="timestamp")
            h4.to_csv(h4_path, index_label="timestamp")
            span = (h4.index[-1] - h4.index[0]).days / 365.25
            print(f"H1 {len(h1)} bars -> {h1_path}")
            print(f"H4 {len(h4)} bars, {span:.2f} years, {h4.index[0]} -> {h4.index[-1]}")
            print(f"Wrote {h4_path}")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
