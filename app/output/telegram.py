"""Official Telegram Bot API sendMessage. Skip when token or chat_id is missing."""

from __future__ import annotations

import json
import os
from urllib import error, parse, request


def send_message(text: str, cfg: dict | None, *, poster=None) -> dict | None:
    tg = (cfg or {}).get("telegram") or {}
    token = str(tg.get("token") or os.environ.get("TELEGRAM_BOT_TOKEN") or "").strip()
    chat_id = tg.get("chat_id") or os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return None
    timeout = float(tg.get("timeout_sec", 10))
    body = parse.urlencode(
        {"chat_id": str(chat_id), "text": text[:3900], "disable_web_page_preview": "true"}
    ).encode("utf-8")
    url = f"https://api.telegram.org/bot{token}/sendMessage"

    def _post(target: str, raw: bytes) -> int:
        req = request.Request(target, data=raw, method="POST")
        with request.urlopen(req, timeout=timeout) as resp:
            return int(resp.status)

    send = poster or _post
    try:
        status = send(url, body)
        return {"ok": 200 <= status < 300, "status": status, "channel": "telegram"}
    except (error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        return {"ok": False, "status": 0, "channel": "telegram", "error": str(exc)}
