"""Closed-bar Donchian proposals. feed → strategy → account → output. No orders."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from paths import boot

boot()

from account.propose import propose, risk_pct_for  # noqa: E402
from account.books import load_venues  # noqa: E402
from account.veto import VetoDedup, evaluate, format_alert, veto_from_cfg  # noqa: E402
from account.settings import (  # noqa: E402
    kit_data_dir,
    kit_params_dir,
    kit_reports_dir,
    load_config,
    parse_symbols,
)
from feed.loader import load_csv  # noqa: E402
from output.cores import load_enabled  # noqa: E402
from output.publish import publish  # noqa: E402
from output.status import record as record_status  # noqa: E402
from output.status import tracked  # noqa: E402
from strategy.common.params import (  # noqa: E402
    portfolio_params,
    prepare_core,
    snapshot_pair,
)


def _log(msg: str) -> None:
    now = pd.Timestamp.now(tz="UTC").strftime("%Y-%m-%d %H:%M:%S UTC")
    print(f"[{now}] {msg}", flush=True)


def _status(out_dir: Path, action: str, state: str, message: str = "") -> None:
    record_status("app", action, state, message, out_dir=out_dir)


def _emit_veto(cfg: dict, out_dir: Path, dedup: VetoDedup, *, spread_pips: float | None = None) -> None:
    """Telegram only when the reject list fires. Does not change signals."""
    from datetime import datetime, timezone

    from output.telegram import send_message

    now = datetime.now(timezone.utc)
    halted = any(v.halted for v in load_venues(cfg).values())
    result = evaluate(
        now,
        spread_pips=spread_pips,
        venue_halted=halted,
        cfg=veto_from_cfg(cfg),
    )
    if not dedup.should_send(result):
        return
    text = format_alert(result, now)
    _log(text.replace("\n", " | "))
    record_status("account", "veto", "ok", result.signature, out_dir=out_dir)
    send_message(text, cfg)


def collect_proposals(
    symbols: list[str],
    data_dir: Path,
    params_dir: Path,
    fallback,
    cfg: dict,
    lookback: int,
    *,
    out_dir: Path | None = None,
    cores: list[str] | None = None,
) -> list[dict]:
    port = cfg.get("portfolio", {})
    if cores is not None:
        names = list(cores)
    else:
        names = [n for n, on in load_enabled(out_dir, cfg).items() if on]
    pairs: list[dict] = []
    for symbol in symbols:
        path = data_dir / f"{symbol.lower()}_h4.csv"
        if not path.exists():
            _log(f"SKIP {symbol}: missing {path}")
            continue
        h4 = load_csv(path)
        for name in names:
            try:
                prepared, params = prepare_core(
                    symbol, h4, core=name, cfg=cfg, params_dir=params_dir, fallback=fallback
                )
            except Exception as exc:  # noqa: BLE001
                _log(f"SKIP {symbol} {name}: {exc}")
                continue
            snap = snapshot_pair(symbol, prepared, params, lookback=lookback, core=name)
            pairs.append(propose(snap, cfg, risk_pct=risk_pct_for(symbol, port)))
    return pairs


def refresh_pairs(symbols: list[str], data_dir: Path, lag: pd.Timedelta) -> list[dict]:
    from feed.live import is_fx_weekend, last_closed_h4_open, retry_call, update_symbol, utc_now

    if is_fx_weekend(utc_now()):
        _log("FX weekend (Sat/Sun UTC): skip download")
        return []

    closed = last_closed_h4_open(lag=lag)
    updates = []
    for symbol in symbols:

        def _one(sym=symbol):
            return update_symbol(sym, data_dir, closed_open=closed, log=_log)

        info = retry_call(_one, attempts=6, base_wait=20.0, cap_wait=300.0, log=_log)
        updates.append(info)
        _log(
            f"{symbol} H4 {info['h4_end']} added={info['h4_added']} "
            f"gaps_left={len(info['gaps_left'])}"
        )
    return updates


def watch_loop(
    symbols: list[str],
    data_dir: Path,
    params_dir: Path,
    fallback,
    cfg: dict,
    out_dir: Path,
    lookback: int,
    lag: pd.Timedelta,
    serve_http: bool,
    sleeper=None,
    on_cores_change=None,
) -> int:
    from feed.live import is_fx_weekend, next_poll_time, utc_now

    sleep = sleeper or __import__("time").sleep
    last_bars: dict[str, str] = {}
    last_flags: dict[str, bool] = {}
    veto_dedup = VetoDedup()
    _log("watch started (signals only, no orders)")
    _status(out_dir, "watch", "started", ",".join(symbols))
    while True:
        try:
            now = utc_now()
            flags = load_enabled(out_dir, cfg)
            if is_fx_weekend(now):
                _log("FX weekend (Sat/Sun UTC): no download")
                snaps = collect_proposals(
                    symbols, data_dir, params_dir, fallback, cfg, lookback, out_dir=out_dir
                )
                if not last_bars or flags != last_flags:
                    publish(
                        snaps,
                        cfg,
                        out_dir,
                        extra={"updates": [], "skipped": "weekend"},
                        serve_http=serve_http,
                        on_cores_change=on_cores_change,
                    )
                    last_bars = {row["symbol"]: row["bar_open_utc"] for row in snaps}
                    last_flags = flags
                    _status(out_dir, "watch", "ok", f"weekend snapshot {len(snaps)} rows")
            else:
                updates = refresh_pairs(symbols, data_dir, lag)
                snaps = collect_proposals(
                    symbols, data_dir, params_dir, fallback, cfg, lookback, out_dir=out_dir
                )
                bars = {row["symbol"]: row["bar_open_utc"] for row in snaps}
                changed = bars != last_bars or flags != last_flags or not last_bars
                if changed:
                    publish(
                        snaps,
                        cfg,
                        out_dir,
                        extra={"updates": updates},
                        serve_http=serve_http,
                        on_cores_change=on_cores_change,
                    )
                    last_bars = bars
                    last_flags = flags
                    _status(out_dir, "watch", "ok", f"published {len(snaps)} rows")
                else:
                    _log("no new H4 bar yet")
            _emit_veto(cfg, out_dir, veto_dedup)
        except KeyboardInterrupt:
            _log("stopped")
            _status(out_dir, "watch", "ok", "stopped")
            return 0
        except Exception as exc:  # noqa: BLE001
            _log(f"cycle failed, will wait then retry: {exc}")
            _status(out_dir, "watch", "error", str(exc))
        nxt = next_poll_time(utc_now(), lag=lag)
        wait = max(5.0, (nxt - utc_now()).total_seconds())
        _log(f"sleep until {nxt} ({wait / 60:.1f} min)")
        try:
            sleep(wait)
        except KeyboardInterrupt:
            _log("stopped")
            _status(out_dir, "watch", "ok", "stopped")
            return 0


def _hold_server(serve_http: bool) -> int:
    """Keep --offline/--once --serve alive; daemon HTTP thread dies with the process."""
    if not serve_http:
        return 0
    _log("serving until Ctrl+C")
    try:
        while True:
            __import__("time").sleep(1.0)
    except KeyboardInterrupt:
        _log("stopped")
        return 0
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Adopted Donchian proposals from H4 CSV. No orders. Default: watch H4 closes."
    )
    p.add_argument("--config", type=Path, default=None)
    p.add_argument("--data", type=Path, default=None)
    p.add_argument("--params-dir", type=Path, default=None)
    p.add_argument("--pairs", default=None)
    p.add_argument("--lookback", type=int, default=None)
    p.add_argument("--out", type=Path, default=None)
    p.add_argument("--once", action="store_true", help="Refresh once, print signals, exit")
    p.add_argument("--offline", action="store_true", help="Do not download; print from CSV only")
    p.add_argument("--lag-sec", type=int, default=None, help="Seconds after H4 close before fetch")
    p.add_argument("--serve", action="store_true", help="Serve reports/www on 127.0.0.1")
    args = p.parse_args(argv)

    cfg = load_config(args.config)
    port = dict(cfg.get("portfolio") or {})
    if cfg.get("pairs"):
        port.setdefault("candidates", cfg["pairs"])
    data_dir = args.data or kit_data_dir(cfg)
    out_dir = args.out or kit_reports_dir(cfg)
    symbols = parse_symbols(args.pairs, port)
    fallback = portfolio_params(cfg)
    params_dir = args.params_dir or kit_params_dir(cfg)
    lookback = int(args.lookback if args.lookback is not None else cfg.get("lookback", 8))
    lag_sec = args.lag_sec if args.lag_sec is not None else int(cfg.get("lag_sec", 180))
    lag = pd.Timedelta(seconds=max(0, lag_sec))
    serve_http = bool(args.serve or cfg.get("serve"))

    def republish(_flags=None):
        snaps = collect_proposals(
            symbols, data_dir, params_dir, fallback, cfg, lookback, out_dir=out_dir
        )
        publish(snaps, cfg, out_dir, serve_http=False)

    hook = republish if serve_http else None

    if args.offline:
        with tracked("app", "offline", out_dir=out_dir, message=",".join(symbols)):
            snaps = collect_proposals(
                symbols, data_dir, params_dir, fallback, cfg, lookback, out_dir=out_dir
            )
            publish(snaps, cfg, out_dir, serve_http=serve_http, on_cores_change=hook)
        return _hold_server(serve_http)
    if args.once:
        with tracked("app", "once", out_dir=out_dir, message=",".join(symbols)):
            updates = refresh_pairs(symbols, data_dir, lag)
            snaps = collect_proposals(
                symbols, data_dir, params_dir, fallback, cfg, lookback, out_dir=out_dir
            )
            publish(
                snaps,
                cfg,
                out_dir,
                extra={"updates": updates},
                serve_http=serve_http,
                on_cores_change=hook,
            )
            _emit_veto(cfg, out_dir, VetoDedup())
        return _hold_server(serve_http)
    return watch_loop(
        symbols,
        data_dir,
        params_dir,
        fallback,
        cfg,
        out_dir,
        lookback,
        lag,
        serve_http,
        on_cores_change=hook,
    )


if __name__ == "__main__":
    raise SystemExit(main())
