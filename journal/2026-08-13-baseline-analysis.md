# Research Journal — 2026-08-13 (baseline analysis)

Continuation of [2026-08-13-pipeline-extension.md](2026-08-13-pipeline-extension.md).
This entry analyzes the pre-registered baseline backtest (136 trades,
0.5% strike distance, 1000 min volume, zero costs) from five angles.
No strategy parameters were changed for any of this.

## 1. Calendar luck

Only 7 trading days in 2024-2026 moved more than 2% open-to-close:

| Date | Weekday | Move | Was it an expiry day? |
|---|---|---|---|
| 2024-01-23 | Tuesday | −2.20% | No (nearest expiry 2024-01-25, 2d out) |
| 2024-06-04 | Tuesday | **−5.59%** | **No** (nearest expiry 2024-06-06, 2d out) |
| 2024-06-05 | Wednesday | +2.22% | No (nearest expiry 2024-06-06, 1d out) |
| 2024-06-07 | Friday | +2.05% | No (nearest expiry 2024-06-13, 6d out) |
| 2024-11-22 | Friday | +2.12% | No (nearest expiry 2024-11-28, 6d out) |
| 2025-05-12 | Monday | +2.07% | No (nearest expiry 2025-05-15, 3d out) |
| 2026-02-03 | Tuesday | −2.21% | **Yes** (in the 136-trade sample) |

**2024-06-04 (Lok Sabha election results, −5.59%) was confirmed NOT an
expiry day** -- verified directly against that date's actual bhavcopy
(downloaded specifically for this check, not inferred from the
weekday rule): the nearest NIFTY option expiry available that day was
2024-06-06, two days out. Of the 7 largest single-day moves in the
2024-2026 sample, only one (2026-02-03) actually landed on an expiry
day and entered the backtest. The other 6, including the single
largest move in the entire sample, simply weren't trading days for
this strategy. **The 80.88% win rate and Rs 171,473.25 total P&L in the
baseline backtest reflect real calendar luck, not just a naturally
low tail-risk exposure.**

## 2. Stress test -- the 5 worst non-expiry days, simulated as if they'd been expiry days

For each, that date's actual option chain was pulled (downloaded
specifically for this test) and priced using the *nearest available*
expiry rather than a same-day one, since these days genuinely weren't
expiry days -- there is no real same-day-expiry chain for them. This
is clearly an estimate, not a same-day-expiry result: a real expiry-day
chain would have less time value baked in, which cuts both ways
depending on which side breaks.

| Date | Actual move | Expiry used | Days out | Strikes (CE/PE) | Credit | Debit | P&L (points) | P&L (Rs) |
|---|---|---|---|---|---|---|---|---|
| 2024-06-04 | −5.59% | 2024-06-06 | 2d | 23300 / 23050 | 556.00 | 1332.60 | −776.60 | **−50,479.00** |
| 2024-01-23 | −2.20% | 2024-01-25 | 2d | 21850 / 21600 | 119.00 | 430.10 | −311.10 | **−20,221.50** |
| 2025-05-12 | +2.07% | 2025-05-15 | 3d | 24550 / 24250 | 209.10 | 519.65 | −310.55 | **−20,185.75** |
| 2024-11-22 | +2.12% | 2024-11-28 | 6d | 23550 / 23250 | 269.20 | 461.70 | −192.50 | **−12,512.50** |
| 2024-06-05 | +2.22% | 2024-06-06 | 1d | 22250 / 22000 | 392.00 | 387.80 | +4.20 | **+273.00** |

If 2024-06-04 had been an expiry day, the estimated loss (−Rs 50,479)
would have been **more than 3x the actual worst loss in the real
136-trade backtest** (−Rs 16,198, 2025-04-17). This is the clearest
evidence that the baseline backtest's risk profile is understated by
the luck of which days happened to be expiry days, not by the strategy
being inherently safer than a 5.6% move would suggest.

## 3. Drawdown detail

- **Longest losing streak:** 2 consecutive trades (2024-04-18 to
  2024-04-25, 7 calendar days). The backtest never had a long losing
  streak -- losses are isolated single events, not clusters, at least
  in this sample.
