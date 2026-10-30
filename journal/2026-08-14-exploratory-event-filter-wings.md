# Research Journal — 2026-08-14 (exploratory experiments)

**Both experiments in this entry are exploratory tests against the
pre-registered baseline (136 trades, 0.5% strike distance, 1000 min
volume, committed in `902da2c` / `630d1b0`). Neither changes the
baseline's strike distance or volume threshold, and neither replaces
the baseline as the strategy's reference result.**

## Experiment 1: event-day filter

Built `config/event_calendar.csv` -- 47 rows / 46 unique dates covering
Union Budget days, the 2024 Lok Sabha election result day, RBI MPC
announcement days, US Fed FOMC decision days, and state election result
days for 2024-2026. Every date is cited to a source (RBI's own site,
federalreserve.gov, and named news outlets reporting official EC/RBI/Fed
schedules) -- see the `source_url` column in the CSV itself.

One methodological note: FOMC decisions are announced at 2pm US Eastern,
which is after the Indian market has already closed on the Fed's own
calendar date. The calendar therefore flags the *next* India trading
session for Fed events, not the US announcement date itself, since
that's the session where the news actually gets priced in. All 21 Fed
rows in the CSV are dated this way and say so explicitly in their
description field.

Added a `--skip-event-days` flag to `backtest_strangle.py` (checks each
trade date against the calendar; matched dates are skipped and logged
with which event triggered the skip, same mechanism as the existing
volume-skip logic). Re-ran the **costed** backtest with the filter on,
saved to `outputs/backtest_trades_with_costs_event_filtered.csv`
(separate from both `outputs/backtest_trades.csv` and
`outputs/backtest_trades_with_costs.csv`, neither of which was touched).

| Metric | Costed, no filter | Costed + event filter |
|---|---|---|
| Trades | 136 | 121 (15 skipped) |
| Win rate | 80.15% | 78.51% |
| Total P&L | Rs 142,443.23 | Rs 87,392.59 |
| Max drawdown | Rs 21,005.25 | Rs 25,305.00 |

**The filter made things worse, not better, in this sample.** Of the 15
skipped trades, 14 were winners and only 1 was a loss in the unfiltered
run -- together they contributed **Rs 55,050.64 in profit** that the
filter throws away. **None of the 10 worst trades from the earlier
distribution analysis fell on a flagged event day** -- checked directly
against the skip list, zero overlap. Max drawdown also got worse
(Rs 21,005 -> Rs 25,305), because removing profitable trades shrinks the
cushion available to absorb the real losses, which weren't event days
anyway.

**Correction (2026-08-14, caught after first writing this entry):** an
earlier draft of this finding called 2024-06-04 a "non-scheduled event
day." That's wrong. 2024-06-04 (Lok Sabha election results) **is** a
scheduled event -- it's literally row 5 of `config/event_calendar.csv`,
and the counting date was public knowledge months in advance via the
Election Commission's official poll schedule. The reason it never
showed up anywhere in this filter test has nothing to do with whether
it was scheduled: **it wasn't a NIFTY expiry day** (confirmed directly
in the 2026-08-13 calendar-luck analysis -- nearest expiry was
2024-06-06, two days later), so it was never a candidate trade in the
136-trade sample at all. The event filter had nothing to skip on that
date because the strategy never traded that date in the first place.

The correct, narrower finding: **of the scheduled events that *did*
coincide with an actual expiry day in this sample, all 15 were
benign** -- 14 winners, 1 loss, none among the 10 worst trades. That's
a statement about the 15 event-days that happened to land on Thursday
(pre-2025-09-02) or Tuesday (from 2025-09-02) expiries, not a general
claim about scheduled-event risk. **Since NIFTY's weekly expiry moved
to Tuesday on 2025-09-02, which scheduled events land on an expiry day
going forward will be different from which ones did in this sample** --
a Tuesday-heavy regime changes the odds of a Tuesday-anchored event
(or any event whose date happens to fall on a Tuesday) coinciding with
an expiry day, compared to the Thursday-anchored regime that produced
most of this sample. This finding should not be assumed to hold once
enough post-2025-09-02 Tuesday-expiry data accumulates to check it
separately.

