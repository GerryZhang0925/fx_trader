"""Publish proposals to console, files, Telegram, and local HTML. No orders."""

from __future__ import annotations

from pathlib import Path

from .console import format_text
from .cores import load_enabled
from .reporting import envelope, notify, write_json
from .telegram import send_message
from .web import serve, write_site

EVENT_TYPE = "fx_trader.signal.snapshot.v1"
_SERVER = None


def publish(
    pairs: list[dict],
    cfg: dict,
    out_dir: Path,
    *,
    extra: dict | None = None,
    serve_http: bool = False,
    on_cores_change=None,
) -> dict:
    data = {
        "disclaimer": "Signals only. No broker connection and no order placement.",
        "pairs": pairs,
        **(extra or {}),
        "cores": load_enabled(out_dir, cfg),
    }
    wrapped = envelope(data, event_type=EVENT_TYPE)
    text = format_text(wrapped)
    enabled = set(cfg.get("outputs") or ["console", "files", "telegram", "web"])
    if "console" in enabled:
        print(text, flush=True)
    out_dir.mkdir(parents=True, exist_ok=True)
    if "files" in enabled:
        (out_dir / "signals.md").write_text(text, encoding="utf-8")
        write_json(out_dir / "signals.json", wrapped)
    if "web" in enabled:
        web_cfg = cfg.get("web") or {}
        write_site(wrapped, out_dir, refresh_sec=int(web_cfg.get("refresh_sec") or 20))
    if "telegram" in enabled:
        send_message(text, cfg)
    notify(cfg, wrapped)
    if serve_http:
        global _SERVER
        web_cfg = cfg.get("web") or {}
        host = str(web_cfg.get("host") or "127.0.0.1")
        port = int(web_cfg.get("port") or 18080)
        if _SERVER is None:
            try:
                _SERVER = serve(
                    out_dir / "www",
                    host=host,
                    port=port,
                    background=True,
                    cfg=cfg,
                    on_cores_change=on_cores_change,
                )
                print(f"Local page http://{host}:{port}/", flush=True)
            except OSError as exc:
                print(f"Could not bind http://{host}:{port}/: {exc}", flush=True)
    return wrapped
