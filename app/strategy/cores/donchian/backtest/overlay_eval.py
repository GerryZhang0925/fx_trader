"""Shared overlay runner: train <2021 / test 2021-2025, book yearly/CAGR/DD gate."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import pandas as pd

from account.backtest.run_portfolio import _daily_pnl, _load_pair_params, _portfolio_params
from account.metrics import compute_metrics
from account.settings import load_config
from feed.loader import load_csv
from strategy.cores.donchian.backtest.eval_regime import CORE, ROOT, _metrics
from strategy.cores.donchian.backtest.optimize_donchian import TEST_END, TRAIN_END
from strategy.cores.donchian import DonchianStrategy

AttachFn = Callable[[str, pd.DataFrame, Path], pd.DataFrame]
ApplyFn = Callable[[pd.DataFrame, str], pd.DataFrame]


def gate_signals(prepared: pd.DataFrame, keep: pd.Series) -> pd.DataFrame:
    out = prepared.copy()
    keep = keep.fillna(False)
    out.loc[~keep, "signal"] = 0
    out.loc[~keep, "reason"] = ""
    return out


def run_overlay(
    *,
    filters: tuple[str, ...],
    attach: AttachFn,
    apply_fn: ApplyFn,
    report_stem: str,
    title: str,
    note: str,
) -> int:
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
        print(f"prepare {symbol} L={params.length} n={len(h4)}", flush=True)
        prepared[symbol] = attach(symbol, DonchianStrategy(params).prepare(h4), data_dir)

    rows: list[dict] = []
    book_pnls: dict[str, dict[str, pd.Series]] = {name: {} for name in filters}
    book_trades: dict[str, list[pd.DataFrame]] = {name: [] for name in filters}

    print("\n## Per pair (train <2021 / test 2021-2025)\n", flush=True)
    for symbol in CORE:
        base = prepared[symbol]
        train_mask = base.index < TRAIN_END
        test_mask = (base.index >= TRAIN_END) & (base.index < TEST_END)
        for name in filters:
            framed = apply_fn(base, name)
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
    for name in filters:
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
    for name in filters:
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
        same_book = (
            int(rec["trades"]) == int(base_book["trades"])
            and abs(float(rec["yearly_mean"]) - float(base_book["yearly_mean"])) < 1e-12
            and abs(float(rec["cagr"]) - float(base_book["cagr"])) < 1e-12
            and abs(float(rec["max_drawdown_pct"]) - float(base_book["max_drawdown_pct"])) < 1e-12
        )
        book_ok = (
            float(rec["yearly_mean"]) >= float(base_book["yearly_mean"]) - 1e-12
            and float(rec["cagr"]) >= float(base_book["cagr"]) - 1e-12
            and float(rec["max_drawdown_pct"]) <= float(base_book["max_drawdown_pct"]) + 1e-12
        )
        live = test_ok and book_ok and not same_book
        verdicts.append(
            {
                "filter": name,
                "test_pf_not_below_core": test_ok,
                "book_not_worse": book_ok,
                "same_as_core": same_book,
                "live": live,
                "worse_pairs": ",".join(worse) or "",
            }
        )
        why = []
        if worse:
            why.append(",".join(worse))
        if same_book:
            why.append("no-op vs core")
        elif not book_ok:
            why.append("book worse than core")
        print(
            f"  verdict {name}: {'LIVE candidate' if live else 'DROP'} "
            f"({'; '.join(why) or 'held'})",
            flush=True,
        )

    out = ROOT / "reports"
    out.mkdir(parents=True, exist_ok=True)
    pair_df.to_csv(out / f"{report_stem}_pairs.csv", index=False)
    book_df.to_csv(out / f"{report_stem}_books.csv", index=False)
    payload = {
        "risk_pct": risk,
        "pairs": pair_df.to_dict(orient="records"),
        "books": book_df.to_dict(orient="records"),
        "verdicts": verdicts,
        "note": note,
    }
    (out / f"{report_stem}.json").write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    lines = [
        f"# {title}",
        "",
        f"Risk {risk:g}% per pair. Train <2021, test 2021–2025. Same engine and costs.",
        "",
        note,
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
        extra = v["worse_pairs"] or (
            "no-op vs core" if v["same_as_core"] else ("book worse than core" if not v["book_not_worse"] else "")
        )
        lines.append(f"- {v['filter']}: {tag} {extra}".rstrip())
    lines.append("")
    lines.append("Live only if test PF holds, book yearly/CAGR/DD are not worse, and the overlay is not a no-op.")
    lines.append("Checklist, not a guarantee.")
    lines.append("")
    path = out / f"{report_stem}.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nWrote {path}")
    return 0
