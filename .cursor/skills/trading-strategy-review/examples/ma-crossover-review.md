# Review — MA Crossover backtest (Python)

> Example output of the **trading-strategy-review** skill. The strategy below is a fabricated
> teaching example. **Not financial advice.**

## Submitted strategy

A user shared this `backtest.py` and a results table claiming **Sharpe 4.1, CAGR 38%, max
drawdown 6%, win rate 71%** on daily SPY, 2015–2023, with "best parameters found by grid
search."

```python
import pandas as pd

df = pd.read_csv("spy_daily.csv", parse_dates=["date"]).set_index("date")

# grid-searched best params
FAST, SLOW = 7, 23

df["fast"] = df["close"].rolling(FAST).mean()
df["slow"] = df["close"].rolling(SLOW).mean()
df["signal"] = (df["fast"] > df["slow"]).astype(int)

# returns
df["ret"] = df["signal"] * df["close"].pct_change()
equity = (1 + df["ret"]).cumprod()

sharpe = df["ret"].mean() / df["ret"].std() * (252 ** 0.5)
print("Sharpe:", round(sharpe, 2))
```

---

## Step 1 — Scope & context

| Field | Value |
|---|---|
| Asset / timeframe | SPY, daily bars |
| Window / in-sample | 2015–2023, **entirely in-sample** |
| Parameters | 2 (fast, slow) + the grid that selected them |
| Trials | Grid search — **count not disclosed** |
| OOS / walk-forward | **None** |
| Live/paper | None |
| Costs modeled | **None** |

## Step 2/4 — Red-flag quick scan

- 🚩 **Sharpe 4.1 on daily data** — physically implausible for a 2-MA SPY strategy.
- 🚩 **Max drawdown 6%** during a window that includes the **2020 COVID crash** — impossible
  for a long-only equity strategy that holds through it.
- 🚩 **No transaction costs.**
- 🚩 **`signal * pct_change()` on the same row** — uses the same bar's close to both decide and
  realize the return (look-ahead).
- 🚩 **Best grid params reported, trial count hidden** (multiple testing).

## Findings summary

| ID | Issue | Severity | Where |
|----|-------|----------|-------|
| F1 | Look-ahead: return uses the same-bar signal/close | **Critical** | `backtest.py` line `df["ret"] = df["signal"] * df["close"].pct_change()` |
| F2 | No transaction costs / slippage | **Critical** | whole file (no cost term) |
| F3 | Parameters grid-searched in-sample, no OOS/walk-forward | **Critical** | `FAST, SLOW = 7, 23` |
| F4 | Multiple testing — trial count undisclosed, only best reported | **High** | grid search |
| F5 | Single regime risk / drawdown implausibly small | **High** | results table (6% DD across 2020) |
| F6 | Metrics not net-of-cost; Sharpe scaling unverified | **Medium** | `sharpe = ...` |

---

## Per-finding detail

### F1 — Look-ahead bias *(Critical)*
- **Impact:** The signal computed from bar *t*'s close is multiplied by bar *t*'s own return.
  In practice you cannot know the close-based crossover until the bar has closed, yet the code
  credits you with that bar's full move. This is the primary source of the 4.1 Sharpe.
- **How to verify:** Lag the signal by one bar and re-run. If the Sharpe collapses, this was
  the cause (it will).
- **Fix:**

  ```python
  # decide on bar t (closed), act on bar t+1
  df["position"] = df["signal"].shift(1)
  df["ret"] = df["position"] * df["close"].pct_change()
  ```

### F2 — No transaction costs *(Critical)*
- **Impact:** Every crossover flip is free. With realistic costs the thin edge of a 2-MA
  system on SPY largely disappears.
- **How to verify:** Add a per-turnover cost and watch net Sharpe drop.
- **Fix:**

  ```python
  COST_BPS = 3  # commission + half-spread + slippage, round trip
  df["turnover"] = df["position"].diff().abs()
  df["net_ret"] = df["ret"] - df["turnover"] * (COST_BPS / 1e4)
  ```

### F3 — In-sample tuning, no OOS *(Critical)*
- **Impact:** `7/23` were chosen because they looked best on 2015–2023; the reported number is
  the *maximum* over the grid, not an estimate of the future.
- **How to verify:** Hold out 2022–2023, tune only on 2015–2021, evaluate on the holdout.
- **Fix:** Walk-forward — anchored tune windows, evaluate on the next untouched window;
  concatenate OOS segments for an honest curve; keep a final lockbox.

### F4 — Multiple testing *(High)*
- **Impact:** Across an undisclosed number of (fast, slow) pairs, a Sharpe near 2 in-sample is
  expected by chance alone.
- **How to verify:** Report the trial count and compute the **Deflated Sharpe Ratio**; compute
  **PBO** via CSCV (> 0.5 ⇒ overfit).
- **Fix:** Disclose trials, deflate the Sharpe, prefer few round parameters.

### F5 — Drawdown implausible / regime *(High)*
- **Impact:** A 6% max drawdown across the 2020 crash signals either look-ahead (F1) or a
  curve fit that dodged the crash specifically.
- **How to verify:** Plot the **net, lagged** equity curve through Feb–Mar 2020.
- **Fix:** Re-measure max drawdown on the corrected net curve; test across bull/bear/high-vol
  regimes.

### F6 — Metrics not net-of-cost *(Medium)*
- **Fix:** Recompute Sharpe/Sortino/max-DD on `net_ret`, confirm √252 annualization, and report
  trade count and exposure.

---

## Metrics sanity check

- **Sharpe 4.1:** not credible for daily SPY with two moving averages; expected to fall to ~0
  once F1 (lag) and F2 (costs) are fixed.
- **Max drawdown 6%:** inconsistent with holding SPY through 2020 — recompute on the corrected
  curve.
- **Deflated Sharpe / PBO:** cannot be assessed — **trial count was not provided.** Request it.
- **Trade count / exposure:** not reported; a 2-MA daily system over 8 years yields a modest
  number of flips — confirm significance.

## Verdict

**Do not deploy.** Three independent **Critical** findings (look-ahead, zero costs, fully
in-sample tuning) mean the reported numbers are not achievable. Re-run with: signal lagged one
bar, realistic costs, and a walk-forward split; disclose trials and compute the Deflated Sharpe.
Expect most of the apparent edge to vanish.

> **Educational review — not financial advice.** Past backtest performance does not guarantee
> live results. You are solely responsible for your own trading and risk decisions.
