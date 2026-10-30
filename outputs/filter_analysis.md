VIX data source used: **yfinance (^INDIAVIX)**

## Task 1 & 2: 30 Worst Open-to-Close Days (with VIX Open)

| Rank | Date | Weekday | Open | Close | Move % | Direction | VIX Open |
|---|---|---|---|---|---|---|---|
| 1 | 2020-03-13 | Friday | 9107.60 | 9955.20 | +9.31% | UP | 41.16 |
| 2 | 2020-03-25 | Wednesday | 7735.15 | 8317.85 | +7.53% | UP | 83.61 |
| 3 | 2020-03-18 | Wednesday | 9088.45 | 8468.80 | -6.82% | DOWN | 62.93 |
| 4 | 2024-06-04 | Tuesday | 23179.50 | 21884.50 | -5.59% | DOWN | 20.94 |
| 5 | 2020-03-20 | Friday | 8284.45 | 8745.45 | +5.56% | UP | 72.20 |
| 6 | 2019-09-20 | Friday | 10746.80 | 11274.20 | +4.91% | UP | 15.55 |
| 7 | 2016-11-09 | Wednesday | 8067.50 | 8432.00 | +4.52% | UP | 16.77 |
| 8 | 2020-06-12 | Friday | 9544.95 | 9972.90 | +4.48% | UP | 29.66 |
| 9 | 2020-03-12 | Thursday | 10039.95 | 9590.15 | -4.48% | DOWN | 31.56 |
| 10 | 2020-03-23 | Monday | 7945.70 | 7610.25 | -4.22% | DOWN | 67.10 |
| 11 | 2020-04-07 | Tuesday | 8446.30 | 8792.20 | +4.10% | UP | 55.30 |
| 12 | 2020-03-16 | Monday | 9587.80 | 9197.40 | -4.07% | DOWN | 51.47 |
| 13 | 2020-04-01 | Wednesday | 8584.10 | 8253.80 | -3.85% | DOWN | 64.41 |
| 14 | 2021-02-01 | Monday | 13758.60 | 14281.20 | +3.80% | UP | 25.34 |
| 15 | 2020-05-18 | Monday | 9158.30 | 8823.25 | -3.66% | DOWN | 38.02 |
| 16 | 2020-03-17 | Tuesday | 9285.40 | 8967.05 | -3.43% | DOWN | 58.88 |
| 17 | 2020-08-31 | Monday | 11777.55 | 11387.50 | -3.31% | DOWN | 18.35 |
| 18 | 2020-04-03 | Friday | 8356.55 | 8083.80 | -3.26% | DOWN | 60.05 |
| 19 | 2020-03-27 | Friday | 8949.10 | 8660.25 | -3.23% | DOWN | 71.53 |
| 20 | 2016-02-11 | Thursday | 7203.60 | 6976.35 | -3.15% | DOWN | 22.47 |
| 21 | 2020-12-21 | Monday | 13741.90 | 13328.40 | -3.01% | DOWN | 18.62 |
| 22 | 2022-06-16 | Thursday | 15832.25 | 15360.60 | -2.98% | DOWN | 22.15 |
| 23 | 2020-04-15 | Wednesday | 9196.40 | 8925.30 | -2.95% | DOWN | 51.46 |
| 24 | 2020-10-15 | Thursday | 12023.45 | 11680.35 | -2.85% | DOWN | 20.21 |
| 25 | 2020-03-09 | Monday | 10742.05 | 10451.45 | -2.71% | DOWN | 25.64 |
| 26 | 2016-03-01 | Tuesday | 7038.25 | 7222.30 | +2.61% | UP | 20.16 |
| 27 | 2020-05-27 | Wednesday | 9082.20 | 9314.95 | +2.56% | UP | 31.47 |
| 28 | 2020-05-04 | Monday | 9533.50 | 9293.50 | -2.52% | DOWN | 33.99 |
| 29 | 2020-03-19 | Thursday | 8063.30 | 8263.45 | +2.48% | UP | 63.96 |
| 30 | 2022-02-15 | Tuesday | 16933.25 | 17352.45 | +2.48% | UP | 22.98 |

## Task 3: VIX-Threshold Filter Effectiveness

Baseline (no filter) combined breach rate: **10.68%**
Days excluded from this analysis due to missing VIX data: **17**
Trading days with known VIX used below: **2596**

| VIX Open Threshold | Worst-30 Days Skipped | % of All Days Skipped | Breach Rate on Remaining Days | Avg Abs Move on Remaining Days |
|---|---|---|---|---|
| > 15 | 30 / 30 | 50.81% | 4.70% | 0.434% |
| > 18 | 28 / 30 | 26.77% | 6.79% | 0.482% |
| > 20 | 26 / 30 | 17.18% | 7.44% | 0.495% |
| > 25 | 20 / 30 | 5.08% | 8.93% | 0.523% |
| > 30 | 17 / 30 | 2.47% | 9.68% | 0.536% |

## Task 4: Breach Clustering

Longest consecutive-trading-day breach streak: **10 days**, from **2020-03-09** to **2020-03-23**

Number of 5-trading-day rolling windows containing 2+ breach days: **308**

Breach count by calendar year:

| Year | Breach Days |
|---|---|
| 2016 | 35 |
| 2017 | 7 |
| 2018 | 25 |
| 2019 | 28 |
| 2020 | 63 |
| 2021 | 34 |
| 2022 | 34 |
| 2023 | 3 |
| 2024 | 24 |
| 2025 | 12 |
| 2026 | 14 |

## Task 5: Breach Magnitude (overshoot past the boundary)

| Direction | Breach Days | Mean Overshoot | Median Overshoot | Worst Overshoot |
|---|---|---|---|---|
| Upside (> +1.11%) | 128 | 0.636% | 0.287% | 8.197% |
| Downside (< -1.27%) | 151 | 0.613% | 0.354% | 5.548% |

