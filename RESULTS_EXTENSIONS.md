# Results Extensions

This document supplements `RESULTS.md` with findings discovered after
that document was written. **`RESULTS.md` itself has not been edited**
-- see the closing section below for why.

## Lot size audit and the case for points-based reporting

### What RESULTS.md currently assumes, and why it's wrong

Every rupee figure in `RESULTS.md` -- the 136-trade baseline's Rs
171,473 total profit, its Rs 16,198 largest single loss, the Rs 142,443
costed figure, the roughly Rs 50,000 calendar-luck stress estimate, all
of it -- was computed using a single flat number: NIFTY's lot size is
65 contracts per lot, applied to every trade regardless of date.

That's wrong for the large majority of the sample. NIFTY's lot size
actually changed multiple times across the 2024-2026 period this
project covers, and the 65 figure only became correct from January
2026 onward. **104 of the 136 baseline trades (76%) used the wrong lot
size in every rupee figure `RESULTS.md` reports.**

### The four real regimes, and why a calendar alone can't determine them

Checked directly against `NewBrdLotQty`, a real per-contract field
present in every NSE bhavcopy file this project already downloads --
not inferred from any announcement date:

| Lot size | In effect | Baseline trades affected |
|---|---|---|
| 50 | 2024-01-04 (start of this project's data) to 2024-04-25 | 17 |
| 25 | 2024-04-26 to 2024-11-19 (policy), but individual contracts through 2025-01-30 | 36 |
| 75 | 2024-11-20 to 2025-10-27 (policy), individual contracts from as early as 2025-01-02 | 51 |
| 65 | 2025-10-28 onward (policy), fully in effect from 2026-01-06 | 32 |

The reason the boundaries aren't clean dates: NSE grandfathers already-
listed contracts at their *original* lot size until each one's own
expiry, rather than switching everything on a single day. Since NIFTY's
monthly contracts are listed months ahead of their expiry, a monthly
contract already on the exchange's books before a lot-size change can
still be trading -- and still using the *old* lot size -- weeks or
months after the change took effect for newly-listed contracts. This
was confirmed directly: the single 2025 baseline trade still carrying
the old lot size of 25 (2025-01-30) is exactly a month-end (monthly)
expiry, consistent with this mechanism, though with only one such case
in the sample this confirms the mechanism rather than proving it
generally.

### Corrected baseline total vs. reported total

Recomputed using each trade's own real lot size instead of the flat 65:

| | Reported in RESULTS.md | Corrected |
|---|---|---|
| 136-trade baseline total P&L | Rs 171,473 | **Rs 148,660.25** |
| Difference | | **-Rs 22,813.00 (-13.3%)** |

This also affects a headline risk figure beyond the total: the "largest
single loss" RESULTS.md reports as Rs 16,198 (2025-04-17) is itself
under a lot-size correction -- that trade's real contract carried lot
size 75, not 65, making its true rupee loss **Rs 18,690.00**, not
Rs 16,198.00.

**Record for quick reference:** the worst baseline trade is **2025-04-17
at -Rs 18,690** (lot size 75), not -Rs 16,198 as `RESULTS.md` states. In
points -- the lot-size-independent unit -- it is **-249** against
**-777** for the 2024-06-04 stress scenario, a ratio of **3.12x**.

### The 2024-06-04 figure, in rupees and points, and why points is the number that matters

RESULTS.md's single most-cited finding -- the "was the good result just
luck?" section -- rests on a stress-test estimate that 2024-06-04 (the
Lok Sabha election result day, the largest single-day index move in
the whole 2024-2026 period) would have cost roughly Rs 50,000 had it
been an expiry day. That figure used the flat lot size of 65. The real
contract traded that day (nearest expiry 2024-06-06) carried lot size
**25**.

| | Rupees | Points |
|---|---|---|
| As reported in RESULTS.md (lot 65 assumed) | -Rs 50,479.00 | -776.60 |
| Corrected (true lot size 25) | **-Rs 19,415.00** | -776.60 (unchanged) |

