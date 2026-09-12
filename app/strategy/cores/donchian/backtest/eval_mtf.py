"""H1 direction gates on adopted H4 Donchian. Train <2021, test 2021-2025.

Last H1 bar inside each H4 bucket (same resample as feed). No M5. Drop if test PF
falls vs core, or if the 3-pair book yearly/CAGR/DD get worse. Checklist, not a guarantee.
"""

from __future__ import annotations

import json

import pandas as pd

from paths import KIT_DIR, boot

boot()

from account.backtest.run_portfolio import _daily_pnl, _load_pair_params, _portfolio_params  # noqa: E402
from account.metrics import compute_metrics  # noqa: E402
from account.settings import load_config  # noqa: E402
from feed.loader import load_csv  # noqa: E402
from strategy.cores.donchian.backtest.eval_regime import CORE, _metrics  # noqa: E402
from strategy.cores.donchian.backtest.optimize_donchian import TEST_END, TRAIN_END  # noqa: E402
from strategy.cores.donchian import DonchianStrategy  # noqa: E402
from strategy.common.indicators import donchian_prev, ema  # noqa: E402

ROOT = KIT_DIR
FILTERS = ("baseline", "h1_slope_agree", "h1_ema50_side", "h1_ema200_side", "h1_donch_third")


def attach_h1(prepared: pd.DataFrame, h1: pd.DataFrame) -> pd.DataFrame:
    """Map last closed H1 inside each H4 bar. Matches feed resample (label/closed left)."""
    src = h1.copy()
    close = src["close"]
    ema50 = ema(close, 50)
    ema200 = ema(close, 200)
    src["h1_ema50_slope_pct"] = (ema50 - ema50.shift(5)) / ema50.shift(5) * 100.0
    src["h1_above_ema50"] = close > ema50
    src["h1_above_ema200"] = close > ema200
    hi, lo = donchian_prev(src, 20)
    width = (hi - lo).replace(0, pd.NA)
    src["h1_donch_pos"] = (close - lo) / width
    cols = ["h1_ema50_slope_pct", "h1_above_ema50", "h1_above_ema200", "h1_donch_pos"]
    bucketed = src[cols].resample("4h", label="left", closed="left").last()
    out = prepared.copy()
    for col in cols:
        out[col] = bucketed[col].reindex(out.index)
    return out


def apply_h1(prepared: pd.DataFrame, name: str) -> pd.DataFrame:
    out = prepared.copy()
    sig = out["signal"]
    slope = out["h1_ema50_slope_pct"]
    long_ = sig > 0
    short_ = sig < 0
    if name == "baseline":
        keep = sig != 0
    elif name == "h1_slope_agree":
        keep = (long_ & (slope > 0)) | (short_ & (slope < 0))
    elif name == "h1_ema50_side":
        keep = (long_ & out["h1_above_ema50"].eq(True)) | (short_ & out["h1_above_ema50"].eq(False))
    elif name == "h1_ema200_side":
        keep = (long_ & out["h1_above_ema200"].eq(True)) | (short_ & out["h1_above_ema200"].eq(False))
    elif name == "h1_donch_third":
        pos = out["h1_donch_pos"]
        keep = (long_ & (pos > 2.0 / 3.0)) | (short_ & (pos < 1.0 / 3.0))
    else:
        raise ValueError(f"unknown H1 filter {name!r}")
    keep = keep.fillna(False)
    out.loc[~keep, "signal"] = 0
    out.loc[~keep, "reason"] = ""
    return out


