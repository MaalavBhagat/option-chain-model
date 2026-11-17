# Weekly strangle study — Step 8: EXPLORATORY tail analysis

**EXPLORATORY — not pre-registered.** Nothing here changes any pre-registered result, rule or file. Spot: `data/raw/nifty50_daily_v2.csv` (yfinance ^NSEI close), 2016-01-04 to 2026-11-13; the provisional 2026-11-16 row is excluded. Expiry days: the data-derived calendar used in Steps 6-7 (from 2019).

## A. EXPLORATORY — largest one-day close-to-close moves, 2016-01-04 to 2026-11-13

15 largest falls:

| Date | Weekday | Move % | Close | Weekly expiry day |
|---|---|---|---|---|
| 2020-03-23 | Mon | -12.98 | 7,610.25 | no |
| 2020-03-12 | Thu | -8.30 | 9,590.15 | yes |
| 2020-03-16 | Mon | -7.61 | 9,197.40 | no |
| 2024-06-04 | Tue | -5.93 | 21,884.50 | no |
| 2020-05-04 | Mon | -5.74 | 9,293.50 | no |
| 2020-03-18 | Wed | -5.56 | 8,468.80 | no |
| 2020-03-09 | Mon | -4.90 | 10,451.45 | no |
| 2022-02-24 | Thu | -4.78 | 16,247.95 | yes |
| 2020-03-30 | Mon | -4.38 | 8,281.10 | no |
| 2020-04-01 | Wed | -4.00 | 8,253.80 | yes |
| 2021-02-26 | Fri | -3.76 | 14,529.15 | no |
| 2020-02-28 | Fri | -3.71 | 11,201.75 | no |
| 2021-04-12 | Mon | -3.53 | 14,310.80 | no |
| 2020-05-18 | Mon | -3.43 | 8,823.25 | no |
| 2016-02-11 | Thu | -3.32 | 6,976.35 | before NIFTY weeklies (last-Thursday monthly rule: no, unverified) |

15 largest rises:

| Date | Weekday | Move % | Close | Weekly expiry day |
|---|---|---|---|---|
| 2020-04-07 | Tue | 8.76 | 8,792.20 | no |
| 2020-03-25 | Wed | 6.62 | 8,317.85 | no |
| 2020-03-20 | Fri | 5.83 | 8,745.45 | no |
| 2019-09-20 | Fri | 5.32 | 11,274.20 | no |
| 2021-02-01 | Mon | 4.74 | 14,281.20 | no |
| 2020-04-09 | Thu | 4.15 | 9,111.90 | yes |
| 2020-03-26 | Thu | 3.89 | 8,641.45 | yes |
| 2020-03-31 | Tue | 3.82 | 8,597.75 | no |
| 2025-05-12 | Mon | 3.82 | 24,924.70 | no |
| 2020-03-13 | Fri | 3.81 | 9,955.20 | no |
| 2026-04-08 | Wed | 3.78 | 23,997.35 | no |
| 2019-05-20 | Mon | 3.69 | 11,828.25 | no |
| 2016-03-01 | Tue | 3.37 | 7,222.30 | before NIFTY weeklies (last-Thursday monthly rule: no, unverified) |
| 2024-06-05 | Wed | 3.36 | 22,620.35 | no |
| 2024-06-03 | Mon | 3.25 | 23,263.90 | no |

## B. EXPLORATORY — counterfactual: each of those 30 days as an expiry day with V1 T-1 open

- Position: short call at 7% above and short put at 10% below the previous close; loss = intrinsic value at that day's close (premium received not included), as % of the previous close.
- Today's terms: loss % × spot 25,000 = points per unit; × lot 65 × lots = rupees.
- Weeks erased = loss at 10 lots ÷ average weekly V1 net profit at 10 lots in today's terms, where the average = Step 7 OOS (2024-01-04 to 2026-11-09) mean weekly net points per unit (V1, T-1, s = 1, primary) × 650 units:
  - Brokerage A: mean weekly -0.3013 pts/unit -> Rs -195.87 per week at 10 lots (Step 7 OOS rupee total at 10 lots ÷ 150 weeks, actual lot sizes: Rs -7.68)
  - Brokerage B: mean weekly 0.1653 pts/unit -> Rs 107.47 per week at 10 lots (Step 7 OOS rupee total at 10 lots ÷ 150 weeks, actual lot sizes: Rs 214.94)
  - Brokerage C: mean weekly 1.0987 pts/unit -> Rs 714.15 per week at 10 lots (Step 7 OOS rupee total at 10 lots ÷ 150 weeks, actual lot sizes: Rs 660.20)