**The points figure never moved.** That's the point of reporting it at
all: `pnl_points = (call_entry + put_entry) - (call_exit + put_exit)`
never touches lot size, so it's the one number in this whole audit that
was never wrong. The rupee figure swings by more than 2.6x depending on
which lot size gets multiplied in -- but the *option-market* severity
of that day, measured the way an options trader actually measures it
(how many points did the position move against you), was always
-776.60, full stop.

This matters specifically for judging tail risk against ordinary bad
days. A trader comparing "how bad was 2024-06-04 versus a normal losing
Tuesday" should compare *points moved*, not rupees at a lot size that
turns out to depend on which year it happened to be. In points,
2024-06-04's -776.60 is directly comparable to, say, 2025-04-17's
-249.20 (the real baseline's actual worst trade) -- a **3.12x** ratio
that holds regardless of any future lot-size change. The rupee
comparison, by contrast, gives a *different* ratio (roughly 1.04x)
purely because the two trades happened to fall in different lot-size
eras -- an artifact of bookkeeping, not of what actually happened to
the strategy. Anyone drawing a conclusion about relative severity from
rupee figures alone, across trades from different eras, will draw the
wrong conclusion; points figures don't have this problem.

## Strike distance experiment

A separate, pre-registered experiment (`config/strike_distance_experiment.json`,
committed before any result existed) tested whether moving the short
strangle's strikes further from the money -- 0.5%, 0.75%, or 1.0% on
each leg independently, 9 combinations -- would have produced a better
result than the pre-registered baseline's fixed 0.5%/0.5%.

**Honest conclusion: no detectable difference was found, in either
direction, on either the tune set or the holdout.**

- On the tune set (104 trades, 2024-2025), all 36 pairwise comparisons
  across the 9 combinations were statistically flat. The widest possible
  spread (0.5%/0.5% vs 1.0%/1.0%, a 733-point gap) reached p=0.099 for
  that specific comparison -- not the closest any comparison in the grid
  got to significance. The single lowest p-value across all 36 pairwise
  comparisons was **p=0.0598** (0.5%/0.5% vs 0.75%/1.0%), still short of
  the conventional p<0.05 threshold. Neither comparison, nor any of the
  other 34, reaches significance -- the conclusion is unchanged: no
  detectable difference anywhere in the grid. The baseline came out
  numerically first, but that ranking was already flagged as
  indistinguishable from noise before the holdout was opened.
  Full pairwise table: `outputs/strike_distance_flatness.txt`.
- On the holdout (32 trades, 2026), the baseline was **not** the
  top-ranked combination -- it placed 6th of 9. The Spearman
  correlation between the tune-set ranking and the holdout ranking was
  **-0.28** (not significant, p=0.46): slightly negative, meaning the
  tune set's ordering did not carry forward and if anything trended in
  reverse. The holdout's own best combination (0.5%/1.0%, widening only
  the put) moved in the *opposite* direction from what the tune set's
  raw totals suggested wider strikes would do.

**A flat grid means the original pre-registered parameter (0.5%/0.5%)
is retained by default, not because this experiment demonstrated it
was superior.** No evidence surfaced here supports moving away from
it, but no evidence supports it as the *right* choice among the 9
tested either -- the honest reading is that this strategy's strike
distance, at least within the 0.5%-1.0% range and at this sample size,
does not appear to be a lever with a detectable effect on outcome.
Full detail: `outputs/strike_distance_tune_results.txt`,
`outputs/strike_distance_flatness.txt`, `outputs/strike_distance_holdout.txt`,
and `journal/2026-08-16-strike-distance-*.md`.

## Corrected baseline: a missing 137th trade

