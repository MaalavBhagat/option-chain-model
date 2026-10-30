# Research Journal — 2026-08-16 (corrected 137-trade baseline)

The inclusion decision for 2025-10-20 was recorded and committed at
`7d166f7` before this trade's P&L was known. This entry runs it.

New files: `src/build_corrected_baseline.py`,
`outputs/backtest_trades_137.csv`, `outputs/baseline_137_summary.txt`.
`outputs/backtest_trades.csv` (the original 136-trade file) is
untouched and remains the historical record; the corrected version is
a new, separate file, exactly as instructed.

## The 2025-10-20 trade

A quiet, ordinary day: index moved +0.07%, both legs decayed to near
zero by close (call 14.90 -> 0.15, put 19.55 -> 0.15). P&L: **34.15
points, Rs 2,561.25** at its real lot size (75, confirmed via bhavcopy,
not the history-table fallback).

## 136 vs 137, side by side

| Metric | 136 (original) | 137 (corrected) | Change |
|---|---|---|---|
| Trades | 136 | 137 | +1 |
| Total P&L (points) | 2,638.05 | 2,672.20 | +34.15 |
| Win rate | 80.88% | 81.02% | +0.14pp |
| Mean P&L (points) | 19.40 | 19.51 | +0.11 |
| Median P&L (points) | 32.65 | 32.70 | +0.05 |
| Worst single trade (points) | -249.20 | -249.20 | unchanged |
| Max drawdown (points) | 303.50 | 303.50 | unchanged |
| Longest losing streak | 2 | 2 | unchanged |

Rupee totals are deliberately not put side by side as a clean
comparison here: the 136-trade figure uses the flat lot_size=65
convention (`RESULTS.md`), the 137-trade figure uses actual
per-contract `NewBrdLotQty` -- the two aren't measuring the same thing,
and conflating them would double up two separate, already-documented
corrections (missing trade + lot size) into one confusing number. Full
detail in `outputs/baseline_137_summary.txt`.

**2025-10-20 ranks 72nd of 137 by points (worst=1) -- almost exactly
the median.** It's an unremarkable, ordinary day, not a tail event in
either direction. Its inclusion nudges every headline figure slightly
in the favorable direction and changes none of them materially. **No
headline conclusion in `RESULTS.md` or `RESULTS_EXTENSIONS.md` is
overturned by this correction.**

## Findings re-checked against 137 trades

- **Event base rate check**: worst-10 and best-10 by points are
  **identical to the 136-trade version** -- 2025-10-20 doesn't rank
  extreme enough to enter either group. Worst-10 hit rate: 0/10
  (unchanged). Best-10 hit rate: 3/10 (unchanged). Overall hit rate
  shifts trivially from 15/136 (11.0%) to 15/137 (10.9%) -- denominator
  only, not a real change.
- **2025-04-17 is still the worst trade** in points (-249.20), unchanged.
- **The 2024-06-04 stress ratio is unchanged: 3.12x** (-776.60 pts vs
  -249.20 pts) -- neither number in that comparison moved.

All three: **unchanged.**

## What was deliberately left alone

The strike-distance experiment (`config/strike_distance_experiment.json`,
tune set 104 trades, holdout 32 trades) is **not re-run** with this
correction. Its tune/holdout split and its winning-combination selection
were fixed and committed before the holdout was examined
(`9019efa`, `651903f`, `d012168`); silently adding a trade after
that discipline was already exercised -- especially one now known to be
median-performing and therefore unlikely to shift anything, which is
exactly the kind of reasoning that shouldn't be allowed to justify
reopening a closed pre-registration -- would undermine the entire point
of having fixed it in the first place. If the strike-distance experiment
is ever revisited, it should be as an explicitly new, separately
pre-registered pass on the full 137-trade set, not a quiet patch of the
one already run and reported.

## Not yet done

The every-day extension's Phase B (predictions a-e,
`config/everyday_experiment.json`) has not been run. Per instruction,
this task stops here.
