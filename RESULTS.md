# NIFTY Intraday Short Strangle — Research Summary

**This is a paper-trading research project. No broker is connected, no
order has ever been placed, and nothing here should be read as
investment advice.** This document summarizes what's been found so
far, written for someone who hasn't looked at the code.

## The strategy being studied

A **short strangle** is an options position built from two trades: sell
a call option above the current price, and sell a put option below it,
at the same time. You collect money upfront (the "premium") for both.
You keep that money if the index stays between the two strike prices;
you lose money if it moves past either one, with losses growing the
further it moves.

The specific version studied here:
- Traded only on **NIFTY 50** (India's benchmark stock index).
- Entered at market open, closed before market close, **the same
  day** — never held overnight.
- Only traded on the index's **weekly options expiry day** (the one day
  a week when a specific batch of options contracts expires), because
  that's when time decay works fastest in the seller's favor.
- Strikes placed 0.5% away from that morning's opening price on each
  side.

## Data and its limits

Two data sources, each with a hard boundary that shapes everything
below:

- **NIFTY 50 daily prices**, 2016 to present, from Yahoo Finance. This
  covers the whole 10-year window and has no gaps.
- **NIFTY option prices** (what a specific call or put actually traded
  for on a given day), from NSE's own historical archive. **This
  archive only goes back to 1 January 2024** — confirmed by directly
  testing dozens of dates in 2023, every one of which came back empty,
  while every date from 2024 onward returned real data. This is a
  limit of NSE's own published archive, not a choice made in this
  project, and it's the single biggest constraint on everything that
  follows: **real, verified results only exist for 2024-01-04 through
  2026-08-11.** Anything about 2016-2023 is an estimate (see below),
  clearly separated from the real results.

