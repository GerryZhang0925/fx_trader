from __future__ import annotations

from output.console import format_text
from output.publish import publish
from output.telegram import send_message
from output.web import render_html, write_site


def _payload():
    return {
        "time": "2026-09-12T00:00:00Z",
        "data": {
            "pairs": [
                {
                    "symbol": "USDCAD",
                    "signal": 1,
                    "side": "long",
                    "close": 1.35,
                    "adx": 22,
                    "ema_trend": 1.34,
                    "donch_hi": 1.36,
                    "donch_lo": 1.33,
                    "reason": "donchian_long",
                    "stop_dist": 0.005,
                    "fill_price_if_next_open_equals_close": 1.35012,
                    "stop_price_if_filled_at_close": 1.345,
                    "partial_1r_if_filled_at_close": 1.355,
                    "lots": 1.1,
                    "units": 110000,
                    "risk_pct": 5.5,
                    "equity": 100000,
                    "spread_pips": 1.0,
                    "slippage_pips": 0.2,
                    "trail_atr_mult": 3.0,
                    "partial_frac": 0.5,
                    "partial_r": 1.0,
                    "bar_open_utc": "2026-08-31 20:00:00+00:00",
                    "bar_open_jst": "2026-09-01 05:00:00+09:00",
                    "recent_signals": [],
                }
            ]
        },
    }


def test_html_and_markdown_contain_pair(tmp_path):
    payload = _payload()
    html = render_html(payload)
    assert "USDCAD" in html
    assert "1.1000 lots" in html
    text = format_text(payload)
    assert "USDCAD" in text
    assert "no orders" in text.lower() or "Not a broker" in text
    path = write_site(payload, tmp_path)
    assert path.exists()
    wrapped = publish(payload["data"]["pairs"], {"outputs": ["files", "web"]}, tmp_path)
    assert (tmp_path / "signals.json").exists()
    assert (tmp_path / "www" / "index.html").exists()
    assert wrapped["data"]["pairs"][0]["symbol"] == "USDCAD"


def test_telegram_skips_without_token():
    assert send_message("hello", {"telegram": {"chat_id": None}}) is None
