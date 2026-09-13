from __future__ import annotations

from feed.download import parse_cli_symbols
from feed.pairs import CANDIDATES, RECOMMENDED


def test_download_defaults_to_compared_pairs():
    names = parse_cli_symbols(None, None)
    assert names == CANDIDATES
    assert set(RECOMMENDED) <= set(names)
    for symbol in ("EURUSD", "AUDUSD", "NZDUSD", "USDCHF"):
        assert symbol in names


def test_download_symbol_selects_one_pair():
    assert parse_cli_symbols("usdcad", None) == ["USDCAD"]


def test_download_symbols_overrides_symbol():
    assert parse_cli_symbols("EURUSD", "gbpusd, nzdusd") == ["GBPUSD", "NZDUSD"]
