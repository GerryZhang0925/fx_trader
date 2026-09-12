"""Read-only local HTML for proposals. No login, no orders, bind 127.0.0.1 only."""

from __future__ import annotations

import html
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


def render_html(payload: dict) -> str:
    pairs = payload.get("data", {}).get("pairs") or []
    generated = html.escape(str(payload.get("time") or ""))
    rows = []
    for row in pairs:
        mark = "SIGNAL" if row.get("signal") else "flat"
        lots = row.get("lots")
        size = f"{lots:.4f} lots" if lots is not None else "—"
        rows.append(
            "<tr>"
            f"<td>{html.escape(str(row.get('symbol') or ''))}</td>"
            f"<td>{html.escape(mark)}</td>"
            f"<td>{html.escape(str(row.get('side') or ''))}</td>"
            f"<td>{html.escape(str(row.get('close') or ''))}</td>"
            f"<td>{html.escape(str(row.get('fill_price_if_next_open_equals_close') or '—'))}</td>"
            f"<td>{html.escape(size)}</td>"
            f"<td>{html.escape(str(row.get('risk_pct') or ''))}%</td>"
            f"<td>{html.escape(str(row.get('reason') or ''))}</td>"
            "</tr>"
        )
    table = "\n".join(rows) or "<tr><td colspan='8'>No pairs</td></tr>"
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>Donchian proposals</title>
  <style>
    body {{ font-family: sans-serif; margin: 24px; color: #111; background: #fff; }}
    table {{ border-collapse: collapse; width: 100%; }}
    th, td {{ border: 1px solid #ccc; padding: 8px 10px; text-align: left; }}
    th {{ background: #f4f4f4; }}
    .note {{ color: #444; max-width: 72rem; }}
  </style>
</head>
<body>
  <h1>Donchian proposals</h1>
  <p class="note">Read-only. Next-bar fill estimate. Not advice. Not a broker. Generated {generated}.</p>
  <table>
    <thead>
      <tr>
        <th>Pair</th><th>Mark</th><th>Side</th><th>Close</th>
        <th>Est. fill</th><th>Size</th><th>Risk</th><th>Reason</th>
      </tr>
    </thead>
    <tbody>
      {table}
    </tbody>
  </table>
</body>
</html>
"""


def write_site(payload: dict, out_dir: Path) -> Path:
    web_dir = out_dir / "www"
    web_dir.mkdir(parents=True, exist_ok=True)
    path = web_dir / "index.html"
    path.write_text(render_html(payload), encoding="utf-8")
    return path


def serve(web_dir: Path, host: str = "127.0.0.1", port: int = 8765, *, background: bool = True):
    """Static file server. Host must be loopback."""
    if host not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("web host must be loopback")
    directory = str(web_dir)

    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=directory, **kwargs)

        def log_message(self, fmt, *args):
            return

    httpd = ThreadingHTTPServer((host, int(port)), Handler)
    if background:
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        return httpd
    httpd.serve_forever()
    return httpd
