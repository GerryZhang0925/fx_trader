# Review — RSI strategy (TradingView Pine)

> Example output of the **trading-strategy-review** skill. The strategy below is a fabricated
> teaching example. **Not financial advice.**

## Submitted strategy

A user shared this Pine v5 strategy and a Strategy Tester screenshot claiming **profit factor
3.2, win rate 88%, max drawdown 4%** on BTCUSD 15m, tuned on the last 6 months.

```pine
//@version=5
strategy("RSI HTF reversal", overlay=true)

// higher-timeframe RSI for "confirmation"
htfRsi = request.security(syminfo.tickerid, "240",
     ta.rsi(close, 14), lookahead = barmerge.lookahead_on)

rsi = ta.rsi(close, 14)

longCond  = rsi < 27 and htfRsi < 41
shortCond = rsi > 73 and htfRsi > 62

if longCond
    strategy.entry("L", strategy.long)
    strategy.exit("Lx", "L", stop = close * 0.983, limit = close * 1.041)

if shortCond
    strategy.entry("S", strategy.short)
    strategy.exit("Sx", "S", stop = close * 1.017, limit = close * 0.962)
```

---

## Step 1 — Scope & context

| Field | Value |
|---|---|
| Asset / timeframe | BTCUSD, 15m (HTF = 4h) |
| Window / in-sample | Last 6 months, **in-sample** |
| Parameters | RSI thresholds (27/41/73/62) + stop/limit multipliers — **6+ tuned levels** |
| Trials | Not disclosed |
| OOS / walk-forward | None |
| Costs / funding | **None** (perp funding ignored) |

## Step 2/4 — Red-flag quick scan

- 🚩 **`lookahead = barmerge.lookahead_on`** on the HTF RSI — **repainting / look-ahead.**
- 🚩 **Win rate 88%, max DD 4%** — classic repaint/curve-fit signature.
- 🚩 **Curve-fit stop/limit multipliers** (`0.983`, `1.041`, `1.017`, `0.962`).
- 🚩 **No commission/slippage; perpetual funding ignored.**
- 🚩 Tuned on **6 months, no OOS.**

## Findings summary

| ID | Issue | Severity | Where |
|----|-------|----------|-------|
| F1 | Repainting HTF signal via `lookahead_on` | **Critical** | `request.security(... lookahead = barmerge.lookahead_on)` |
| F2 | Curve-fit stop/take-profit multipliers | **High** | `strategy.exit` levels |
| F3 | No costs; perpetual **funding** ignored | **High** | whole script |
| F4 | In-sample only, no walk-forward | **High** | 6-month tune |
| F5 | Intrabar exit fills may be optimistic | **Medium** | `strategy.exit` stop/limit on same bar |
| F6 | Threshold over-parameterization (4 RSI levels) | **Medium** | `longCond` / `shortCond` |

---

## Per-finding detail

### F1 — Repainting HTF signal *(Critical)*
- **Impact:** `lookahead_on` makes `request.security` return the **final** 4h RSI value to
  *every* 15m bar inside that 4h candle — including bars before the 4h candle closed. Historical
  signals use information from the future; the Strategy Tester result is fiction and will not
  reproduce live.
- **How to verify:** Switch to `lookahead_off` with a confirmed-bar offset and reload — the
  backtest will change materially. Or compare to bar-close-only alerts.
- **Fix:**

  ```pine
  // request the PRIOR, fully-closed HTF value; no look-ahead
  htfRsi = request.security(syminfo.tickerid, "240", ta.rsi(close, 14)[1],
       lookahead = barmerge.lookahead_off)
  // and act only on confirmed bars
  if longCond and barstate.isconfirmed
      strategy.entry("L", strategy.long)
  ```

### F2 — Curve-fit stop/take-profit *(High)*
- **Impact:** Levels like `0.983` / `1.041` are oddly specific — they were almost certainly
  swept to dodge the exact historical losers, inflating win rate and shrinking drawdown.
- **How to verify:** Replace with ATR/volatility-based exits chosen a priori and re-test OOS;
  if performance collapses, the levels were fitted.
- **Fix:** Use risk-based exits (e.g. stop = `1.5 * ta.atr(14)`, target at a fixed R multiple)
  defined before testing; validate robustness out-of-sample.

### F3 — Costs & funding ignored *(High)*
- **Impact:** 15m BTC perp trading is high-turnover; commission, spread/slippage, and
  **continuously-paid funding** on the perp can exceed the gross edge — especially for shorts.
- **How to verify:** Add commission + slippage in Strategy Tester properties and subtract
  realistic funding; watch profit factor drop.
- **Fix:** Set commission and slippage; model funding on held positions; recompute net results.

### F4 — In-sample only *(High)*
- **Fix:** Walk-forward across multiple 6-month windows and a different regime (e.g. tune in a
  trending period, test in a chop period); keep a final holdout.

### F5 — Optimistic intrabar fills *(Medium)*
- **Impact:** When stop and limit can both be hit within one bar, the tester may assume the
  favorable one — overstating results.
- **Fix:** Enable conservative intrabar assumptions / use `calc_on_every_tick` carefully, or
  confirm fill priority; require the level to actually trade through.

### F6 — Threshold over-parameterization *(Medium)*
- **Fix:** Reduce to fewer, rounder thresholds (e.g. 30/70) and justify them a priori; deflate
  for the number of threshold combinations tried.

---

## Metrics sanity check

- **Profit factor 3.2 / win rate 88% / max DD 4%:** jointly implausible on 15m BTC; consistent
  with repainting (F1) plus curve-fit exits (F2). Expect a large degradation after the fix.
- **Costs/funding:** results are **gross**; net-of-cost is the only number that matters for a
  high-turnover perp strategy.
- **Deflated Sharpe / PBO:** cannot be computed — return series and **trial count** not provided.
- **Trade count / exposure:** confirm a meaningful number of trades over the 6 months; a few
  lucky reversals can manufacture an 88% win rate.

## Verdict

**Do not deploy.** The repainting HTF signal (**Critical**) alone invalidates the Strategy
Tester output. After fixing F1 (closed-bar HTF + confirmed bars), replacing curve-fit exits with
a-priori risk-based levels, and adding commission/slippage/funding, re-test out-of-sample across
regimes. The realistic edge is likely far smaller — possibly negative.

> **Educational review — not financial advice.** Past backtest performance does not guarantee
> live results. You are solely responsible for your own trading and risk decisions.
