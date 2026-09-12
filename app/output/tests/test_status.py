from __future__ import annotations

import pytest

from output.status import load_dashboard, read_events, record, tracked
from output.web import render_html


def test_record_and_dashboard(tmp_path):
    record("app", "offline", "started", "USDCAD,USDJPY", out_dir=tmp_path)
    record("app", "offline", "ok", "USDCAD,USDJPY", out_dir=tmp_path)
    record("feed", "download", "error", "timeout", out_dir=tmp_path)
    events = read_events(tmp_path)
    assert [e["state"] for e in events] == ["started", "ok", "error"]
    dash = load_dashboard(tmp_path)
    assert dash["last_ok"]["module"] == "app"
    assert dash["last_error"]["module"] == "feed"
    assert dash["modules"]["app"]["state"] == "ok"
    assert dash["modules"]["feed"]["state"] == "error"
    html = render_html({"time": "t", "data": {"pairs": []}}, dashboard=dash)
    assert "Run status" in html
    assert "timeout" in html
    assert "USDCAD,USDJPY" in html
    assert (tmp_path / "www" / "index.html").exists()


def test_tracked_records_error(tmp_path):
    with pytest.raises(RuntimeError, match="boom"):
        with tracked("strategy", "optimize", out_dir=tmp_path, message="GBPUSD"):
            raise RuntimeError("boom")
    events = read_events(tmp_path)
    assert events[0]["state"] == "started"
    assert events[-1]["state"] == "error"
    assert "boom" in events[-1]["message"]


def test_read_skips_bad_lines(tmp_path):
    path = tmp_path / "status.jsonl"
    path.write_text("{not json\n{\"module\":\"app\",\"action\":\"x\",\"state\":\"ok\",\"message\":\"ok\",\"time\":\"t\"}\n", encoding="utf-8")
    events = read_events(tmp_path)
    assert len(events) == 1
    assert events[0]["message"] == "ok"


def test_html_without_events_has_idle_cards():
    html = render_html({"time": "t", "data": {"pairs": []}})
    assert "no run yet" in html
    assert "Proposals" in html
