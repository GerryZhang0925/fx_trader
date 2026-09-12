"""Local HTML for run status, core toggles, and proposals. Loopback only. No orders."""

from __future__ import annotations

import html
import json
import socket
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse


class LoopbackHTTPServer(ThreadingHTTPServer):
    """Refuse a second bind on Windows (SO_REUSEADDR would steal /api/cores)."""

    allow_reuse_address = False

    def server_bind(self):
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


_REPUBLISH = threading.Lock()


def _esc(value) -> str:
    return html.escape("" if value is None else str(value))


def _event_row(event: dict | None, empty: str = "—") -> str:
    if not event:
        return _esc(empty)
    bits = [
        event.get("state") or "",
        event.get("action") or "",
        event.get("time") or "",
    ]
    msg = event.get("message") or ""
    head = " · ".join(_esc(b) for b in bits if b)
    return f"{head}<br/><span class='msg'>{_esc(msg)}</span>" if msg else head


def _cores_panel(cores: dict) -> str:
    cards = []
    for name, on in cores.items():
        state = "on" if on else "off"
        label = "ON" if on else "OFF"
        next_label = "Turn off" if on else "Turn on"
        adopted = " <span class='badge'>adopted book</span>" if name == "donchian" else ""
        cards.append(
            "<article class='card core-card'>"
            f"<h3>{_esc(name)}{adopted}</h3>"
            f"<p class='state {state}'>{label}</p>"
            f"<button type='button' class='core-toggle' data-core='{_esc(name)}' "
            f"data-on='{str(bool(on)).lower()}'>{_esc(next_label)}</button>"
            "</article>"
        )
    if not cards:
        return "<p class='note'>No cores in catalog.</p>"
    return "<div class='grid'>" + "".join(cards) + "</div>"


