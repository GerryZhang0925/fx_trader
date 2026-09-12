from __future__ import annotations

import json
import threading
import time
import urllib.request

from output.cores import load_enabled, set_core
from output.web import serve, write_site
from strategy.catalog import cores_map, enabled_cores


def test_yaml_cores_parallel_defaults():
    flags = cores_map({"cores": {"donchian": True, "ema_atr": True}})
    assert flags["donchian"] is True
    assert flags["ema_atr"] is True
    assert flags["killzone"] is False
    assert enabled_cores({"cores": {"ema_atr": True, "donchian": False}}) == ["ema_atr"]


def test_overlay_file_overrides_yaml(tmp_path):
    cfg = {"cores": {"donchian": True, "ema_atr": False}}
    flags = set_core(tmp_path, cfg, "ema_atr", True)
    assert flags["ema_atr"] is True
    assert flags["donchian"] is True
    loaded = load_enabled(tmp_path, cfg)
    assert loaded == flags
    flags = set_core(tmp_path, cfg, "donchian", False)
    assert flags["donchian"] is False
    assert load_enabled(tmp_path, cfg)["donchian"] is False


def test_api_cores_get_and_post(tmp_path):
    cfg = {"cores": {"donchian": True, "ema_atr": False}}
    write_site({"time": "t", "data": {"pairs": [], "cores": cores_map(cfg)}}, tmp_path)
    httpd = serve(tmp_path / "www", host="127.0.0.1", port=0, background=True, cfg=cfg)
    try:
        port = httpd.server_address[1]
        url = f"http://127.0.0.1:{port}/api/cores"
        with urllib.request.urlopen(url, timeout=5) as res:
            body = json.loads(res.read().decode())
        assert body["cores"]["donchian"] is True
        assert body["cores"]["ema_atr"] is False
        req = urllib.request.Request(
            url,
            data=json.dumps({"core": "ema_atr", "enabled": True}).encode(),
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=5) as res:
            body = json.loads(res.read().decode())
        assert body["cores"]["ema_atr"] is True
        assert body["cores"]["donchian"] is True
        assert load_enabled(tmp_path, cfg)["ema_atr"] is True
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_api_cores_post_returns_before_republish(tmp_path):
    started = threading.Event()
    release = threading.Event()

    def slow(_flags):
        started.set()
        release.wait(timeout=5)

    cfg = {"cores": {"donchian": True, "ema_atr": False}}
    write_site({"time": "t", "data": {"pairs": [], "cores": cores_map(cfg)}}, tmp_path)
    httpd = serve(
        tmp_path / "www",
        host="127.0.0.1",
        port=0,
        background=True,
        cfg=cfg,
        on_cores_change=slow,
    )
    try:
        url = f"http://127.0.0.1:{httpd.server_address[1]}/api/cores"
        t0 = time.monotonic()
        req = urllib.request.Request(
            url,
            data=json.dumps({"core": "ema_atr", "enabled": True}).encode(),
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=5) as res:
            body = json.loads(res.read().decode())
        assert time.monotonic() - t0 < 2
        assert body["cores"]["ema_atr"] is True
        assert started.wait(timeout=2)
    finally:
        release.set()
        httpd.shutdown()
        httpd.server_close()