The every-day extension's Phase B correctness gate (`src/everyday_backtest.py`,
Step 1) required its DTE=0 subset to reproduce the 136-trade baseline
exactly before proceeding. It didn't: every one of the 136 overlapping
trades matched exactly (a calculation check that passed), but a 137th
genuine same-day-expiry date -- **2025-10-20** -- was found missing
from the baseline entirely (a completeness gap, not a calculation
error). Root cause: that week's real weekly expiry fell on Monday
2025-10-20 rather than the expected Tuesday, because 21 October 2025
was an official NSE holiday for Diwali with only a ceremonial one-hour
session; the original downloader's holiday-rollback logic only
triggers on a full market closure (HTTP 404), which never happened,
so it never looked at Monday. Full account:
`journal/2026-08-16-missing-expiry-day.md`.

**The inclusion decision -- to add 2025-10-20 as a data-completeness
correction, since it meets the pre-registered "trade every weekly
expiry day" rule exactly -- was made and committed (`7d166f7`) before
its P&L was computed or seen.**

Once run, 2025-10-20 turned out to be an unremarkable, near-median
trade (34.15 points, rank 72 of 137). The corrected 137-trade totals:

| Metric | 136 (original) | 137 (corrected) |
|---|---|---|
| Total P&L (points) | 2,638.05 | 2,672.20 |
| Win rate | 80.88% | 81.02% |
| Worst single trade (points) | -249.20 | -249.20 (unchanged) |
| Max drawdown (points) | 303.50 | 303.50 (unchanged) |

No headline conclusion changes. The worst trade, the max drawdown, the
event-base-rate check's worst-10/best-10 groups, and the 2024-06-04
stress ratio (3.12x in points) are all identical between the 136- and
137-trade versions. Full detail: `outputs/backtest_trades_137.csv`,
`outputs/baseline_137_summary.txt`, `journal/2026-08-16-corrected-baseline-137.md`.

The strike-distance experiment (tune/holdout split fixed and the
holdout already examined before this correction existed) was
deliberately **not** re-run against the 137-trade set, to preserve the
pre-registration discipline that experiment was built around.

## Every-day extension and the DTE confound

**Research question:** does trading this strategy's entry rule on
*every* trading day, not just weekly expiry days, produce more profit
than the pre-registered expiry-only baseline? The starting hypothesis
going in (`journal/2026-08-16-everyday-preregistration.md`) was "more
trading days should mean more profit."

**Structural difference, never pooled:** a non-expiry-day option does
not expire that afternoon, so its closing price still carries real
time value, unlike a same-day-expiry (0 DTE) trade's near-pure
intrinsic close. Every result below is stratified by DTE (days to
expiry, 0-6) and by variant, never combined into one pooled number.

**Phase B's raw result** (`journal/2026-08-16-everyday-results.md`)
appeared to show DTE=5 beating DTE=0 on a per-trade basis: 24.02 points
average vs 19.51 for the real expiry-day baseline. Four of the five
pre-registered predictions -- (a) mean P&L declines with DTE, (b) win
rate falls with DTE, (c) stddev rises with DTE, (d) mean P&L turns
negative for DTE>=3 after costs -- all initially **FAILED**, with this
DTE=5 result as the clearest violation of (a) and (b).

The fifth pre-registered prediction, **(e) the DTE=0 subset must
reproduce the 137-trade baseline exactly, was the Step 1 correctness
gate and HELD on the very first run** (137/137 exact match) -- it was
never in question and needed no later correction. It is a different
kind of check from (a)-(d): a pipeline-integrity gate that had to pass
before Phase B's substantive predictions could even be examined, not
one of the four directional hypotheses that failed. See
`journal/2026-08-16-everyday-results.md`, "Step 1 -- correctness gate."

**The confound** (`outputs/dte_confound_check.txt`): DTE buckets turn
out to be largely proxies for day-of-week and expiry regime, not for
time-to-expiry itself. Cross-tabulating DTE x weekday x regime shows
DTE=2 is 100% pre-regime (95.4% Tuesday), DTE=3 is 95.1% pre-regime
(95.1% Monday), DTE=4 is 97.9% post-regime (93.6% Friday) -- these are
effectively single-weekday-single-regime samples wearing a DTE label,
not a clean sweep across time-to-expiry.