def render_html(
    payload: dict,
    *,
    dashboard: dict | None = None,
    refresh_sec: int = 20,
) -> str:
    dash = dashboard or {"modules": {}, "last_ok": None, "last_error": None, "events": []}
    data = payload.get("data") or {}
    pairs = data.get("pairs") or []
    cores = data.get("cores") if isinstance(data.get("cores"), dict) else {}
    generated = _esc(payload.get("time") or "")
    rows = []
    for row in pairs:
        mark = "SIGNAL" if row.get("signal") else "flat"
        lots = row.get("lots")
        size = f"{lots:.4f} lots" if lots is not None else "—"
        rows.append(
            "<tr>"
            f"<td>{_esc(row.get('core') or '')}</td>"
            f"<td>{_esc(row.get('symbol'))}</td>"
            f"<td>{_esc(mark)}</td>"
            f"<td>{_esc(row.get('side'))}</td>"
            f"<td>{_esc(row.get('close'))}</td>"
            f"<td>{_esc(row.get('fill_price_if_next_open_equals_close') or '—')}</td>"
            f"<td>{_esc(size)}</td>"
            f"<td>{_esc(row.get('risk_pct'))}%</td>"
            f"<td>{_esc(row.get('reason'))}</td>"
            "</tr>"
        )
    table = "\n".join(rows) or "<tr><td colspan='9'>No pairs</td></tr>"

    modules = dash.get("modules") or {}
    cards = []
    for name in ("app", "feed", "strategy", "account"):
        event = modules.get(name)
        state = (event or {}).get("state") or "idle"
        cards.append(
            "<article class='card'>"
            f"<h3>{_esc(name)}</h3>"
            f"<p class='state {html.escape(str(state))}'>{_esc(state)}</p>"
            f"<p class='detail'>{_event_row(event, 'no run yet')}</p>"
            "</article>"
        )

    log_rows = []
    for event in dash.get("events") or []:
        st = _esc(event.get("state"))
        log_rows.append(
            "<tr>"
            f"<td>{_esc(event.get('time'))}</td>"
            f"<td>{_esc(event.get('module'))}</td>"
            f"<td>{_esc(event.get('action'))}</td>"
            f"<td class='state {st}'>{st}</td>"
            f"<td>{_esc(event.get('message'))}</td>"
            "</tr>"
        )
    log_table = "\n".join(log_rows) or "<tr><td colspan='5'>No runs recorded yet.</td></tr>"
    refresh_ms = int(refresh_sec or 0) * 1000
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>FX Trader dashboard</title>
  <style>
    body {{ font-family: sans-serif; margin: 24px; color: #111; background: #fff; }}
    h1, h2 {{ margin-bottom: 0.4rem; }}
    nav a {{ margin-right: 1rem; }}
    table {{ border-collapse: collapse; width: 100%; margin: 12px 0 28px; }}
    th, td {{ border: 1px solid #ccc; padding: 8px 10px; text-align: left; vertical-align: top; }}
    th {{ background: #f4f4f4; }}
    .note {{ color: #444; max-width: 72rem; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(16rem, 1fr)); gap: 12px; margin: 12px 0 8px; }}
    .card {{ border: 1px solid #ccc; padding: 12px 14px; background: #fafafa; }}
    .card h3 {{ margin: 0 0 6px; font-size: 1rem; }}
    .state {{ font-weight: 700; margin: 0 0 6px; }}
    .state.ok, .state.on {{ color: #0a7a28; }}
    .state.error, .state.off {{ color: #b00020; }}
    .state.started {{ color: #8a5a00; }}
    .state.idle {{ color: #666; }}
    .detail, .msg {{ color: #444; font-size: 0.9rem; }}
    .summary {{ margin: 8px 0 16px; }}
    .badge {{ font-size: 0.75rem; font-weight: 400; color: #444; }}
    button.core-toggle {{ margin-top: 8px; padding: 6px 10px; cursor: pointer; }}
  </style>
</head>
<body>
  <h1>FX Trader</h1>
  <p class="note">Local loopback only. Next-bar fill estimate. Not advice. Not a broker. Toggles change config, not orders. Generated {generated}.</p>
  <nav><a href="#cores">Cores</a><a href="#status">Run status</a><a href="#proposals">Proposals</a></nav>

  <h2 id="cores">Cores</h2>
  <p class="note">Enabled cores run in parallel on each refresh. YAML defaults live in <code>app/strategy/config.yaml</code>; dashboard writes <code>reports/cores.json</code>. Buttons work with <code>--serve</code>.</p>
  {_cores_panel(cores)}

  <h2 id="status">Run status</h2>
  <p class="summary"><strong>Last ok:</strong> {_event_row(dash.get("last_ok"), "none")}</p>
  <p class="summary"><strong>Last error:</strong> {_event_row(dash.get("last_error"), "none")}</p>
  <div class="grid">
    {"".join(cards)}
  </div>
  <table>
    <thead>
      <tr><th>Time (UTC)</th><th>Module</th><th>Action</th><th>State</th><th>Message</th></tr>
    </thead>
    <tbody>
      {log_table}
    </tbody>
  </table>

  <h2 id="proposals">Proposals</h2>
  <table>
    <thead>
      <tr>
        <th>Core</th><th>Pair</th><th>Mark</th><th>Side</th><th>Close</th>
        <th>Est. fill</th><th>Size</th><th>Risk</th><th>Reason</th>
      </tr>
    </thead>
    <tbody>
      {table}
    </tbody>
  </table>
  <script>
    let toggling = false;
    document.querySelectorAll(".core-toggle").forEach(function (btn) {{
      btn.addEventListener("click", async function () {{
        const name = btn.getAttribute("data-core");
        const next = btn.getAttribute("data-on") !== "true";
        btn.disabled = true;
        toggling = true;
        try {{
          const res = await fetch("/api/cores", {{
            method: "POST",
            headers: {{ "Content-Type": "application/json" }},
            body: JSON.stringify({{ core: name, enabled: next }}),
          }});
          if (!res.ok) throw new Error("HTTP " + res.status);
          window.location.reload();
        }} catch (err) {{
          toggling = false;
          btn.disabled = false;
          alert("Toggle needs python run.py --serve on this machine. " + err);
        }}
      }});
    }});
    const refreshMs = {refresh_ms};
    if (refreshMs > 0) {{
      setTimeout(function tick() {{
        if (!toggling) window.location.reload();
        else setTimeout(tick, 1000);
      }}, refreshMs);
    }}
  </script>
</body>
</html>
"""


def write_site(
    payload: dict,
    out_dir: Path,
    *,
    dashboard: dict | None = None,
    refresh_sec: int = 20,
) -> Path:
    if dashboard is None:
        from .status import load_dashboard

        dashboard = load_dashboard(out_dir)
    from .cores import load_enabled

    data = dict(payload.get("data") or {})
    payload = {**payload, "data": {**data, "cores": load_enabled(out_dir, None)}}
    web_dir = out_dir / "www"
    web_dir.mkdir(parents=True, exist_ok=True)
    path = web_dir / "index.html"
    path.write_text(
        render_html(payload, dashboard=dashboard, refresh_sec=refresh_sec),
        encoding="utf-8",
    )
    return path


def refresh_site(out_dir: Path, *, refresh_sec: int = 20) -> Path | None:
    """Rebuild index.html from signals.json + status.jsonl."""
    payload: dict = {"time": "", "data": {"pairs": []}}
    sig = out_dir / "signals.json"
    if sig.exists():
        try:
            loaded = json.loads(sig.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                payload = loaded
        except (OSError, json.JSONDecodeError):
            pass
    from .status import load_dashboard

    return write_site(payload, out_dir, dashboard=load_dashboard(out_dir), refresh_sec=refresh_sec)


def serve(
    web_dir: Path,
    host: str = "127.0.0.1",
    port: int = 18080,
    *,
    background: bool = True,
    cfg: dict | None = None,
    on_cores_change=None,
):
    """Static files plus POST /api/cores. Host must be loopback."""
    if host not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("web host must be loopback")
    directory = str(web_dir)
    out_dir = Path(web_dir).resolve().parent

    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=directory, **kwargs)

        def log_message(self, fmt, *args):
            return

        def end_headers(self):
            self.send_header("Cache-Control", "no-store")
            super().end_headers()

        def _loopback(self) -> bool:
            peer = self.client_address[0] if self.client_address else ""
            return peer in {"127.0.0.1", "::1", "localhost"}

        def _send_json(self, code: int, payload: dict) -> None:
            body = json.dumps(payload).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            path = urlparse(self.path).path
            if path == "/api/cores":
                if not self._loopback():
                    self.send_error(403)
                    return
                from .cores import load_enabled

                self._send_json(200, {"cores": load_enabled(out_dir, cfg)})
                return
            super().do_GET()

        def do_POST(self):
            path = urlparse(self.path).path
            if path != "/api/cores":
                self.send_error(404)
                return
            if not self._loopback():
                self.send_error(403)
                return
            length = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(length) if length else b"{}"
            try:
                body = json.loads(raw.decode("utf-8") or "{}")
            except json.JSONDecodeError:
                self._send_json(400, {"error": "invalid json"})
                return
            name = str(body.get("core") or "")
            if "enabled" not in body:
                self._send_json(400, {"error": "enabled required"})
                return
            from .cores import set_core

            try:
                flags = set_core(out_dir, cfg, name, bool(body.get("enabled")))
            except ValueError as exc:
                self._send_json(400, {"error": str(exc)})
                return
            try:
                refresh_site(out_dir)
            except OSError:
                pass
            if on_cores_change is not None:
                def _after(current=flags):
                    with _REPUBLISH:
                        on_cores_change(current)

                threading.Thread(target=_after, daemon=True).start()
            self._send_json(200, {"cores": flags})

    httpd = LoopbackHTTPServer((host, int(port)), Handler)
    if background:
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        return httpd
    httpd.serve_forever()
    return httpd
