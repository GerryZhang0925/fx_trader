---
name: fx-usd-factor
description: >-
  FX book construction around the USD factor. Use when adding pairs, a second
  timeframe core, EURUSD/GBPUSD overlap, correlation gates, or claiming MTF
  diversification.
---

# FX USD factor (this kit)

Most majors are one dollar bet with a second currency. Timeframe stacking does
not diversify if the payoff is still USD trend-following.

> Educational — not financial advice.

## Live book (why these three)

USDCAD / USDJPY / GBPUSD were kept for **strategy** correlation under 0.7, not
because every major "needs a core". Pair-price correlation can still spike in stress.

Dropped: EURUSD (OOS PF ~1.01), AUDUSD (no test PF ≥ 1.2 cell), NZDUSD (test PF ~1.06, AUD corr), USDCHF (book DD cap).

## Do not

- Put GBPUSD on H4 Donchian **and** an H1/M15 satellite.
- Assign EURUSD/AUDUSD to a new TF as if the instrument gained edge.
- Call HalfTrend + Donchian "two factors" — both ATR breakout trend-follow.
- Add M15+H1+H4 expected returns. Blend correlated streams; check combined DD.

## USD map (signs flip with quote)

| Position | Rough USD |
|---|---|
| Long USDJPY / USDCAD / USDCHF | Long USD |
| Long EURUSD / GBPUSD / AUDUSD | Short USD |
| Short EURUSD after an upside break | Long USD |

Fading EURUSD breakouts **while H4 ADX ≥ 25** often aligns with USDJPY Donchian longs. Range-only EURUSD (ADX < 20) is the regime that *can* be low-corr (RSI fade daily corr was about −0.05) — that satellite still failed the DD cap.

## Gates

- `max_corr: 0.7` on **strategy daily returns**, not price levels.
- Report rolling corr and a ρ → 1 stress, not a single 60-day number.
- MTF means one trade with HTF bias / primary setup / LTF timing. Three independent books are not MTF. H1 alignment on this Donchian book already dropped.

## Add-on test

Always: H4 3-pair equity vs H4 + new sleeve. DROP if yearly/CAGR/DD worsen or DD > 15%.