## Experiment 2: protective wings (iron condor conversion)

For each of the 136 baseline trades, computed the cost and effect of
also buying a call and put 2% out-of-the-money (bought at `OpnPric`,
sold at `ClsPric`, same intraday round trip as the short legs) --
turning the naked strangle into an iron condor. Wing distance (2%) is
fixed for this experiment only, not read from `config/strategy.json`.
Per-trade detail saved to `outputs/wing_insurance_analysis.csv`.

- **Total wing premium spent (136 trades): Rs 61,061.00**
- **Total wing P&L: -Rs 57,047.25** (wings lose money on most days, as
  expected -- they only pay off when the move is large enough to reach
  a 2% strike, which happened on 0 of the 136 actual expiry days in
  this sample)
- Naked strangle total P&L: Rs 171,473.25 -> combined with wings:
  **Rs 114,426.00** (a Rs 57,047.25 reduction, matching the wing P&L
  above almost exactly since premium spent and lost are nearly the
  same number here)
- Naked strangle's single worst loss (2025-04-17): -Rs 16,198.00 ->
  with wings: **-Rs 16,571.75** -- slightly *worse*. That day's 1.92%
  move never reached either 2% wing strike, so both wings simply
  decayed to a small loss on top of the naked loss.

**The 4 June 2024 stress scenario, re-run with wings:** using the same
non-expiry-day chain from the earlier stress test (nearest expiry
2024-06-06, 2 days out), the protective put (22700 strike, bought at
110.00) would have closed at 973.30 as the index fell 5.59% -- an
8.8x return on that leg alone.

| | Naked strangle | With 2% wings |
|---|---|---|
| P&L | -Rs 50,479.00 | **-Rs 5,915.00** |

Wings would have cut that specific stress-scenario loss by roughly 88%.

**The two results together are the actual finding:** on an ordinary
day, wings are close to pure cost -- they lost money in the one
concrete case checked in detail (2025-04-17) and dragged down the
aggregate P&L across all 136 trades by roughly a third. But on the one
day in this entire 2.6-year period that actually mattered (2024-06-04),
wings would have been the difference between a catastrophic loss and a
manageable one -- and per the corrected Experiment 1 finding above,
that day *was* a scheduled event, it just never became a trade because
it wasn't an expiry day. Neither experiment argues for adopting the
filter or the wings as-is; both argue that the real risk in this
strategy is concentrated in large moves that don't reliably coincide
with the days this strategy actually trades, and that a static
event-day filter (which only ever sees days that *are* expiry days)
doesn't reach that risk, while a fixed-cost insurance overlay does, at
a steady drag the rest of the time.

## Experiment 3 (exploratory): are the 15 event-day winners explained by richer premium?

Compared the 15 event-day trades against the other 121 on four metrics,
using the costed baseline (`outputs/backtest_trades_with_costs.csv`),
each trade's actual event-calendar match, and India VIX (`^INDIAVIX`,
fetched fresh via yfinance). Welch's t-test on each (unequal variances,
appropriate for n=15 vs n=121). Full detail in
`outputs/event_winners_analysis.csv`.

| Metric | Event-day mean | Non-event mean | Difference | Welch t | p-value |
|---|---|---|---|---|---|
| Premium collected (Rs) | 4,639.27 | 3,382.44 | +1,256.82 | 1.99 | 0.061 |
| Abs index move (%) | 0.41 | 0.52 | -0.11 | -1.19 | 0.247 |
| P&L (Rs, costed) | 3,670.04 | 722.25 | +2,947.79 | 2.83 | **0.011** |
| India VIX (open) | 15.09 | 14.45 | +0.64 | 0.87 | 0.394 |