| Date | Move % | Intrinsic loss % of prev close | Today pts/unit | Rs 1 lot(s) | Rs 10 lot(s) | Rs 100 lot(s) | Weeks erased A | Weeks erased B | Weeks erased C |
|---|---|---|---|---|---|---|---|---|---|
| 2020-03-23 | -12.98 | 2.98 | 745.12 | 48,432.57 | 484,325.74 | 4,843,257.36 | n/a (avg weekly <= 0) | 4,506.52 | 678.19 |
| 2020-03-12 | -8.30 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| 2020-03-16 | -7.61 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| 2024-06-04 | -5.93 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| 2020-05-04 | -5.74 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| 2020-03-18 | -5.56 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| 2020-03-09 | -4.90 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| 2022-02-24 | -4.78 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| 2020-03-30 | -4.38 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| 2020-04-01 | -4.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| 2021-02-26 | -3.76 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| 2020-02-28 | -3.71 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| 2021-04-12 | -3.53 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| 2020-05-18 | -3.43 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| 2016-02-11 | -3.32 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| 2020-04-07 | 8.76 | 1.76 | 440.80 | 28,652.17 | 286,521.70 | 2,865,217.01 | n/a (avg weekly <= 0) | 2,666.01 | 401.21 |
| 2020-03-25 | 6.62 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| 2020-03-20 | 5.83 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| 2019-09-20 | 5.32 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| 2021-02-01 | 4.74 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| 2020-04-09 | 4.15 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| 2020-03-26 | 3.89 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| 2020-03-31 | 3.82 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| 2025-05-12 | 3.82 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| 2020-03-13 | 3.81 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| 2026-04-08 | 3.78 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| 2019-05-20 | 3.69 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| 2016-03-01 | 3.37 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| 2024-06-05 | 3.36 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| 2024-06-03 | 3.25 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |

## C. EXPLORATORY — frequency

- Trading days 2019-01-01 to 2026-11-13 (option-file days minus Muhurat): 1,939; expiry days among them: 406; share 0.2094 (20.94%).
- Window for move counts: 2016-01-04 to 2026-11-13 = 10.86 years; 2,676 one-day moves.
- Implied chance per year = (count per year) × (expiry-day share). **This is a rough estimate**: it assumes large moves fall on any trading day with equal probability and uses a short history with very few events.

| One-day move | Count 2016-2026 | Dates | Per year | Implied per year on an expiry day |
|---|---|---|---|---|
| <= -10% | 1 | 2020-03-23 | 0.0921 | 0.0193 |
| <= -8% | 2 | 2020-03-12, 2020-03-23 | 0.1842 | 0.0386 |
| <= -7% | 3 | 2020-03-12, 2020-03-16, 2020-03-23 | 0.2763 | 0.0579 |
| >= +7% | 1 | 2020-04-07 | 0.0921 | 0.0193 |
| >= +8% | 1 | 2020-04-07 | 0.0921 | 0.0193 |

## D. EXPLORATORY — concentration: V1, T-1, s = 1 totals with the best weeks removed

- Best weeks ranked separately for each column (points per unit, and rupees at 10 lots with actual lot sizes). Skipped weeks count as 0.

| Brk | Period | Weeks | Total pts/unit | Total Rs 10 lots | pts minus best 1 | Rs minus best 1 | pts minus best 5 | Rs minus best 5 | pts minus best 10 | Rs minus best 10 |
|---|---|---|---|---|---|---|---|---|---|---|
| A | IS | 255 | 155.82 | 125,800.71 | 107.27 | 89,386.76 | 5.46 | 13,030.26 | -10.67 | 1,024.91 |
| A | OOS | 150 | -45.20 | -1,152.26 | -49.50 | -3,949.27 | -62.91 | -12,956.52 | -70.20 | -17,767.14 |
| B | IS | 255 | 254.86 | 185,154.71 | 206.00 | 148,504.76 | 102.93 | 71,204.26 | 85.06 | 58,018.91 |
| B | OOS | 150 | 24.80 | 32,241.74 | 20.14 | 29,208.73 | 5.32 | 19,257.48 | -3.68 | 13,266.86 |
| C | IS | 255 | 452.95 | 303,862.71 | 403.45 | 266,740.76 | 297.86 | 187,552.26 | 276.54 | 172,006.91 |
| C | OOS | 150 | 164.80 | 99,029.74 | 159.41 | 95,524.73 | 141.79 | 83,685.48 | 127.76 | 75,334.86 |

## E. EXPLORATORY — NSE index circuit breakers

- NSE/CMTR/24709 (2013-10-11), https://archives.nseindia.com/content/circulars/CMTR24709.pdf: index-based market-wide circuit filters at 10%, 15% and 20%, "based on the closing index value of NIFTY on the previous trading day". They halt trading for a set time (10%: 45 min before 1 PM, 15 min from 1 PM to 2:30 PM, no halt at or after 2:30 PM; 15%: 1 h 45 min before 1 PM, 45 min from 1 PM to 2 PM, market closed on or after 2 PM; 20%: market closed for the day). Trading resumes after a halt, and the expiry-day settlement uses the index closing value, so a halt does not cap the settlement move (only a 20% trigger closes the market for the day).
