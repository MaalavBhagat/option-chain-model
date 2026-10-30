# Research Journal — 2026-08-14 (regime stress test / extrapolation)

# THIS IS AN ESTIMATE, NOT A BACKTEST

Everything in this entry is a statistical extrapolation, not a
historical simulation. No option prices exist anywhere in this project
for 2016-2023 -- NSE's UDiFF bhavcopy archive begins 2024-01-01 (see
`journal/2026-08-13-pipeline-extension.md`), confirmed by direct
probing, and no substitute source was used. What follows fits a simple
relationship between index move and trade P&L using the 136 real
2024-2026 trades, then applies that same relationship to historical
index-only data (which does exist back to 2016) to produce a rough,
heavily-caveated sense of what the strategy's P&L *might* have looked
like. It is exploratory, and it does not become part of the strategy's
reference result.

## The mapping

Fit separately for the naked strangle and the winged (iron condor)
version, both using absolute index open-to-close move as the predictor
(chosen because move and P&L correlate far more strongly in absolute
value than in signed value -- correlation -0.75 vs -0.06 for the naked
strangle -- consistent with the roughly symmetric 0.5% strike
placement on both sides):

- **Naked:** P&L = 5,092.42 - 7,504.81 x abs(move %). **R-squared =
  0.560.**
- **Winged:** P&L = 4,995.93 - 8,137.40 x abs(move %). **R-squared =
  0.669.**

Both fits are statistically significant (p < 1e-24), but R-squared
0.56-0.67 means roughly a third to a half of the variation in real
trade P&L is *not* explained by move size alone -- volume, exact strike
availability, and day-to-day premium levels all matter too and aren't
captured by this one-variable model.

**The fit was estimated on moves ranging 0.01% to 2.21%.** That range
matters enormously for what follows.

## Limitations (stated plainly, per instruction)

1. **This cannot capture volatility regime changes.** The fitted line
   encodes the relationship between move size and P&L *as priced by
   the market in 2024-2026* -- a period without a crash. In a real
   volatility spike (like March 2020), implied volatility would have
   made the premium collected at entry far richer than this model
   assumes, which would change the P&L for a given move size in ways
   this linear fit has no way to know about. The model was never shown
   a single high-IV day, so it cannot extrapolate what one looks like.
2. **The winged model is extrapolated past a structurally impossible
   region without correction.** An iron condor has a hard cap on both
   maximum profit (net credit received) and maximum loss (spread width
   minus net credit) by construction -- no move, however large, can
   exceed those bounds. The raw linear fit doesn't know this and would
   predict ever-growing losses for ever-larger moves, which is
   physically impossible for this structure. **A capped version is
   used for all winged results below**, clipping the linear
   prediction at an approximate structural floor/ceiling (using the
   136-trade average net credit, Rs 3,072, and a 1.5%-of-spot spread
   width). This is a necessary correction, not an enhancement -- the
   uncapped numbers are meaningless past the wing distance.
3. **No such correction was applied to the naked model.** Its risk is
   genuinely much closer to unbounded (bounded only by the underlying
   going to zero, far outside any realistic scope here), so the raw
   linear extrapolation is used as-is. This likely understates 2020's
   true naked risk rather than overstates it, given point 1.
4. Only Thursdays (2016 - 2025-09-01) are used, matching the
   pre-2025-09-02 expiry regime. Holidays are shifted to the previous
   trading day, same convention as the real downloader.

## Naked strangle -- estimated by year (2016-2023)

| Year | Trades | Win rate | Total P&L (est.) | Worst trade (est.) | Max drawdown (est.) |
|---|---|---|---|---|---|
| 2016 | 52 | 59.6% | Rs 7,976.09 | -Rs 18,582.78 | Rs 19,509.03 |
| 2017 | 52 | 88.5% | Rs 111,799.23 | -Rs 4,960.33 | Rs 5,224.88 |
| 2018 | 52 | 82.7% | Rs 80,612.28 | -Rs 11,453.18 | Rs 19,758.18 |
| 2019 | 52 | 65.4% | Rs 47,326.45 | -Rs 10,309.66 | Rs 21,324.82 |
| **2020** | **53** | **64.2%** | **-Rs 64,279.95** | **-Rs 28,529.85** | **Rs 114,511.70** |
| 2021 | 52 | 63.5% | Rs 48,527.03 | -Rs 9,944.49 | Rs 17,522.40 |
| 2022 | 52 | 55.8% | Rs 10,073.62 | -Rs 17,264.75 | Rs 38,901.84 |
| 2023 | 52 | 80.8% | Rs 85,947.42 | -Rs 3,955.44 | Rs 3,955.44 |

## Winged (iron condor) -- estimated by year (2016-2023), structurally capped

| Year | Trades | Win rate | Total P&L (est.) | Worst trade (est.) | Max drawdown (est.) |
|---|---|---|---|---|---|
| 2016 | 52 | 53.8% | -Rs 2,755.98 | -Rs 5,500.79 | Rs 18,646.77 |
| 2017 | 52 | 84.6% | Rs 81,164.89 | -Rs 5,904.19 | Rs 6,716.78 |
| 2018 | 52 | 75.0% | Rs 55,982.49 | -Rs 7,349.39 | Rs 18,457.40 |
| 2019 | 52 | 59.6% | Rs 10,596.09 | -Rs 8,531.68 | Rs 25,929.40 |
| **2020** | **53** | **60.4%** | **-Rs 17,909.69** | **-Rs 8,650.77** | **Rs 54,938.55** |
| 2021 | 52 | 61.5% | Rs 7,852.59 | -Rs 11,308.46 | Rs 21,870.69 |
| 2022 | 52 | 53.8% | -Rs 18,934.68 | -Rs 12,364.35 | Rs 45,980.68 |
| 2023 | 52 | 76.9% | Rs 51,790.43 | -Rs 4,814.59 | Rs 4,814.59 |

## 2020, called out specifically

2020 is the only losing year for the naked strangle in this 8-year
estimate, and its estimated drawdown (Rs 114,511.70) dwarfs every other
year. But there's a specific, non-obvious reason the number isn't
worse: **the largest move among 2020's actual Thursday-expiry dates was
only 4.48%** (2020-03-12) -- not the 9.31% single-day peak from the
March 2020 crash (2020-03-13, a *Friday*), nor the 7.53% and 6.82%
moves on 2020-03-25 and 2020-03-18 (Wednesdays). Those catastrophic
days simply didn't fall on Thursdays. This is the same calendar-luck
pattern found for 2024-06-04 in the 2026-08-13 analysis, playing out
again here -- and it means even this "worst case" estimate is itself
somewhat calendar-lucky, not a true worst-case sample of 2020's
volatility.

That said, 4.48% is still roughly **2x outside the model's fitted
range** (0.01%-2.21%), so per Limitation 1, even this moderated number
should be read as directional, not precise -- real 2020 option premiums
would likely have been priced very differently than a linear
extrapolation from a calm 2024-2026 sample can capture.

## What this does and doesn't support

**Does support:** the general shape that a bad-volatility year like
2020 would have been meaningfully worse than the 2024-2026 baseline
period for the naked strangle, and that wings would have reduced (not
eliminated) that damage, consistent with the 2024-06-04 stress
scenario from the prior entry.

**Does not support:** any specific rupee figure being treated as a real
historical estimate, any claim about what 2020 premiums actually would
have been, or a conclusion that the strategy "survives" any given year
-- the R-squared of 0.56-0.67 means this model already leaves a lot
unexplained even within its own fitted range, before extrapolation
error is added on top.

Per-trade extrapolation detail: `outputs/regime_extrapolation_2016_2023.csv`.