- **Max drawdown: Rs 19,727.50**
  - Peak: trade #15, 2024-04-10, cumulative Rs 31,372.25
  - Trough: trade #21, 2024-05-23, cumulative Rs 11,644.75
  - Time to trough: 6 trades, 43 calendar days
  - Recovered: trade #25, 2024-06-20 -- 10 trades / 71 days after the peak
- Equity curve saved to `outputs/equity_curve.png` (drawdown period shaded).

## 4. Costs

Re-run with `config/strategy_with_costs.json` (costs_enabled: true):
Rs 20 brokerage per leg (4 legs/trade), 0.1% STT on sell-side premium,
0.5-point bid-ask slippage per leg (worse fill on every leg, both sides).
Saved separately to `outputs/backtest_trades_with_costs.csv` -- the
zero-cost baseline (`outputs/backtest_trades.csv`) was not touched or
re-run.

| Metric | Zero-cost baseline | With costs | Change |
|---|---|---|---|
| Trades | 136 | 136 | -- |
| Win rate | 80.88% | 80.15% | −0.73pp |
| Average win | Rs 3,001.97 | Rs 2,814.23 | −Rs 187.74 |
| Average loss | −Rs 6,105.50 | −Rs 6,085.48 | +Rs 20.02 |
| Largest win | Rs 11,209.25 | Rs 10,988.03 | −Rs 221.22 |
| Largest loss | −Rs 16,198.00 | −Rs 16,411.44 | −Rs 213.44 |
| **Total P&L** | **Rs 171,473.25** | **Rs 142,443.23** | **−Rs 29,030.02 (−16.9%)** |
| Max drawdown | Rs 19,727.50 | Rs 21,005.25 | +Rs 1,277.75 |

The Rs 29,030.02 total drag breaks down into two parts: Rs 17,680
(136 trades x 4 legs x 0.5pt slippage x Rs 65/point) embedded directly
in the P&L via worse fill prices, plus Rs 11,350.02 in explicit STT and
brokerage (averaging Rs 83.46/trade). **Only one trade flipped sign**
under costs: 2026-06-30 went from +Rs 208.00 to −Rs 4.83 -- a reminder
that on already-marginal trades, a fixed per-trade cost is what decides
the outcome, not the market move.

## 5. Loss distribution

Histogram saved to `outputs/pnl_distribution.png` (zero-cost baseline,
136 trades). 10 worst trades:

| Date | Index move | P&L (Rs) |
|---|---|---|
| 2025-04-17 | +1.92% | −16,198.00 |
| 2024-11-28 | −1.48% | −12,548.25 |
| 2024-05-23 | +1.56% | −10,946.00 |
| 2025-01-02 | +1.71% | −10,026.25 |
| 2024-09-12 | +1.31% | −10,003.50 |
| 2026-05-12 | −1.45% | −9,945.00 |
| 2025-05-15 | +1.49% | −9,789.00 |
| 2026-01-20 | −1.36% | −8,937.50 |
| 2024-10-17 | −1.11% | −7,852.00 |
| 2025-06-26 | +1.11% | −7,055.75 |

All 10 worst trades cluster in the 1.1%-1.9% index-move range -- well
short of the 2%+ moves examined in sections 1-2. This is consistent
with the strike selection: at 0.5% OTM, a move doesn't need to be a
historic tail event to breach both breakevens, it just needs to clear
roughly 1%+, which happens far more often (Finding 2 in the 2026-08-12
entry: ~10.68% of all days under the wider hold-to-expiry zone; the
real ~0.71% breakeven zone from Finding 3 is narrower still).

## Summary

The pre-registered baseline is profitable (Rs 171,473.25 gross, Rs
142,443.23 with realistic costs) over 136 trades, but three things
temper that: (1) the sample's worst-case exposure is understated by
calendar luck -- the single largest index move in the whole period
wasn't even a trading day for this strategy, and would have cost ~3x
the actual worst loss if it had been; (2) costs eat ~17% of gross P&L
even under a fairly standard cost assumption; (3) losses are
concentrated in the 1-2% move range rather than requiring extreme
moves, which is a much more frequent occurrence than the >2% events
examined for calendar luck.