def main() -> int:
    cfg = load_config()
    risk = float((cfg.get("portfolio") or {}).get("risk_pct_per_pair", 5.0))
    initial = float(cfg.get("initial_equity", 100000))
    fallback = _portfolio_params(cfg)
    params_dir = ROOT / "params"
    data_dir = ROOT / "data"

    prepared: dict[str, pd.DataFrame] = {}
    for symbol in CORE:
        params, _ = _load_pair_params(symbol, params_dir, fallback)
        h4 = load_csv(data_dir / f"{symbol.lower()}_h4.csv")
        h1 = load_csv(data_dir / f"{symbol.lower()}_h1.csv")
        print(f"prepare {symbol} H4={len(h4)} H1={len(h1)}", flush=True)
        prepared[symbol] = attach_h1(DonchianStrategy(params).prepare(h4), h1)

    rows = []
    book_pnls: dict[str, dict[str, pd.Series]] = {name: {} for name in FILTERS}
    book_trades: dict[str, list[pd.DataFrame]] = {name: [] for name in FILTERS}

    print("\n## Per pair (train <2021 / test 2021-2025)\n", flush=True)
    for symbol in CORE:
        base = prepared[symbol]
        train_mask = base.index < TRAIN_END
        test_mask = (base.index >= TRAIN_END) & (base.index < TEST_END)
        for name in FILTERS:
            framed = apply_h1(base, name)
            for split, mask in (("train", train_mask), ("test", test_mask), ("full", None)):
                eq, trades, m = _metrics(framed, cfg, symbol, risk, mask)
                rows.append(
                    {
                        "symbol": symbol,
                        "filter": name,
                        "split": split,
                        "trades": m.trades,
                        "profit_factor": m.profit_factor,
                        "avg_r": m.avg_r,
                        "max_drawdown_pct": m.max_drawdown_pct,
                        "sharpe": m.sharpe,
                        "return_pct": m.return_pct,
                        "yearly_mean": m.yearly_return_mean,
                    }
                )
                if split == "full":
                    book_pnls[name][symbol] = _daily_pnl(eq)
                    if not trades.empty:
                        book_trades[name].append(trades.assign(symbol=symbol))
            tes = next(r for r in rows[-3:] if r["split"] == "test")
            trn = next(r for r in rows[-3:] if r["split"] == "train")
            print(
                f"  {symbol:7} {name:16} train n={trn['trades']:3} PF={trn['profit_factor']:.3f}  "
                f"test n={tes['trades']:3} PF={tes['profit_factor']:.3f}",
                flush=True,
            )

    print("\n## 3-pair book full sample\n", flush=True)
    books = []
    for name in FILTERS:
        pnl_sum = pd.concat(book_pnls[name], axis=1).fillna(0.0).sum(axis=1)
        eq = (initial + pnl_sum.cumsum()).rename("equity")
        tds = book_trades[name]
        trades = pd.concat(tds, ignore_index=True) if tds else pd.DataFrame()
        if not trades.empty and "exit_time" in trades.columns:
            trades = trades.sort_values("exit_time")
        m = compute_metrics(eq, trades, initial)
        rec = {
            "filter": name,
            "trades": m.trades,
            "profit_factor": m.profit_factor,
            "yearly_mean": m.yearly_return_mean,
            "cagr": m.cagr,
            "max_drawdown_pct": m.max_drawdown_pct,
            "sharpe": m.sharpe,
            "return_pct": m.return_pct,
        }
        books.append(rec)
        print(
            f"  {name:16} n={m.trades:4} PF={m.profit_factor:.3f} year={m.yearly_return_mean:.2%} "
            f"CAGR={m.cagr:.2%} DD={m.max_drawdown_pct:.2f}%",
            flush=True,
        )

    pair_df = pd.DataFrame(rows)
    book_df = pd.DataFrame(books)
    base_test = pair_df[(pair_df["filter"] == "baseline") & (pair_df["split"] == "test")].set_index("symbol")
    base_book = book_df[book_df["filter"] == "baseline"].iloc[0]
    verdicts = []
    for name in FILTERS:
        if name == "baseline":
            continue
        tes = pair_df[(pair_df["filter"] == name) & (pair_df["split"] == "test")].set_index("symbol")
        rec = book_df[book_df["filter"] == name].iloc[0]
        worse = [
            symbol
            for symbol in CORE
            if float(tes.loc[symbol, "profit_factor"]) < float(base_test.loc[symbol, "profit_factor"])
        ]
        test_ok = len(worse) == 0
        book_ok = (
            float(rec["yearly_mean"]) >= float(base_book["yearly_mean"]) - 1e-12
            and float(rec["cagr"]) >= float(base_book["cagr"]) - 1e-12
            and float(rec["max_drawdown_pct"]) <= float(base_book["max_drawdown_pct"]) + 1e-12
        )
        live = test_ok and book_ok
        verdicts.append(
            {
                "filter": name,
                "test_pf_not_below_core": test_ok,
                "book_not_worse": book_ok,
                "live": live,
                "worse_pairs": ",".join(worse) or "",
            }
        )
        print(
            f"  verdict {name}: {'LIVE candidate' if live else 'DROP'} "
            f"(test PF worse: {','.join(worse) or 'none'}; "
            f"book {'ok' if book_ok else 'worse'})",
            flush=True,
        )

    out = ROOT / "reports"
    out.mkdir(parents=True, exist_ok=True)
    pair_df.to_csv(out / "mtf_pairs.csv", index=False)
    book_df.to_csv(out / "mtf_books.csv", index=False)
    payload = {
        "risk_pct": risk,
        "pairs": pair_df.to_dict(orient="records"),
        "books": book_df.to_dict(orient="records"),
        "verdicts": verdicts,
        "note": "H1 last-bar-in-H4. Reject if test PF falls or book yearly/CAGR/DD worsen.",
    }
    (out / "mtf.json").write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    lines = [
        "# H1 alignment on adopted H4 Donchian",
        "",
        f"Risk {risk:g}% per pair. Train <2021, test 2021–2025. Same engine and costs. No M5.",
        "",
        "## Per pair test PF",
        "",
        pair_df[pair_df["split"] == "test"][
            ["symbol", "filter", "trades", "profit_factor", "avg_r", "max_drawdown_pct"]
        ].to_string(index=False),
        "",
        "## Book (full sample)",
        "",
        book_df.to_string(index=False),
        "",
        "## Verdict",
        "",
    ]
    for v in verdicts:
        tag = "LIVE candidate" if v["live"] else "DROP"
        extra = v["worse_pairs"] or ("book worse than core" if not v["book_not_worse"] else "")
        lines.append(f"- {v['filter']}: {tag} {extra}".rstrip())
    lines.append("")
    lines.append("Live only if every pair test PF is not below core AND book yearly/CAGR/DD are not worse.")
    lines.append("Checklist, not a guarantee.")
    lines.append("")
    (out / "mtf.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"\nWrote {out / 'mtf.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