A third, smaller data source — **India VIX** (the market's "fear
gauge") — was used for some of the exploratory checks and also comes
from Yahoo Finance.

## How the research was done

1. A script downloads NSE's daily options data file for every weekly
   expiry day in the target range (identifying the right day itself
   took some care — NIFTY's expiry day changed from Thursday to Tuesday
   partway through the sample, on 2 September 2025, and holidays shift
   the actual expiry to the previous trading day).
2. A second script extracts just the relevant same-day-expiry NIFTY
   option prices from each file and merges in that day's actual index
   opening price (needed as the reference point for where to place the
   strikes).
3. A backtest script replays the strategy exactly as defined above
   against every one of those real trading days.
4. Several follow-up experiments (below) test variations and add
   realism, each clearly kept separate from the core result rather than
   replacing it.

Every parameter that defines the strategy — the 0.5% strike distance,
and a rule requiring at least 1,000 contracts of trading volume on each
leg (to avoid untradeable, illiquid strikes) — was **written down and
committed to this project's history before the backtest was ever run**,
specifically so the numbers below couldn't be quietly adjusted after
the fact to look better.

## The core result (136 real trades, no costs)

Every NIFTY weekly expiry day from 4 January 2024 to 11 August 2026 —
136 trading days — using real, traded option prices:

| | |
|---|---|
| Trades | 136 |
| Win rate | 80.88% |
| Total profit | Rs 171,473 |
| Average win | Rs 3,002 |
| Average loss | -Rs 6,106 |
| Largest single loss | -Rs 16,198 |
| Maximum drawdown | Rs 19,728 |

At face value, this looks strong: the strategy made money on about 4
out of 5 trading days. But every section below exists because that
headline number, on its own, is incomplete or misleading in some way.

## Adding realistic trading costs

The result above assumes zero costs. Adding standard costs — Rs 20
brokerage per leg (4 legs per trade), the government's 0.1% securities
transaction tax on money received from selling, and a small assumed
cost for the gap between buy and sell prices on each leg — brings total
profit down to **Rs 142,443**, a **17% reduction**. This is the
realistic reference number, not the zero-cost one.

## Was the good result just luck?

This is the most important finding in the whole project. The single
largest one-day move in NIFTY across the entire 2024-2026 period was
**4 June 2024, when the index dropped 5.59%** on the day national
election results were announced. **That day never entered the
backtest at all** — it happened to not be an options expiry day, so
the strategy was never exposed to it, purely by the calendar.

Simulating what would have happened if that day *had* been an expiry
day (using its real option prices, just for a slightly different
contract than a same-day expiry) produces an estimated loss of
**roughly Rs 50,000 — more than three times worse than any loss that
actually occurred** in the real 136-trade sample. In other words, the
strategy's real track record benefited from a real stroke of luck: the
worst day of the whole period simply wasn't a trading day for this
strategy. This tempers every other number in this document.

## Does avoiding "risky" calendar days help?

A calendar of 46 known high-risk dates was built — India's Union
Budget days, election result days, the central bank's rate decisions,
and the US Federal Reserve's rate decisions, each sourced and dated
from official or reputable sources.

Skipping trades on any day that matched this calendar **made results
worse, not better**: total profit dropped from Rs 142,443 to Rs 87,393.
Of the 15 real trades that happened to land on a "risky" calendar day,
14 were winners — the filter throws away good trades far more often
than it avoids bad ones, and it avoided none of the 10 worst trades in
the whole sample. The lesson isn't that scheduled events are harmless
in general — 4 June 2024 *was* a scheduled event, per the point
above — it's that this strategy's real risk doesn't reliably show up
on the days a fixed calendar would flag, because those are exactly the
days the strategy already tends not to trade on.

## Buying insurance: protective wings

A variation was tested: alongside the original two sold options, also
*buy* a further-out call and put (2% away from the opening price
instead of 0.5%) as protection, capping the maximum possible loss. This
is a well-known options structure called an **iron condor**.

- On an ordinary trading day, this insurance is close to pure cost —
  across all 136 trades it cost Rs 61,061 in total and paid back only
  Rs 4,014, a net drag of roughly Rs 57,000 (about a third of the
  no-insurance profit).
- But re-run against the 4 June 2024 stress scenario above, the
  insurance cut that estimated Rs 50,000 loss down to roughly
  **Rs 5,900 — an 88% reduction.**

So the insurance is expensive on quiet days and highly effective on the
one day that actually mattered in this sample.

## Margin: the capital-efficiency angle

Comparing strategies purely on rupee profit misses something: selling
options *without* buying protection requires posting a much larger
security deposit ("margin") with the broker than a protected position
does, because the broker's risk is much larger. Estimating this
(the naked side using a standard percentage-of-notional approximation
grounded in typical real-world broker figures; the protected side using
an exact, standard calculation since its maximum possible loss is
mathematically fixed by the strike prices):

| | Naked strangle | With protective wings |
|---|---|---|
| Total profit | Rs 142,443 | Rs 85,396 |
| Typical margin required | Rs 156,541 | Rs 21,136 |
| **Return on capital used** | **91%** | **404%** |

The naked version needs roughly **7x more capital** to run. Judged on
return on the money actually tied up — arguably the more honest way to
compare two strategies — the protected version is the clear winner,
even though its absolute profit is smaller.

## A rough estimate for 2016-2023

Since no real option-price data exists before 2024, a separate,
heavily-labeled *estimate* was built: the observed relationship between
"how much did the index move that day" and "how much did the trade make
or lose" was measured from the 136 real trades, then applied to every
historical Thursday (NIFTY's expiry day before the 2025 switch to
Tuesday) back to 2016, using only index price data.

**This is explicitly not a backtest.** The relationship was learned
from a calm 2024-2026 period; it has no way to know that option prices
would have been priced very differently during a real volatility spike
like March 2020. With that large caveat: the estimate shows **2020 as
the only losing year** in the 2016-2023 window for the unprotected
strategy (roughly -Rs 64,000 estimated, against +Rs 48,000 to
+Rs 112,000 in most other years), and even that estimate is likely
understated, since the largest actual 2020 crash days weren't Thursdays
either — the same calendar-luck pattern as 4 June 2024, playing out
again by coincidence.

## Where things stand

- The core, real, pre-registered result (136 trades, 2024-2026) is
  genuinely profitable, including after realistic costs.
- That result is materially flattered by which days happened to be
  expiry days — the worst single day in the whole sample simply wasn't
  one.
- A fixed calendar of "risky" days doesn't fix this and actively hurts
  returns.
- Protective wings cost money most of the time but would have been
  decisive on the one day that mattered, and they win decisively on a
  capital-efficiency basis even though they look worse on paper.
- Anything about years before 2024 is a labeled, caveated estimate, not
  a result, because the underlying option-price data doesn't exist.

## Forward paper trading vs. backtested results

Starting now, `src/paper_blotter.py` records what the pre-registered
rule *would have done* on each real NIFTY expiry day, going forward,
using that day's actual end-of-day prices. It's run once per expiry
day, after the market closes and NSE publishes that day's data — never
during the trading day, and never to place or simulate placing an
order. Results land in `outputs/paper_blotter.csv`, with a blank
`notes` column for manual annotation.

**This file is deliberately separate from everything above it in this
document, and the two must never be combined.** The 136-trade result
this document is built around is a backtest — every trade in it was
already known, dated, and priced before the analysis began, which is a
fundamentally easier setting than trading forward without knowing what
happens next. Mixing a handful of forward paper trades into that
number, or reporting a "combined" win rate or P&L across both files,
would quietly launder forward results into a backtest's credibility (or
vice versa) and make neither number trustworthy. Any future summary of
paper-blotter performance should stand entirely on its own, dated from
whenever the blotter actually starts recording trades — not spliced
onto the 2024-2026 backtest total.

## Where everything lives

- `journal/` — the full lab notebook, one dated entry per finding, in
  the order they were discovered (including corrections, when an
  earlier entry turned out to be wrong).
- `src/` — every script, each one runnable on its own.
- `config/` — the pre-registered strategy parameters, the cost model,
  and the cited event calendar.
- `data/raw/` and `data/processed/` — downloaded and cleaned data.
- `outputs/` — every result file and chart referenced above, plus the
  forward-only `paper_blotter.csv` once it starts recording.
