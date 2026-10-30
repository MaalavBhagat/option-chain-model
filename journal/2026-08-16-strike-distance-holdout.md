# Research Journal — 2026-08-16 (strike-distance grid, holdout)

## Departure from the pre-registered plan, recorded before computing anything

Pre-registration specified examining the holdout on the single selected
winner (0.5/0.5). That combination is the existing baseline, so its
2026 results were already known and the holdout cannot verify a new
choice. All 9 combinations are therefore run on the holdout for a
DESCRIPTIVE purpose: to test whether the flatness observed on the tune
set persists out of sample. This is not re-selection -- the winner was
fixed before the holdout was opened and does not change based on
holdout results.

Everything below this line was written after that decision, and after
running the holdout computation.

## Results (n=32, 2026-01-06 to 2026-08-11)

New files: `src/strike_distance_holdout.py`,
`outputs/strike_distance_holdout.txt`. Written as a separate script
rather than an extension of `src/strike_distance_grid.py`, deliberately
-- that script's tune-set-only date assertions are left exactly as
committed, not loosened to also permit holdout dates. The genuinely
reusable pieces (`select_asymmetric_strikes`, `compute_metrics`,
`attach_lot_size_and_rupees`) are imported from it; only the
holdout-specific loading and looping logic is new.

**0.5%/0.5% is NOT the top-ranked combination on the holdout.** It
totals 861.85 points, placing 6th of 9. The top combination is
0.5%/1.0% (put widened, call unchanged) at 1,157.65 points --
295.80 points ahead of the selected baseline.

**Spearman correlation between tune-set rank and holdout rank across
the 9 cells: rho = -0.28 (p = 0.46).** Negative, not significant. This
is squarely consistent with -- not merely "not contradicting" -- the
tune-set flatness finding (`outputs/strike_distance_flatness.txt`):
an ordering built from noise should not be expected to reproduce on a
second, independent sample, and it didn't. If anything the sign is
worth sitting with: the tune set's weak apparent preference for
tighter strikes on the put side did not just fail to repeat, it
inverted on the holdout, where the two combinations with the widest
put (0.5/1.0 and 0.75/1.0) posted the two best holdout totals.

**The grid is flat on the holdout too.** Best (0.5/1.0) vs worst
(1.0/0.5): 539-point spread, paired t-test p=0.17 -- not significant,
though n=32 leaves this test very little power to detect anything
short of a large effect.

**Per the pre-registration's holdout_rule**, a holdout that contradicts
the tune-set result is itself the finding, not grounds to re-select.
Recorded exactly that way here: the tune set's nominal winner did not
hold up, the ranking did not transfer, and no different combination is
being substituted in its place. 0.5%/0.5% remains the strategy's
parameter because it was pre-registered and because nothing tested
here clears the bar to replace it -- not because either dataset
demonstrated it was the best of the 9.

## Sample sizes, stated plainly

n=32 on the holdout, n=104 on the tune set, 9 cells. Every number in
this entry should be read as descriptive, not confirmatory.