**Plain answer: this is not clearly explained by richer premium, and
15 trades is too few to say with confidence.** Only the P&L difference
clears the conventional p<0.05 bar; the premium-collected difference
that would explain *why* P&L was higher is itself only borderline
(p=0.061, not significant at the usual threshold). If richer premium
were compensating for genuinely higher risk, VIX should also have been
elevated on those days -- it wasn't (p=0.394). Four metrics were tested
here; under a Bonferroni correction for multiple comparisons the bar
for "significant" moves to roughly p<0.0125, which the P&L result
barely clears and could easily not have.

More concretely: 3 of the 15 event trades (2024-02-01, 2025-01-30,
2025-04-09) averaged Rs 8,602 in premium and Rs 8,328 in P&L each --
they are doing most of the work. Excluding them, the remaining 12
event trades still average somewhat better than non-event trades
(Rs 2,506 vs Rs 722), but that's now a 12-trade sub-comparison, not
independently tested, and offered only as a sanity check rather than a
new claim. **The honest conclusion is that the apparent event-day edge
is real in this specific sample but not statistically robust, and not
mechanistically explained by any of the four candidate variables tested
here.** More data (post-2025-09-02 Tuesday-expiry trades accumulating
over time) would be needed before treating "event days are safer" as
an actionable finding.

## Experiment 4 (exploratory): margin and return on capital

Absolute P&L doesn't reflect capital efficiency -- a strategy needing 7x
less margin to run is a different proposition even at lower gross
profit. Estimated SEBI/exchange margin for both the naked strangle and
the winged version, per trade, and recomputed both as return on margin.
Full detail in `outputs/margin_return_analysis.csv`.

**Margin methodology (both approximations where noted):**
- **Naked strangle:** SEBI's actual SPAN + Exposure margin requires the
  exchange's live risk-scenario arrays, which this project doesn't have
  access to. Approximated as **10% of notional** (index open x lot
  size) per trade -- this lands inside the real-world range cited for a
  single naked NIFTY option lot (roughly Rs 100,000-150,000, per a
  5paisa explainer on SEBI margin rules) across this sample's spot
  levels. This is a labeled estimate, not an exact SPAN figure.
- **Winged (iron condor):** SEBI's 2020 hedged-margining framework caps
  a defined-risk spread's margin at its maximum possible loss (spread
  width minus net credit received) -- this is standard, documented
  methodology (Zerodha Varsity's Iron Condor chapter, corroborated by
  other sources), and is computed **exactly** here from this project's
  own strike and premium data, not approximated.

| | Naked strangle | Winged (iron condor) |
|---|---|---|
| Total P&L | Rs 142,443.23 | Rs 85,395.98 |
| Avg margin required | Rs 156,541.35 | Rs 21,135.63 |
| Max margin required | Rs 171,002.33 | Rs 25,389.00 |
| **Return on avg margin** | **91.0%** | **404.0%** |
| Return on max margin | 83.3% | 336.4% |

The winged P&L figure (Rs 85,395.98) combines the naked legs' realistic
costs (brokerage/STT/slippage) with the wing legs at zero cost -- it is
not a fully-costed iron condor figure (the wings' own brokerage, STT on
their exit sale, and slippage were not modeled here). It's used as
given since it matches how the comparison was framed, but this
composition is noted rather than hidden.

**The ranking reverses.** In absolute rupees the naked strangle looks
better (Rs 142,443 vs Rs 85,396). On return on capital, the winged
version wins by roughly 4-5x (404% vs 91% on average margin required)
because it needs about **7.4x less margin** -- the naked strangle's
margin is dominated by the approximated SPAN/exposure charge on
effectively uncapped risk, while the winged version's margin is capped
at its known maximum loss by construction. This is the single most
capital-efficiency-relevant result in this entry: if margin (not
absolute P&L) is the real constraint on how much of this strategy can
actually be run, the winged version is not just "safer," it's the
better-performing strategy.

## Open question carried forward

Is there a wing distance or a dynamic (e.g., VIX-scaled) insurance
sizing that pays for itself across the full sample rather than only in
the single worst-case scenario checked here? Not tested -- would need a
proper backtest of wings across all 136 trades against varying
distances, not just the one stress date, before drawing a sizing
conclusion. Given Experiment 4's result, that backtest should be
evaluated on return on margin, not absolute P&L.