**The correction:** holding time period constant kills the DTE=5
finding. DTE=0 restricted to the post-2025-09-02 period alone averages
**25.25 points -- higher than DTE=5's overall 24.02.** The apparent
DTE=5 advantage was a recent-period effect, not a genuine DTE effect,
and does not survive controlling for when the trades happened.

**The clean comparison:** comparing `fixed_dte` against `nearest_weekly`'s
DTE=0 subset on the *same* 137 expiry dates (holding the date set, and
therefore weekday/regime mix, constant) isolates DTE properly: DTE=0
(mean 19.51 points) outperforms the longer-dated leg (mean 15.67
points) -- **this supports prediction (a)** once the confound is
controlled for.

**A design wrinkle surfaced by this check:** on those same 137 expiry
dates, `fixed_dte`'s realized DTE skews to **7, not 5** -- on an actual
expiry day, next week's DTE=7 is mathematically closer to the 5-day
target than today's DTE=0 is, so the "closest to 5" rule picks the
following week's contract instead. The clean comparison above is
therefore DTE=0 vs mostly-DTE=7, reported as such rather than
mislabeled as "~5 DTE."

**Plain conclusion: the starting hypothesis is NOT supported.**
Expiry-day trading outperforms non-expiry-day trading on a per-trade
basis once the day-of-week/regime confound is accounted for. Of the
five pre-registered predictions, (e) -- the DTE=0 correctness gate --
held from the first run and was never in question. Of the remaining
four substantive predictions, (a)-(d) all failed on first look; only
(a) recovers, and only after this correction -- it did not hold on the
raw, confounded DTE breakdown. This is not a case for trading every
day instead of only expiry days.

### RESULTS.md is superseded here, deliberately left unedited

Every rupee figure in `RESULTS.md`'s baseline, costs, calendar-luck,
event-filter, wings, and margin sections was computed at the flat
lot-size-65 assumption and is now known to be inaccurate for the
majority of the sample. This document supersedes those figures. But
`RESULTS.md` itself has not been changed, and should not be
retroactively edited to match this one: it's a record of what this
project believed and reported at the time, complete with the
assumption that turned out to be wrong. Silently correcting it in
place would erase the fact that a real error was found, tracked down,
and fixed -- which is itself part of this project's record, not
something to clean up after the fact. Future summaries of this project
should read `RESULTS.md` for the original baseline narrative and this
document for the corrected numbers, not treat one as a quiet patch of
the other.

## Pledged collateral as leverage: does the extra premium survive the extra risk?

Pre-registered at commit `9137600`; corrected analysis run at `43de021`
(`outputs/pledged_leverage_analysis_v2.csv`). Full reasoning, including
both design errors found and corrected along the way, in
`journal/2026-08-18-pledged-leverage-analysis.md`.

**The question.** NSE brokers let you pledge shares you already own as
margin collateral instead of posting cash. That lets you sell more
contracts on the same cash. Does the extra premium survive the extra
risk? Two arms, same 137 trades, same fixed cash: **Arm A** sizes its
position on cash alone; **Arm B** sizes it on cash plus pledged shares.
Hedged iron condor only. Reported in rupees rather than this project's
usual points, because cash buffers and haircuts have no points
equivalent -- but every margin figure uses the real per-trade lot size,
never a flat assumption.

**Two design errors were found and corrected rather than patched.** The
predecessor study defined the account's cash as a fraction of each
trade's own margin requirement, which made a margin breach
arithmetically impossible -- its "zero breaches" result was the
definition of the input, not a finding. The first run of *this* study
then booked forced-close P&L at the intraday-high ceiling, a price path
its own pre-registration says may never have existed. Both flawed runs
are still on disk, unedited, each with a warning note beside it. Neither
was silently corrected in place.

### Headline

**Pledging roughly doubled position size and multiplied forced closes
from 2 to 15-19 out of 137.** The leverage is structurally capped:
`min(U, C)` limits the pledged shares' contribution to exactly the cash
amount, so available margin can never exceed `2C`. Verified across all
14,796 rows -- zero violations, maximum ratio exactly 1.000000. This
study cannot produce a result implying unlimited leverage.

