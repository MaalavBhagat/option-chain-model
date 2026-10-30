# Research Journal — 2026-08-16 (strike-distance grid pre-registration)

**This entry contains no results.** No backtesting code for this
experiment has been written, and no P&L of any kind has been computed
or looked at while writing this entry or `config/strike_distance_experiment.json`.
The point of committing both now, before any of that happens, is that
the commit timestamp is the evidence that the selection rule below was
fixed before any result existed to tempt it.

## The grid, and why 9 combinations rather than a wider search

`call_distance_pct` and `put_distance_pct` each take `[0.5, 0.75, 1.0]`
(percent away from that day's index open), crossed to give 9
combinations, with 0.5/0.5 -- the existing pre-registered baseline --
as one of the 9. A wider or finer grid (say, 0.25% steps, or distances
beyond 1.0%) was deliberately not chosen, for two reasons:

1. **Sample size discipline.** The tune set is 104 trades and the
   holdout is 32 (see below). A finer grid multiplies the number of
   comparisons without multiplying the data available to distinguish
   them -- more cells searched over the same ~104 tune-set trades makes
   it easier to find a cell that looks good by chance, not easier to
   find a cell that's actually better. Nine cells is already a lot to
   ask 104 trades to discriminate between honestly.
2. **The grid brackets the baseline symmetrically** (0.5% is the
   middle value, not an edge), so the search can show the baseline
   losing to something *tighter* as well as something *wider*, rather
   than only ever being able to find "wider is better" because that's
   the only direction tested.

## Why total P&L in points is the only selection criterion

Points, not rupees, per the lot-size audit earlier this project
(`journal/2026-08-16-lot-size-audit.md`): rupee P&L depends on which
lot-size era a trade falls in, which has nothing to do with strike
placement and would contaminate any comparison across combinations
with an unrelated, time-varying scaling factor. Points P&L is exactly
reproducible regardless of lot size.

Total (not win rate, not worst trade, not drawdown) is the criterion
because this is a single-number decision rule, declared as such before
looking: if any of the secondary metrics were allowed to break a tie
or override a total-P&L result, the "selection rule" would really be
"whichever metric makes the preferred answer win," decided after the
fact. The five secondary metrics are still reported for every
combination -- they're just not allowed to change which combination is
declared the winner.

## Tune/holdout split and sizes

- **Tune set**: all baseline trades with date < 2026-01-01 -- **104 trades**.
- **Holdout set**: all baseline trades with date >= 2026-01-01 -- **32 trades**.

The winning combination will be chosen on the tune set only. The
holdout set gets examined exactly once, after that single choice is
locked in -- not used to pick between close contenders, not used to
"double check," and specifically not re-examined if the first look is
inconvenient. A holdout result that contradicts the tune-set winner is
itself the finding to report, not a reason to look for a different
split or a different metric that resolves the contradiction.

## Predictions, stated before any result is seen

(a) **Wider strikes will reduce total P&L but improve the worst single
    trade.** Moving strikes further from the money collects less
    premium (lower total P&L expected) but should be breached less
    often and less severely when it is (a better worst-single-trade
    figure expected).

(b) **Widening the put will cost more premium than widening the call
    by the same percentage**, because index puts carry a volatility
    skew -- OTM puts are priced richer than equivalently-distant OTM
    calls on most equity indices, so giving up the same percentage of
    distance on the put side should give up more premium than doing so
    on the call side.

(c) **Most differences across the grid will be within noise for this
    sample size.** With 104 tune-set trades split across 9 cells,
    typical cell-to-cell differences are expected to be small relative
    to the sample's own variance -- a genuinely large, clearly-outside-
    noise effect would itself be somewhat surprising.

(d) **The volume filter, which never bound at 0.5% in the pre-registered
    baseline (0 of 136 trades skipped), may begin binding at 1.0%.**
    Strikes further from the money are typically less liquid; the
    baseline's zero-skips result doesn't necessarily hold at the wider
    end of this grid.

## Weak evidence, stated plainly in advance

104 tune-set trades split across 9 grid cells is roughly 11-12 trades
per cell on average (unevenly, since combinations aren't independent
draws). A holdout of 32 trades is smaller still. **Even a clean,
unambiguous result from this experiment is weak evidence** by the
standards this project has already applied to other small-sample
findings (e.g. the 15-trade event-day comparison in
`journal/2026-08-14-exploratory-event-filter-wings.md`, and the 15-trade
pre-holiday flagged group in `outputs/preholiday_analysis.txt`). This
experiment is being run and pre-registered anyway because the process
discipline -- fixing the selection rule and the tune/holdout split
before looking -- is the point, not because 104 and 32 trades are
expected to produce a strong result.
