from __future__ import annotations

from pathlib import Path

from feed.loader import make_synthetic
from output.web import render_html
from run import collect_proposals  # app/run.py (pytest pythonpath = app)
from strategy.cores.donchian import DonchianParams


def test_offline_pipeline_writes_proposals(tmp_path: Path):
    for symbol in ("USDCAD", "USDJPY", "GBPUSD"):
        df = make_synthetic(n=400, freq="4h", seed=3, trend=0.00004)
        df.to_csv(tmp_path / f"{symbol.lower()}_h4.csv", index_label="timestamp")
    cfg = {
        "initial_equity": 100000.0,
        "cost": {"spread_pips": 1.0, "slippage_pips": 0.2, "lot_size": 100000.0},
        "portfolio": {"candidates": ["USDCAD", "USDJPY", "GBPUSD"], "risk_pct_per_pair": 5.0},
        "donchian": {"use_adx_filter": False, "use_atr_filter": False},
    }
    fallback = DonchianParams(use_adx_filter=False, use_atr_filter=False)
    pairs = collect_proposals(["USDCAD", "USDJPY", "GBPUSD"], tmp_path, tmp_path, fallback, cfg, 4)
    assert [p["symbol"] for p in pairs] == ["USDCAD", "USDJPY", "GBPUSD"]
    assert {p["core"] for p in pairs} == {"donchian"}
    for row in pairs:
        assert "order" not in row
        assert row["risk_pct"] == 5.0
        if row["signal"]:
            assert row["lots"] > 0
    html = render_html({"time": "t", "data": {"pairs": pairs, "cores": {"donchian": True, "ema_atr": False}}})
    assert "USDCAD" in html
    assert "Run status" in html
    assert "Cores" in html
    assert "donchian" in html


def test_parallel_cores_emit_one_row_each(tmp_path: Path):
    for symbol in ("USDCAD", "USDJPY"):
        df = make_synthetic(n=400, freq="4h", seed=3, trend=0.00004)
        df.to_csv(tmp_path / f"{symbol.lower()}_h4.csv", index_label="timestamp")
    cfg = {
        "initial_equity": 100000.0,
        "cost": {"spread_pips": 1.0, "slippage_pips": 0.2, "lot_size": 100000.0},
        "portfolio": {"candidates": ["USDCAD", "USDJPY"], "risk_pct_per_pair": 5.0},
        "donchian": {"use_adx_filter": False, "use_atr_filter": False},
        "cores": {"donchian": True, "ema_atr": True},
    }
    fallback = DonchianParams(use_adx_filter=False, use_atr_filter=False)
    pairs = collect_proposals(["USDCAD", "USDJPY"], tmp_path, tmp_path, fallback, cfg, 4)
    keys = {(p["core"], p["symbol"]) for p in pairs}
    assert keys == {("donchian", "USDCAD"), ("donchian", "USDJPY"), ("ema_atr", "USDCAD"), ("ema_atr", "USDJPY")}