**Qualification to "roughly doubled" -- the cap is on margin, not on
lots.** Available margin can never exceed `2C`, and that was verified
with zero violations. But lots are whole numbers, so Arm B gets
`floor(2C / m)` lots against Arm A's `floor(C / m)`, and the first is
generally more than twice the second. **At C=Rs 25,000 the aggregate lot
ratio reaches 2.42x, and on 18 individual trades Arm B holds 3x Arm A's
lots, not 2x** -- the cases where Arm A can afford one lot and Arm B can
afford three. The effect fades as cash grows (2.013x aggregate at
C=Rs 2,00,000). So "roughly doubled" is accurate at the larger cash
levels and an **understatement at the smallest**, where position size
sometimes tripled. A reader sizing a small account from the headline
alone would be misled toward *more* risk than it implies, not less.

Base case: beta 1.0, haircut 9% (the SEBI floor), scenario S3
(high-triggered, close-booked), 137 trades, 2024-01-04 to 2026-08-11.

| Cash `C` | Arm A net | Arm B net | Arm B's edge | Forced closes A / B |
|---|---|---|---|---|
| Rs 25,000 | 77,946 | 157,183 | **+79,237** | 2 / 15 |
| Rs 50,000 | 212,891 | 288,565 | **+75,674** | 2 / 18 |
| Rs 1,00,000 | 517,637 | 568,789 | **+51,152** | 2 / 19 |
| Rs 2,00,000 | 10,87,872 | 11,09,754 | **+21,882** | 2 / 19 |

**Arm B's net edge was positive at every cash level tested, but it
shrank steadily as the account grew -- from +Rs 79,237 at C=Rs 25,000 to
+Rs 21,882 at C=Rs 2,00,000.** Arm A's forced-close count is 2 at every
cash level; Arm B's runs 15 to 19.

**Worst single trade: exactly 2.00x.** In both arms the worst trade is
2026-02-03, at every cash level, and the ratio is exactly 2 -- checked as
an exact fraction, not a rounded decimal. Arm A / Arm B: −36,777 /
−73,554, −73,554 / −147,108, −147,108 / −294,216, −294,216 / −588,432.
Same day, same trade, double the size. That is the whole mechanism of
leverage in one line.

### The +79,237 figure needs a qualification, every time it is quoted

At C=Rs 25,000 -- and only there -- **Arm A cannot fund a single lot on
30 of the 137 trades. Arm B trades all 137.** Those rows contribute
exactly Rs 0.00 to Arm A's total and are flagged in the data
(`cash_insufficient_1lot_A`), so nothing is hidden; but the headline is
misleading without them.

**A substantial part of Arm B's largest edge is therefore
*participation* -- being able to trade at all on 30 days Arm A sits out
-- not leverage earning more per trade on the days both arms traded.**
This result must not be presented as "leverage helps small accounts
most" without that qualification. It is at least as much "an account too
small to trade benefits from anything that lets it trade."

Note also that prediction 2 -- Arm B's net advantage staying under 2x --
fails at exactly this cash level (2.02x) and holds at all three others
(1.36x, 1.10x, 1.02x).

### Calm market vs constrained market

The corrected run reports three scenarios. Two matter here:

- **S1 -- no forced closes.** Both arms record **zero** forced closes,
  in every row of the file, at every beta and haircut. This is the
  calm-market picture: what you collect if nothing ever forces you out.
- **S3 -- forced closes imposed.** The primary result, and the
  constrained picture: what is left after cash runs out intraday and the
  position gets shut.

The gap between them is what the constraint costs. **Using the sign
convention S3 minus S1** -- so a negative number is money lost to being
forced out -- at C=Rs 2,00,000 the hit is **Arm A −1,31,921, Arm B
−12,97,938.** The levered arm pays roughly ten times what the unlevered
arm pays for the same rule. That ratio, not the headline edge, is the
honest picture of what leverage costs when the constraint binds.

### What this does not answer

