"""Versioned JSON envelopes and optional signed outbound webhooks."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable
from urllib import error, request

API_VERSION = "2026-09"
DEFAULT_TYPE = "fx_trader.research.completed.v1"


def envelope(data: dict, *, event_type: str = DEFAULT_TYPE, source: str = "fx_trader") -> dict:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {
        "id": str(uuid.uuid4()),
        "type": event_type,
        "source": source,
        "api_version": API_VERSION,
        "time": now,
        "dataContentType": "application/json",
        "data": data,
    }


def sign_payload(secret: str, timestamp: str, delivery_id: str, body: bytes) -> str:
    canonical = f"{timestamp}.{delivery_id}.".encode("utf-8") + body
    return hmac.new(secret.encode("utf-8"), canonical, hashlib.sha256).hexdigest()


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")


def notify(
    cfg: dict | None,
    payload: dict,
    *,
    poster: Callable[[str, dict, bytes], int] | None = None,
) -> dict | None:
    """POST the envelope. No-op unless webhook.url or FX_TRADER_WEBHOOK_URL is set."""
    hook = (cfg or {}).get("webhook") or {}
    url = hook.get("url") or os.environ.get("FX_TRADER_WEBHOOK_URL") or os.environ.get("EURUSD_WEBHOOK_URL")
    if not url:
        return None
    secret = str(
        hook.get("secret")
        or os.environ.get("FX_TRADER_WEBHOOK_SECRET")
        or os.environ.get("EURUSD_WEBHOOK_SECRET")
        or ""
    )
    timeout = float(hook.get("timeout_sec", 5))
    attempts = int(hook.get("max_attempts", 3))
    body = json.dumps(payload, default=str, separators=(",", ":")).encode("utf-8")
    ts = payload.get("time") or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    delivery_id = str(payload.get("id") or uuid.uuid4())
    headers = {
        "Content-Type": "application/json",
        "X-Webhook-Id": delivery_id,
        "X-Webhook-Timestamp": ts,
        "X-Webhook-Event": str(payload.get("type") or DEFAULT_TYPE),
        "X-Idempotency-Key": delivery_id,
    }
    if secret:
        headers["X-Webhook-Signature"] = f"sha256={sign_payload(secret, ts, delivery_id, body)}"

    def _post(target: str, hdrs: dict, raw: bytes) -> int:
        req = request.Request(target, data=raw, headers=hdrs, method="POST")
        with request.urlopen(req, timeout=timeout) as resp:
            return int(resp.status)

    send = poster or _post
    last_err = None
    for i in range(max(attempts, 1)):
        try:
            status = send(url, headers, body)
            return {"ok": 200 <= status < 300, "status": status, "id": delivery_id}
        except (error.URLError, TimeoutError, OSError) as exc:
            last_err = exc
            if i + 1 < attempts:
                time.sleep((2**i) * 0.25)
    return {"ok": False, "status": 0, "id": delivery_id, "error": str(last_err)}
