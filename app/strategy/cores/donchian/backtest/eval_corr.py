"""Rest the weaker pair when 60-day close-return correlation spikes. No 4th pair."""

from __future__ import annotations

import json

import pandas as pd

from paths import KIT_DIR, boot

boot()

from account.backtest.run_portfolio import _daily_pnl, _load_pair_params, _portfolio_params  # noqa: E402
from account.metrics import compute_metrics  # noqa: E402
from account.settings import load_config  # noqa: E402
from feed.loader import load_csv  # noqa: E402
from feed.pairs import pip_size  # noqa: E402
from strategy.cores.donchian.backtest.eval_regime import CORE, ROOT, _metrics  # noqa: E402
from strategy.cores.donchian.backtest.optimize_donchian import TEST_END, TRAIN_END  # noqa: E402
from strategy.cores.donchian import DonchianStrategy  # noqa: E402

THRESH = 0.70
CORR_WIN = 60


def _daily_close(prepared: pd.DataFrame) -> pd.Series:
    s = prepared["close"].copy()
    s.index = pd.DatetimeIndex(s.index).tz_convert("UTC")
    return s.resample("1D").last().dropna()


def attach_corr(prepared_map: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    rets = pd.concat({s: _daily_close(df).pct_change() for s, df in prepared_map.items()}, axis=1)
    roll = rets.rolling(CORR_WIN, min_periods=40).corr()
    out = {s: df.copy() for s, df in prepared_map.items()}
    dates = rets.index
    skip = {s: pd.Series(False, index=dates) for s in CORE}
    for i, day in enumerate(dates):
        if i < 40:
            continue
        mat = roll.xs(day)
        if mat.isna().all().all():
            continue
        hot = []
        for a, b in (("USDCAD", "USDJPY"), ("USDCAD", "GBPUSD"), ("USDJPY", "GBPUSD")):
            val = mat.loc[a, b]
            if pd.notna(val) and float(val) > THRESH:
                hot.append((a, b, float(val)))
        if not hot:
            continue
        # Weaker = more negative 60d return (frozen ranking from past prices only).
        trail = rets.loc[:day].iloc[-CORR_WIN:].sum()
        rest = min({p for pair in hot for p in pair[:2]}, key=lambda s: float(trail.get(s, 0.0)))
        nxt = dates[i + 1] if i + 1 < len(dates) else None
        if nxt is not None:
            skip[rest].loc[nxt] = True
    for symbol, df in out.items():
        days = pd.DatetimeIndex(df.index).tz_convert("UTC").normalize()
        halt_daily = skip[symbol].reindex(days.unique()).fillna(False)
        halt = halt_daily.reindex(days).fillna(False).to_numpy(dtype=bool)
        keep = (df["signal"] != 0).to_numpy() & ~halt
        df.loc[~keep, "signal"] = 0
        df.loc[~keep, "reason"] = ""
    return out


def main() -> int:
    cfg = load_config()
    risk = float((cfg.get("portfolio") or {}).get("risk_pct_per_pair", 5.0))
    initial = float(cfg.get("initial_equity", 100000))
    fallback = _portfolio_params(cfg)
    data_dir = ROOT / "data"
    params_dir = ROOT / "params"
    prepared = {}
    for symbol in CORE:
        params, _ = _load_pair_params(symbol, params_dir, fallback)
        h4 = load_csv(data_dir / f"{symbol.lower()}_h4.csv")
        print(f"prepare {symbol}", flush=True)
        prepared[symbol] = DonchianStrategy(params).prepare(h4)
    gated = attach_corr(prepared)

    rows = []
    books = []
    for label, src in (("baseline", prepared), ("corr_skip", gated)):
        pnls = {}
        tds = []
        print(f"\n## {label}", flush=True)
        for symbol in CORE:
            base = src[symbol]
            train_mask = base.index < TRAIN_END
            test_mask = (base.index >= TRAIN_END) & (base.index < TEST_END)
            for split, mask in (("train", train_mask), ("test", test_mask), ("full", None)):
                eq, trades, m = _metrics(base, cfg, symbol, risk, mask)
                rows.append(
                    {
                        "filter": label,
                        "symbol": symbol,
                        "split": split,
                        "trades": m.trades,
                        "profit_factor": m.profit_factor,
                        "yearly_mean": m.yearly_return_mean,
                        "max_drawdown_pct": m.max_drawdown_pct,
                    }
                )
                if split == "full":
                    pnls[symbol] = _daily_pnl(eq)
                    if not trades.empty:
                        tds.append(trades.assign(symbol=symbol))
                if split == "test":
                    print(f"  {symbol} test n={m.trades} PF={m.profit_factor:.3f}", flush=True)
        pnl_sum = pd.concat(pnls, axis=1).fillna(0.0).sum(axis=1)
        eq = (initial + pnl_sum.cumsum()).rename("equity")
        trades = pd.concat(tds, ignore_index=True) if tds else pd.DataFrame()
        if not trades.empty and "exit_time" in trades.columns:
            trades = trades.sort_values("exit_time")
        m = compute_metrics(eq, trades, initial)
        rec = {
            "filter": label,
            "trades": m.trades,
            "profit_factor": m.profit_factor,
            "yearly_mean": m.yearly_return_mean,
            "cagr": m.cagr,
            "max_drawdown_pct": m.max_drawdown_pct,
            "sharpe": m.sharpe,
        }
        books.append(rec)
        print(
            f"  book n={m.trades} PF={m.profit_factor:.3f} year={m.yearly_return_mean:.2%} "
            f"CAGR={m.cagr:.2%} DD={m.max_drawdown_pct:.2f}%",
            flush=True,
        )

    pair_df = pd.DataFrame(rows)
    book_df = pd.DataFrame(books)
    base_test = pair_df[(pair_df["filter"] == "baseline") & (pair_df["split"] == "test")].set_index("symbol")
    tes = pair_df[(pair_df["filter"] == "corr_skip") & (pair_df["split"] == "test")].set_index("symbol")
    worse = [
        s for s in CORE if float(tes.loc[s, "profit_factor"]) < float(base_test.loc[s, "profit_factor"])
    ]
    base_book = book_df[book_df["filter"] == "baseline"].iloc[0]
    rec = book_df[book_df["filter"] == "corr_skip"].iloc[0]
    book_ok = (
        float(rec["yearly_mean"]) >= float(base_book["yearly_mean"]) - 1e-12
        and float(rec["cagr"]) >= float(base_book["cagr"]) - 1e-12
        and float(rec["max_drawdown_pct"]) <= float(base_book["max_drawdown_pct"]) + 1e-12
    )
    live = (not worse) and book_ok and int(rec["trades"]) != int(base_book["trades"])
    print(f"  verdict corr_skip: {'LIVE candidate' if live else 'DROP'} worse={','.join(worse) or 'none'} book_ok={book_ok}")

    out = ROOT / "reports"
    pair_df.to_csv(out / "corr_pairs.csv", index=False)
    book_df.to_csv(out / "corr_books.csv", index=False)
    payload = {"pairs": pair_df.to_dict(orient="records"), "books": book_df.to_dict(orient="records"), "live": live}
    (out / "corr.json").write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    md = [
        "# Correlation skip on 3-pair book",
        "",
        f"60-day close-return corr > {THRESH:.2f} → rest the weaker pair next day (trailing 60d return). No 4th pair.",
        "",
        pair_df[pair_df["split"] == "test"].to_string(index=False),
        "",
        book_df.to_string(index=False),
        "",
        f"Verdict: {'LIVE candidate' if live else 'DROP'}",
        "",
        "Checklist, not a guarantee.",
        "",
    ]
    (out / "corr.md").write_text("\n".join(md), encoding="utf-8")
    print(f"Wrote {out / 'corr.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
