"""Adopted-param walk-forward as a pre-deploy gate (3y train / 1y test / 1y step)."""

from __future__ import annotations

import json

import pandas as pd

from paths import boot

boot()

from account.backtest.run_portfolio import _load_pair_params, _portfolio_params  # noqa: E402
from account.settings import load_config  # noqa: E402
from feed.loader import load_csv  # noqa: E402
from strategy.backtest.walkforward import iter_windows  # noqa: E402
from strategy.cores.donchian.backtest.eval_regime import CORE, ROOT, _metrics  # noqa: E402
from strategy.cores.donchian import DonchianStrategy  # noqa: E402


def main() -> int:
    cfg = load_config()
    risk = float((cfg.get("portfolio") or {}).get("risk_pct_per_pair", 5.0))
    fallback = _portfolio_params(cfg)
    wf_cfg = cfg.get("walkforward") or {}
    train_years = int(wf_cfg.get("train_years", 3))
    test_years = int(wf_cfg.get("test_years", 1))
    step_years = int(wf_cfg.get("step_years", 1))
    rows = []
    print("## Adopted Donchian walk-forward\n", flush=True)
    for symbol in CORE:
        params, _ = _load_pair_params(symbol, ROOT / "params", fallback)
        h4 = load_csv(ROOT / "data" / f"{symbol.lower()}_h4.csv")
        prepared = DonchianStrategy(params).prepare(h4)
        print(f"{symbol} L={params.length}", flush=True)
        for t0, t1, t2, _tr, te in iter_windows(prepared.index, train_years, test_years, step_years):
            eq, trades, m = _metrics(prepared, cfg, symbol, risk, te)
            row = {
                "symbol": symbol,
                "train_start": str(pd.Timestamp(t0).date()),
                "test_start": str(pd.Timestamp(t1).date()),
                "test_end": str(pd.Timestamp(t2).date()),
                "trades": m.trades,
                "profit_factor": m.profit_factor,
                "max_drawdown_pct": m.max_drawdown_pct,
                "sharpe": m.sharpe,
                "return_pct": m.return_pct,
            }
            rows.append(row)
            print(
                f"  {row['test_start']}→{row['test_end']} n={m.trades:3} PF={m.profit_factor:.3f} "
                f"DD={m.max_drawdown_pct:.1f}%",
                flush=True,
            )
    df = pd.DataFrame(rows)
    gates = []
    for symbol in CORE:
        part = df[df["symbol"] == symbol]
        mean_pf = float(part["profit_factor"].mean()) if len(part) else 0.0
        fail_windows = int((part["profit_factor"] < 1.0).sum())
        ok = mean_pf >= 1.2 and fail_windows == 0
        gates.append({"symbol": symbol, "mean_test_pf": mean_pf, "windows_pf_lt_1": fail_windows, "pass": ok})
        print(f"  gate {symbol}: mean PF={mean_pf:.3f} PF<1 windows={fail_windows} {'PASS' if ok else 'FAIL'}")
    out = ROOT / "reports"
    df.to_csv(out / "walkforward_adopted.csv", index=False)
    payload = {"windows": df.to_dict(orient="records"), "gates": gates, "pass_all": all(g["pass"] for g in gates)}
    (out / "walkforward_adopted.json").write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    lines = [
        "# Adopted-param walk-forward gate",
        "",
        f"{train_years}y train / {test_years}y test / {step_years}y step. Risk {risk:g}% . Pre-deploy: mean window PF ≥ 1.2 and no window PF < 1.0.",
        "",
        df.to_string(index=False),
        "",
        "## Gate",
        "",
    ]
    for g in gates:
        lines.append(
            f"- {g['symbol']}: mean PF {g['mean_test_pf']:.3f}, PF<1 windows={g['windows_pf_lt_1']} "
            f"{'PASS' if g['pass'] else 'FAIL'}"
        )
    lines.append("")
    lines.append(f"All pairs: {'PASS' if payload['pass_all'] else 'FAIL'}")
    lines.append("Checklist, not a guarantee.")
    lines.append("")
    (out / "walkforward_adopted.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {out / 'walkforward_adopted.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