**This sample contains no crash.** 2024-01-04 to 2026-08-11 holds
nothing on the scale of 2024-06-04 (not an expiry day, not one of these
137 trades) or the 2020 COVID period (no real option data exists for it
anywhere in this project). Every number above describes a market that
never had a genuinely bad day for this strategy.

**The beta and haircut sensitivities did not bind below C=Rs 2,00,000.**
At C=25,000 / 50,000 / 1,00,000 the available margin equals `2C` on all
137 rows -- meaning `min(U, C)` returned the cash amount every time and
the pledged pot was never the binding constraint. The reason is
straightforward: **the haircut-adjusted pot never fell below
Rs 1,17,796 anywhere in the entire grid**, including the harshest corner
tested. A pot that never drops below Rs 1,17,796 cannot bind against
cash of Rs 25,000. Two-thirds of the sensitivity grid therefore carries
no information about beta or haircut at all.

**So the collateral-risk question remains untested.** The concern that
started this whole line of work -- that a bad day for the index is also a
bad day for the pledged shares, so the collateral shrinks at exactly the
moment the margin is needed (wrong-way risk) -- is not answered here. The
pot never got close enough to binding for the correlation to matter.
Answering it needs either a crash in the sample or a deliberately
thinner pot, and this study has neither.

**The 40% haircut sensitivity rests on an unverified secondary source**
(Business Standard, 2026-03-31), not on any SEBI, NSE or RBI primary
document. The 9% base-case haircut is primary-verified from the SEBI
Master Circular.

### Prediction 1, adjudicated: FAILED on the upside

This was the last open prediction from the study. Prediction 1 said Arm
B's **gross** premium, before forced closes, would be close to 2x Arm
A's at every cash level. Computed on scenario S1 (the no-forced-close
scenario, confirmed to be the correct "before forced closes" basis):

| Cash `C` | Arm A gross | Arm B gross | Ratio B/A |
|---|---|---|---|
| Rs 25,000 | 94,044.25 | 245,088.50 | **2.61x** |
| Rs 50,000 | 245,088.50 | 582,032.25 | **2.37x** |
| Rs 1,00,000 | 582,032.25 | 12,19,793.25 | **2.10x** |
| Rs 2,00,000 | 12,19,793.25 | 24,07,692.25 | **1.97x** |

**FAILED** -- and failed on the *upside*: Arm B's gross was **more** than
double, not less. Two of four cash levels fall outside a +/-10% band
(1.80x-2.20x).

**The +/-10% threshold was set at adjudication time, not in the
pre-registration.** That is a real weakness in the original prediction's
wording -- "close to 2x" carries no number, so nothing structurally
prevented the band from being chosen after the ratios were visible. It
is recorded as an after-the-fact convention rather than presented as
pre-registered. The C=Rs 25,000 failure at 2.61x is robust to any band a
reasonable person would have written in advance; **the C=Rs 50,000
failure at 2.37x is not** -- a +/-20% band would pass it, making the
verdict 3-of-4. The overall FAIL survives either band; the count of
failing levels does not.

**Why the ratio exceeds 2x: integer lot rounding, not participation.**
The participation gap documented above was proposed as the explanation
and does not survive checking. Sit-outs occur at C=Rs 25,000 and nowhere
else, yet C=Rs 50,000 still runs 2.37x with Arm A funding all 137
trades. Participation contributes at the smallest cash level only --
removing the 30 sit-out dates there drops the ratio from 2.61x to 2.27x,
about half the excess. The mechanism common to all four levels is
integer lot rounding: measured on tradeable rows only, so participation
is excluded entirely, `lots_B / (2 x lots_A)` runs **1.121 / 1.086 /
1.037 / 1.006** across the four cash levels -- monotone and matching the
deviation ordering exactly, including where participation explains
nothing.

With this, all six pre-registered predictions are adjudicated: **three
failed (1, 2 and 4), three held (3, 5 and 6)** -- and prediction 5 held
only trivially, since Arm B beat Arm A at every cash level tested, so it
never had to discriminate between them.
