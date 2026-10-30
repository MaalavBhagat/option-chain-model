# Research Journal — 2026-08-16 (strike-distance grid, tune set)

Phase B of the experiment pre-registered in
`config/strike_distance_experiment.json` (commit `9019efa`) and
`journal/2026-08-16-strike-distance-preregistration.md`. This entry
covers the tune set (104 trades, 2024-01-04 to 2025-12-30) only.
**The holdout set (32 trades, 2026-01-01 onward) was not loaded,
computed, printed, or examined anywhere in this task.**

New files: `src/strike_distance_grid.py`,
`outputs/strike_distance_tune_results.txt`,
`outputs/strike_distance_tune_results.csv`. Nothing existing was
touched.

## Correctness check before trusting anything else

The 0.5%/0.5% cell (the pre-registered baseline itself) totals
**1,776.20 points** on the tune set. The original 136-trade baseline's
pre-2026 subset, at the flat lot size of 65, was previously computed as
Rs 115,453.00 (in the 2026-08-16 lot-size audit) -- Rs 115,453.00 / 65
= exactly 1,776.20 points. This is not a coincidence; it's the same
104 trades run through the same strike-selection and P&L logic, and it
matching exactly is the confirmation that this script's reuse of
`backtest_strangle.py`'s engine (rather than a reimplementation) is
faithful.

## The result (tune set only)

**Winner by the sole pre-registered criterion (total_pnl_points):
0.5%/0.5% -- the existing baseline itself.** Full 3x3 table and all
five secondary metrics per combination are in
`outputs/strike_distance_tune_results.txt`.

The margin between the winner (1,776.20 pts) and the runner-up
(0.75%/0.5%, 1,551.70 pts) is 224.50 points over 104 paired trades. A
paired t-test on that comparison gives t=1.16, p=0.25 -- **inside the
noise band at the conventional 5% threshold.** Per the pre-registration's
own instruction to state this plainly: the tune-set result does not
give strong grounds to prefer the baseline over its closest competitor
either, even though the baseline nominally ranks first. It ranks first
by the declared rule, and that's what the rule says to report -- but
"ranks first" and "confidently better" are not being conflated here.

## Predictions, checked directly, none softened

- **(a) Wider strikes reduce total P&L but improve the worst single
  trade -- HELD.** Symmetric combinations show a clean monotonic
  pattern in both directions: total P&L falls (1,776 -> 1,301 -> 1,043
  points) and the worst single trade improves (-249 -> -221 -> -179
  points) as distance widens from 0.5% to 0.75% to 1.0%.
- **(b) Widening the put costs more premium than widening the call by
  the same % -- HELD.** Widening the call alone (0.5->1.0%, put fixed
  at 0.5%) gives up 13.56 points of average premium; widening the put
  alone by the same amount gives up 14.79 points. The direction
  predicted (put costs more) is correct, though the margin between the
  two (1.23 points) is modest, not dramatic.
- **(c) Most differences across the grid will be within noise for
  this sample size -- HELD, for the closest pair tested.** The
  winner-vs-runner-up paired test (p=0.25) sits inside the noise band.
  This is not a full check of "most" differences -- only the top two
  combinations were paired-tested here, not all 36 pairwise
  comparisons across the 9-combination grid, which is a real limit on
  how much this verdict can claim. The 733-point spread between the
  best and worst combination overall (0.5/0.5 at 1,776 vs 0.75/1.0 at
  1,098) is large relative to that single pairwise noise estimate,
  which suggests the grid's *extremes* are probably more separable
  than its neighbors, even though this wasn't tested directly.
- **(d) The volume filter may begin binding at 1.0% -- FAILED,
  stated plainly, not softened.** Zero volume-filter failures occurred
  in any of the 9 combinations, including 1.0%/1.0%, the widest tested.
  Every leg across all 936 (combination, date) pairs cleared 1,000
  contracts. The liquidity margin at these distances is evidently
  larger than the pre-registration anticipated.

## What this does not do

This entry does not declare a winner for the experiment as a whole,
does not touch the holdout set, and does not conclude anything about
whether 0.5%/0.5% should remain the strategy's parameters going
forward. Per the pre-registered holdout rule, the tune-set selection
(0.5%/0.5%, by total_pnl_points) is now locked in. The holdout set gets
examined exactly once, in a separate task, against this specific
already-selected combination -- not used to pick among close
contenders, and not re-examined if its result is inconvenient.
