# Research Journal — 2026-08-16 (every-day extension, Phase B results)

Pre-registered in `config/everyday_experiment.json` (commit `2a93f8a`).
Run against the corrected 137-trade baseline (`995e6db`), not the
original 136-trade file.

**DTE>0 trades are structurally different from the expiry-day baseline
and must never be pooled with it or with each other.** Every table
below is stratified by DTE, per variant, exactly as pre-registered.

## Step 1 — correctness gate, re-run against 137

**PASSED.** 137/137 exact match -- same dates, same strikes, same
entry/exit prices, same P&L in points, including 2025-10-20. No
adjustment was needed; the gap that failed the first run (missing
2025-10-20) is now closed in the baseline itself, not patched around
here.

## Step 2 — both variants, all 647 trading days

647 dates extracted for each variant, 0 extraction failures, 0 trades
skipped by the backtest engine, **0 volume-filter failures anywhere,
at any DTE, in either variant.** The 1,000-contract filter does not
start binding away from expiry in this data -- liquidity at these
strike distances stays far above the threshold even several days from
expiry.

## Step 3 — results, stratified by DTE (zero-cost, points)

**nearest_weekly:**

| DTE | n | Mean pts | Median pts | Win rate | StdDev | Worst | Max DD | Mean premium |
|---|---|---|---|---|---|---|---|---|
| 0 | 137 | 19.51 | 32.70 | 81.0% | 67.59 | -249.20 | 303.50 | 54.03 |
| 1 | 124 | 17.58 | 23.53 | 74.2% | 48.45 | -258.75 | 635.95 | 107.34 |
| 2 | 87 | 3.17 | 19.25 | 70.1% | 104.78 | **-776.60** | 778.00 | 147.12 |
| 3 | 81 | 5.78 | 17.60 | 66.7% | 56.75 | -310.55 | 346.00 | 179.32 |
| 4 | 47 | 4.91 | 11.65 | 66.0% | 31.86 | -73.95 | 122.95 | 146.17 |
| 5 | 51 | 24.02 | 25.90 | 80.4% | 53.38 | -192.75 | 192.75 | 209.58 |
| 6 | 119 | 2.03 | 10.10 | 62.2% | 57.21 | -220.45 | 473.85 | 224.32 |

DTE=2's worst trade (-776.60 points) is 2024-06-04 -- the Lok Sabha
result day already studied in `src/event_day_study.py` and
`journal/2026-08-13-baseline-analysis.md`. It shows up here on its own,
independently, as the single worst trade across the entire every-day
extension. Same number, found a second, unrelated way.

**fixed_dte** (target 5 DTE, rolling to whichever available weekly is
closest): DTE=1 has only 4 trades (this variant almost never lands
there by construction -- a small-n bucket, flagged as such rather than
treated as reliable). DTE=2 through 6 broadly track `nearest_weekly`'s
same buckets, as expected since both variants converge on similar
expiries most weeks. Full table, with-costs figures, and per-trade
detail: `outputs/everyday_results.txt`, `outputs/everyday_results.csv`.

## Predictions, checked directly, none softened

- **(a) Mean P&L declines as DTE rises -- FAILED.** Not monotonic:
  19.51, 17.58, 3.17, 5.78, 4.91, **24.02**, 2.03. DTE=5 is the second-
  best bucket, ahead of DTE=0-4 and DTE=6.
- **(b) Win rate falls as DTE rises -- FAILED.** Not monotonic: 81.0%,
  74.2%, 70.1%, 66.7%, 66.0%, **80.4%**, 62.2%. Same DTE=5 bump.
- **(c) Std dev rises with DTE -- FAILED.** Not monotonic. DTE=2 has
  the *highest* stddev (104.78) of any bucket, driven by the single
  2024-06-04 outlier, not by a smooth vega-driven increase toward DTE=6
  (57.21, actually below DTE=2 and DTE=3).
- **(d) Mean P&L after costs may turn negative for DTE>=3 -- FAILED.**
  Every DTE>=3 bucket stayed positive after costs (3.78, 2.91, 22.02,
  0.03). DTE=6 gets close to zero (0.03 points) but never crosses.
- **(e) DTE=0 subset must reproduce the baseline exactly -- HELD.**
  Verified in Step 1.

**Four of five predictions failed, stated plainly, none softened.**
The common thread: DTE=2's huge single loss (2024-06-04) and DTE=5's
unexplained strength both break every monotonic pattern predicted.
The theta/vega reasoning behind (a)-(c) may still be directionally
real on average, but it is not what actually shows up in this data --
a handful of large individual days (like 2024-06-04) and small-sample
noise in some buckets (DTE=4 at n=47, DTE=5 at n=51) dominate the
picture more than a smooth decay curve does.

## The starting hypothesis: "more trading days should mean more profit"

**Not cleanly refuted.** DTE=0 (the real baseline) averages 19.51
points/trade; DTE>0 buckets range from 2.03 to 24.02. DTE=5
specifically *outperforms* DTE=0 on a per-trade basis. If "more trading
days should mean more profit" is read as "some non-expiry days are
worse, but not uniformly all of them," the data agrees with that
weaker version. It does not support the stronger, naive version --
there is no DTE bucket where trading proportionally more often
straightforwardly compounds into proportionally more edge, and DTE=2
in particular carries tail risk (the 2024-06-04 loss) far outside
anything DTE=0 exhibits.

## What this does not do

This entry does not update `RESULTS_EXTENSIONS.md` -- held per explicit
instruction, pending the user reading these results first. It does not
touch `RESULTS.md`, `config/strategy.json`, `outputs/backtest_trades.csv`,
`outputs/backtest_trades_137.csv`, or `outputs/paper_blotter.csv`. It
does not draw a conclusion about whether the every-day extension should
become a real strategy variant -- that's a separate decision, not
something four failed monotonicity predictions settle on their own.
