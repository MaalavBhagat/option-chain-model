# Weekly strangle study — Step 4: descriptive profile

**No P&L or outcome was computed in this step.**

- No profit, loss, win rate, payoff or expiry result was computed for any leg, week or period.
- No price after an entry day was read, and no expiry-day price was read.
- The real statement's "Profit and Loss" column was never opened.
- Part A lists buy-back prices for the 3 legs that were bought back, because the task asked for them.
  Nothing was derived from them.

Run on 2026-11-16. Files:
- Scripts: `scripts/weekly_strangle/describe_real_trades.py` (Part A) and
  `scripts/weekly_strangle/describe_strike_listing.py` (Part B).
- Configs: `config/weekly_strangle/lot_size_pre2024.csv` (Part C) and
  `config/weekly_strangle/event_calendar_2019_2023.csv` (Part D).

Conventions:
- **Trading days**: NSE bhavcopy dates plus yfinance NIFTY dates, minus **Muhurat sessions**. The Muhurat
  dates used are 2019-10-27, 2020-11-14, 2021-11-04, 2022-10-24, 2023-11-12, 2024-11-01, 2025-10-21 and
  2026-11-08.
  - Check from the data: each weekday Muhurat date on disk was the **lowest-volume day of its year** (9–27%
    of a median day).
  - The Sunday 2026-11-08 session was 46% of a median day (12th lowest of 2026).
- **% OTM**: calls = strike / spot − 1; puts = 1 − strike / spot.
- **Spot**: the NIFTY close on that day (bhavcopy `UndrlygPric` for 2024+, yfinance close for 2019–2023).

## PART A — profile of the real NIFTY legs (statement in `data/private/`, not committed)

Method:
- Only the statement's symbol, quantity, average and amount columns were read. The header area and the
  client-code column were never read or printed.
- 59 NIFTY legs: 33 calls and 26 puts, across 31 expiries from 2026-03-30 to 2026-11-17.
  - 54 legs were held to expiry, 3 were bought back and 2 are still open (the 17 Nov 2026 pair).
  - SENSEX legs are excluded.
- **Sell price** is the statement's sell average (sell amount ÷ sell quantity).
  - For NIFTY these averages sit ₹0.0115 per unit below the traded price (found in Step 2).
  - So the entry-day match allows `LOW − 0.012 ≤ sell price ≤ HIGH`, on days the contract traded.
  - The 30 Mar 2026 leg was sold in the previous FY; its price is the opening average.
- **Lots** = quantity ÷ that day's `NewBrdLotQty` (65 throughout).
- **Entry inference** uses the T-1 to T-5 bhavcopies only. T-1 for the 17 Nov expiry (2026-11-16) has
  no bhavcopy yet.

### All NIFTY legs

| Expiry | Type | Strike | Qty | Lots | Sell price | Buy-back price | Status | Spot T-1 | %OTM T-1 | %OTM T-2 | %OTM T-3 | %OTM T-4 | Inferred entry |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2026-03-30 | CE | 25,800 | 650 | 10 | 0.8500 (prev FY) | — | held to expiry | 22,819.60 | 13.06 | 10.70 | 12.60 | 14.60 | T-1 |
| 2026-04-07 | CE | 24,500 | 585 | 9 | 0.5385 | — | held to expiry | 22,968.25 | 6.67 | 7.87 | 8.03 | 9.71 | NO_MATCH |
| 2026-04-28 | CE | 25,400 | 520 | 8 | 0.5385 | — | held to expiry | 24,092.70 | 5.43 | 6.29 | 5.08 | 4.19 | NO_MATCH |
| 2026-05-05 | CE | 25,800 | 585 | 9 | 0.2885 | — | held to expiry | 24,119.30 | 6.97 | 7.51 | 6.71 | 7.52 | NO_MATCH |
| 2026-05-12 | CE | 25,700 | 520 | 8 | 0.5385 | — | held to expiry | 23,815.85 | 7.91 | 6.30 | 5.65 | 5.63 | T-1 |
| 2026-05-26 | CE | 25,500 | 910 | 14 | 0.3885 | — | held to expiry | 24,031.70 | 6.11 | 7.51 | 7.80 | 7.78 | NO_MATCH |
| 2026-05-26 | PE | 21,000 | 650 | 10 | 0.5885 | — | held to expiry | 24,031.70 | 12.62 | 11.46 | 11.22 | 11.24 | T-1 |
| 2026-06-02 | CE | 25,200 | 325 | 5 | 0.4385 | — | held to expiry | 23,382.60 | 7.77 | 7.02 | 5.41 | 5.38 | NO_MATCH |
| 2026-06-02 | CE | 25,500 | 585 | 9 | 0.6885 | — | held to expiry | 23,382.60 | 9.06 | 8.29 | 6.66 | 6.63 | T-1 |
| 2026-06-09 | CE | 25,300 | 650 | 10 | 1.0385 | — | held to expiry | 23,123.00 | 9.41 | 8.27 | 8.04 | 8.09 | AMBIGUOUS: T-1/T-2/T-3 |
| 2026-06-16 | CE | 25,000 | 455 | 7 | 0.4385 | — | held to expiry | 23,853.90 | 4.80 | 5.83 | 7.94 | 7.69 | NO_MATCH |
| 2026-06-16 | PE | 21,200 | 195 | 3 | 1.7885 | — | held to expiry | 23,853.90 | 11.13 | 10.26 | 8.47 | 8.68 | AMBIGUOUS: T-2/T-3/T-4 |
| 2026-06-16 | PE | 22,000 | 260 | 4 | 0.8885 | — | held to expiry | 23,853.90 | 7.77 | 6.87 | 5.02 | 5.23 | T-1 |
| 2026-06-23 | CE | 25,800 | 845 | 13 | 0.4885 | — | held to expiry | 24,102.90 | 7.04 | 7.44 | 6.75 | 7.12 | T-1 |
| 2026-06-23 | PE | 21,500 | 455 | 7 | 1.0885 | — | held to expiry | 24,102.90 | 10.80 | 10.47 | 11.04 | 10.74 | AMBIGUOUS: T-2/T-3 |
| 2026-06-30 | CE | 25,700 | 845 | 13 | 0.5385 | — | held to expiry | 23,946.25 | 7.32 | 6.83 | 6.99 | 7.87 | T-1 |
| 2026-06-30 | PE | 21,500 | 390 | 6 | 1.0385 | — | held to expiry | 23,946.25 | 10.22 | 10.63 | 10.50 | 9.76 | T-2 |
| 2026-07-07 | CE | 25,500 | 910 | 14 | 0.6885 | — | held to expiry | 24,430.35 | 4.38 | 5.06 | 5.48 | 6.22 | AMBIGUOUS: T-1/T-2/T-3 |
| 2026-07-07 | PE | 21,500 | 455 | 7 | 0.8885 | — | held to expiry | 24,430.35 | 11.99 | 11.42 | 11.07 | 10.44 | AMBIGUOUS: T-2/T-3 |
| 2026-07-14 | CE | 25,700 | 650 | 10 | 0.6385 | — | held to expiry | 24,211.00 | 6.15 | 6.17 | 7.25 | 7.61 | AMBIGUOUS: T-1/T-2 |
| 2026-07-14 | PE | 21,500 | 390 | 6 | 0.6385 | — | held to expiry | 24,211.00 | 11.20 | 11.18 | 10.28 | 9.97 | T-1 |
| 2026-07-21 | CE | 26,000 | 390 | 6 | 0.3885 | — | held to expiry | 24,238.50 | 7.27 | 6.85 | 8.01 | 7.98 | AMBIGUOUS: T-1/T-2 |
| 2026-07-21 | PE | 21,600 | 650 | 10 | 1.0885 | — | held to expiry | 24,238.50 | 10.89 | 11.24 | 10.27 | 10.29 | AMBIGUOUS: T-3/T-4 |
| 2026-07-28 | CE | 25,200 | 845 | 13 | 1.0885 | — | held to expiry | 23,995.95 | 5.02 | 6.03 | 5.57 | 5.02 | AMBIGUOUS: T-1/T-2 |
| 2026-07-28 | PE | 21,300 | 455 | 7 | 0.4385 | — | held to expiry | 23,995.95 | 11.24 | 10.38 | 10.77 | 11.24 | T-1 |
| 2026-08-04 | CE | 25,500 | 455 | 7 | 0.3385 | — | held to expiry | 24,774.30 | 2.93 | 4.58 | 4.86 | 5.15 | NO_MATCH |
| 2026-08-04 | PE | 21,600 | 715 | 11 | 0.5885 | — | held to expiry | 24,774.30 | 12.81 | 11.42 | 11.17 | 10.93 | T-1 |
| 2026-08-11 | CE | 26,500 | 650 | 10 | 0.3885 | — | held to expiry | 24,583.80 | 7.79 | 7.85 | 7.57 | 7.62 | T-1 |
| 2026-08-11 | PE | 21,700 | 650 | 10 | 0.5385 | — | held to expiry | 24,583.80 | 11.73 | 11.68 | 11.92 | 11.88 | AMBIGUOUS: T-2/T-3 |
| 2026-08-18 | CE | 26,000 | 585 | 9 | 0.5385 | — | held to expiry | 24,287.65 | 7.05 | 6.71 | 6.58 | 6.40 | AMBIGUOUS: T-1/T-2/T-3 |
| 2026-08-18 | PE | 22,200 | 715 | 11 | 0.3885 | — | held to expiry | 24,287.65 | 8.60 | 8.89 | 9.00 | 9.15 | T-1 |
| 2026-08-25 | CE | 25,700 | 650 | 10 | 0.5385 | — | held to expiry | 24,219.05 | 6.11 | 5.97 | 6.06 | 6.74 | AMBIGUOUS: T-1/T-2/T-3 |
| 2026-08-25 | PE | 21,600 | 715 | 11 | 0.4885 | — | held to expiry | 24,219.05 | 10.81 | 10.94 | 10.86 | 10.29 | AMBIGUOUS: T-1/T-2 |
| 2026-09-01 | CE | 25,800 | 845 | 13 | 0.2885 | — | held to expiry | 24,080.40 | 7.14 | 6.72 | 7.09 | 6.58 | T-1 |
| 2026-09-01 | PE | 22,000 | 975 | 15 | 0.3385 | — | held to expiry | 24,080.40 | 8.64 | 9.00 | 8.68 | 9.12 | T-1 |
| 2026-09-08 | CE | 25,500 | 780 | 12 | 0.5385 | — | held to expiry | 23,779.15 | 7.24 | 6.70 | 6.81 | 6.63 | AMBIGUOUS: T-1/T-2 |
| 2026-09-08 | PE | 22,300 | 1,040 | 16 | 1.4885 | — | held to expiry | 23,779.15 | 6.22 | 6.69 | 6.59 | 6.75 | AMBIGUOUS: T-3/T-4 |
| 2026-09-15 | CE | 25,000 | 1,105 | 17 | 0.8385 | — | held to expiry | 23,398.10 | 6.85 | 6.48 | 6.69 | 5.77 | AMBIGUOUS: T-1/T-2 |
| 2026-09-15 | PE | 21,700 | 845 | 13 | 0.7885 | — | held to expiry | 23,398.10 | 7.26 | 7.57 | 7.39 | 8.19 | AMBIGUOUS: T-1/T-2 |
| 2026-09-22 | CE | 24,600 | 650 | 10 | 0.5385 | — | held to expiry | 23,414.30 | 5.06 | 5.37 | 5.71 | 5.95 | T-1 |
| 2026-09-22 | PE | 21,500 | 585 | 9 | 1.3385 | — | held to expiry | 23,414.30 | 8.18 | 7.91 | 7.61 | 7.40 | AMBIGUOUS: T-2/T-3 |
| 2026-09-29 | CE | 24,900 | 780 | 12 | 0.4385 | — | held to expiry | 22,780.25 | 9.31 | 7.60 | 7.96 | 6.20 | T-1 |
| 2026-09-29 | PE | 21,000 | 780 | 12 | 0.4885 | — | held to expiry | 22,780.25 | 7.81 | 9.25 | 8.95 | 10.44 | T-1 |
| 2026-10-06 | CE | 24,500 | 910 | 14 | 0.4385 | — | held to expiry | 22,555.75 | 8.62 | 9.27 | 8.31 | 7.85 | T-1 |
| 2026-10-06 | PE | 20,700 | 845 | 13 | 0.7885 | — | held to expiry | 22,555.75 | 8.23 | 7.68 | 8.49 | 8.88 | T-1 |
| 2026-10-13 | CE | 24,000 | 845 | 13 | 0.5885 | — | held to expiry | 22,363.35 | 7.32 | 6.57 | 7.95 | 6.18 | AMBIGUOUS: T-1/T-2 |
| 2026-10-13 | PE | 20,200 | 845 | 13 | 0.6885 | 0.6615 | bought back | 22,363.35 | 9.67 | 10.30 | 9.14 | 10.63 | AMBIGUOUS: T-1/T-2 |
| 2026-10-19 | CE | 24,200 | 650 | 10 | 0.4885 | — | held to expiry | 23,146.15 | 4.55 | 5.23 | 6.97 | 6.50 | NO_MATCH |
| 2026-10-19 | PE | 20,200 | 845 | 13 | 1.6423 | — | held to expiry | 23,146.15 | 12.73 | 12.16 | 10.71 | 11.10 | AMBIGUOUS: T-2/T-3/T-4 |
| 2026-10-27 | CE | 25,000 | 715 | 11 | 0.3885 | — | held to expiry | 22,753.20 | 9.87 | 10.62 | 10.19 | 9.59 | T-1 |
| 2026-10-27 | PE | 20,500 | 845 | 13 | 1.0385 | 0.8615 | bought back | 22,753.20 | 9.90 | 9.29 | 9.64 | 10.13 | AMBIGUOUS: T-1/T-2/T-3 |
| 2026-11-03 | CE | 24,200 | 455 | 7 | 1.2385 | — | held to expiry | 23,440.80 | 3.24 | 4.98 | 5.51 | 6.61 | AMBIGUOUS: T-2/T-3/T-4 |
| 2026-11-03 | PE | 20,200 | 390 | 6 | 0.9885 | — | held to expiry | 23,440.80 | 13.83 | 12.38 | 11.93 | 11.01 | AMBIGUOUS: T-2/T-3 |
| 2026-11-03 | PE | 20,500 | 260 | 4 | 2.5885 | — | held to expiry | 23,440.80 | 12.55 | 11.07 | 10.62 | 9.69 | AMBIGUOUS: T-4/T-5 |
| 2026-11-09 | CE | 26,100 | 195 | 3 | 1.2385 | 7.2115 | bought back | 25,030.35 | 4.27 | 6.37 | 8.93 | 9.61 | AMBIGUOUS: T-1/T-3 |
| 2026-11-09 | CE | 27,000 | 195 | 3 | 0.6885 | — | held to expiry | 25,030.35 | 7.87 | 10.04 | 12.68 | 13.39 | NO_MATCH |
| 2026-11-09 | PE | 20,500 | 845 | 13 | 1.1885 | — | held to expiry | 25,030.35 | 18.10 | 16.45 | 14.44 | 13.90 | AMBIGUOUS: T-2/T-3 |
| 2026-11-17 | CE | 27,900 | 390 | 6 | 0.7885 | — | open | — | — | 10.96 | 10.28 | 10.47 | T-2 |
| 2026-11-17 | PE | 22,000 | 715 | 11 | 1.3385 | — | open | — | — | 12.51 | 13.04 | 12.89 | AMBIGUOUS: T-2/T-3 |

### Summary

- **% OTM, calls (33 legs)**, median [min, max]:
  - T-1 7.05 [2.93, 13.06]; T-2 6.72 [4.58, 10.96]; T-3 6.99 [4.86, 12.68]; T-4 6.74 [4.19, 14.60].
  - At the unambiguously inferred entry day (n = 12): median **8.27**, range [5.06, 13.06].
- **% OTM, puts (26 legs)**, median [min, max]:
  - T-1 10.81 [6.22, 18.10]; T-2 10.55 [6.69, 16.45]; T-3 10.39 [5.02, 14.44]; T-4 10.29 [5.23, 13.90].
  - At the unambiguously inferred entry day (n = 10): median **9.63**, range [7.77, 12.81].
- **Inferred entry day (59 legs)**:

| Result | Legs |
|---|---|
| T-1 only | 20 |
| T-2 only | 2 |
| AMBIGUOUS, several days | 28 (T-1/T-2 9; T-2/T-3 7; T-1/T-2/T-3 5; T-2/T-3/T-4 3; T-3/T-4 2; T-4/T-5 1; T-1/T-3 1) |
| NO_MATCH | 9 |

- A NO_MATCH means the price was outside the day's range on every T-1 to T-5 day. Likely causes are a
  multi-fill average or an entry before T-5. Neither can be resolved without trade dates.
- Taken together, single-day matches point mostly to T-1. Ambiguous matches mostly involve T-1 to T-3.
- **Weeks by side (31 expiries)**: both sides in **24**, call-only in **7**, put-only in **0**.
- **Premium per unit at sale** (statement average, points):
  - Calls: median **0.5385** [0.2885, 1.2385].
  - Puts: median **0.8885** [0.3385, 2.5885].
  - For NIFTY, about ₹0.0115 below the traded price.
- **Lots per leg**: median 10 [3, 17], at lot size 65 in every case.

## PART B — strike listing and premium levels, 2019-02-14 → 2026-11-09

Method:
- **405 weekly expiries** (255 from the legacy data, 150 from UDiFF), each with entry days T-1, T-2 and T-4.
  - 1,209 entry days were described.
  - 6 were skipped: 2019-02-13 and 2019-03-29 have no spot price; 2019-02-08 (T-4 of the first weekly)
    has no listed contract; the 3 entry days of the holiday-shifted 2023-06-28 expiry have contracts
    still labelled with the original 29-Jun date.
- **Expiry calendar**: data-derived (a date whose own file lists NIFTY options expiring that day). That
  file was used for the calendar fact only, never for a price.
- **Prices** come from the entry-day file only. "Traded" means volume (contracts) > 0. Band prices are the
  entry-day CLOSE of traded strikes in the band.

### 1. Furthest traded strike, % OTM from entry-day spot (median by year)

| Year | Call T-1 | Call T-2 | Call T-4 | Put T-1 | Put T-2 | Put T-4 |
|---|---|---|---|---|---|---|
| 2019 | 14.02 | 14.18 | 13.23 | 17.79 | 18.14 | 17.07 |
| 2020 | 14.40 | 14.64 | 14.48 | 25.82 | 25.19 | 24.89 |
| 2021 | 10.45 | 10.36 | 10.63 | 17.38 | 17.42 | 16.21 |
| 2022 | 13.18 | 13.58 | 12.99 | 16.71 | 16.47 | 17.14 |
| 2023 | 9.55 | 9.59 | 10.01 | 11.70 | 11.51 | 10.90 |
| 2024 | 9.15 | 8.66 | 8.70 | 10.97 | 11.10 | 10.96 |
| 2025 | 8.42 | 8.88 | 8.82 | 9.48 | 9.55 | 9.37 |
| 2026 | 11.47 | 10.70 | 10.91 | 10.98 | 10.97 | 10.93 |
| All years | 11.27 | 11.14 | 11.34 | 14.23 | 14.13 | 13.61 |

### 2. Median entry-day close (points) of traded strikes in each band

Each figure is the median, across the year, of each entry day's median.

| Year | CE 3–6% T-1/T-2/T-4 | CE 6–10% T-1/T-2/T-4 | PE 6–8% T-1/T-2/T-4 | PE 8–10% T-1/T-2/T-4 | PE 10–14% T-1/T-2/T-4 |
|---|---|---|---|---|---|
| 2019 | 0.40 / 0.84 / 1.72 | 0.30 / 0.48 / 0.75 | 0.62 / 1.09 / 2.25 | 0.48 / 0.76 / 1.48 | 0.38 / 0.65 / 1.14 |
| 2020 | 1.02 / 1.85 / 4.20 | 0.62 / 0.95 / 1.50 | 1.25 / 2.40 / 5.75 | 0.90 / 1.70 / 3.65 | 0.66 / 1.15 / 2.25 |
| 2021 | 1.08 / 1.65 / 2.96 | 0.69 / 1.06 / 1.59 | 0.75 / 1.48 / 3.20 | 0.70 / 1.19 / 2.05 | 0.55 / 0.94 / 1.55 |
| 2022 | 0.88 / 1.40 / 3.56 | 0.50 / 0.79 / 1.36 | 0.80 / 1.35 / 2.90 | 0.62 / 1.00 / 1.85 | 0.48 / 0.80 / 1.35 |
| 2023 | 0.52 / 0.95 / 1.68 | 0.35 / 0.65 / 1.00 | 0.55 / 1.02 / 1.72 | 0.50 / 0.85 / 1.35 | 0.45 / 0.72 / 0.95 |
| 2024 | 0.52 / 1.01 / 1.95 | 0.40 / 0.70 / 1.08 | 0.45 / 1.17 / 2.47 | 0.40 / 0.90 / 1.88 | 0.35 / 0.80 / 1.42 |
| 2025 | 0.80 / 1.02 / 1.90 | 0.60 / 0.70 / 1.10 | 0.70 / 1.08 / 2.10 | 0.55 / 0.90 / 1.70 | 0.50 / 0.70 / 1.52 |
| 2026 | 1.15 / 1.85 / 3.88 | 0.60 / 0.72 / 1.10 | 1.05 / 1.60 / 3.05 | 0.70 / 1.20 / 2.34 | 0.57 / 0.85 / 1.70 |
| All years | 0.75 / 1.20 / 2.30 | 0.45 / 0.75 / 1.15 | 0.70 / 1.33 / 2.55 | 0.60 / 1.00 / 1.85 | 0.50 / 0.85 / 1.45 |

### 3. % of entry days with NO traded strike in the band

| Year | CE 3–6% | CE 6–10% T-1/T-2/T-4 | PE 6–8% T-1/T-2/T-4 | PE 8–10% T-1/T-2/T-4 | PE 10–14% T-1/T-2/T-4 |
|---|---|---|---|---|---|
| 2019 | 0 | 0 / 0 / 2.3 | 0 / 0 / 0 | 0 / 0 / 6.8 | 4.4 / 6.5 / 13.6 |
| 2020 | 0 | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 | 1.9 / 1.9 / 1.9 |
| 2021 | 0 | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 1.9 | 1.9 / 3.8 / 5.8 |
| 2022 | 0 | 0 / 0 / 0 | 0 / 0 / 1.9 | 0 / 0 / 3.8 | 3.8 / 3.8 / 9.6 |
| 2023 | 0 | 0 / 0 / 2.0 | 0 / 0 / 0 | 2.0 / 3.9 / 3.9 | 31.4 / 33.3 / 39.2 |
| 2024 | 0 | 0 / 0 / 1.9 | 1.9 / 0 / 1.9 | 11.5 / 13.5 / 15.4 | 28.8 / 32.7 / 30.8 |
| 2025 | 0 | 0 / 0 / 0 | 0 / 0 / 1.9 | 9.4 / 18.9 / 24.5 | 58.5 / 56.6 / 58.5 |
| 2026 | 0 | 0 / 0 / 0 | 0 / 0 / 4.4 | 13.3 / 15.6 / 11.1 | 33.3 / 37.8 / 37.8 |
| All years | 0 | 0 / 0 / 0.75 | 0.25 / 0 / 1.24 | 4.47 / 6.44 / 8.46 | 20.6 / 22.0 / 24.6 |

### Descriptive observations (no outcome implied)

- **Band availability**:
  - Calls at 3–6% and 6–10% OTM, and puts at 6–8%, have a traded strike on almost every entry day in
    every year.
  - **Puts at 10–14% OTM are often absent from 2023 onward**: 31–39% of entry days in 2023, 29–33% in
    2024, 57–59% in 2025 and 33–38% in 2026. In 2019–2022 the figure was 2–14%.
  - Puts at 8–10% are also missing on 9–25% of entry days in 2024–2026.
- **Strike range**: the furthest traded strike moved in from roughly 13–14% (calls) and 17–26% (puts) in
  2019–2022 to roughly 8.5–11% for both in 2023–2025.
- **Premium levels**:
  - Band premiums at T-1 are well under 1 point in most years: medians of 0.3–1.2 points for every band
    except CE 3–6% and PE 6–8% in 2020/2021/2026.
  - Premiums roughly double from T-1 to T-2, and double again from T-2 to T-4.
  - 2020 has the highest premiums in every band.

## PART C — pre-2024 NIFTY lot sizes (`config/weekly_strangle/lot_size_pre2024.csv`)

Both circulars were read in full from `archives.nseindia.com`.

| Period | Lot | Circular | Status | Rule for existing contracts |
|---|---|---|---|---|
| 2015-08-28 → last expiry 2021-07-22 | **75** | **NSE/FAOP/30449**, dated 2015-08-07, effective 2015-08-28 | VERIFIED | 25 → 75 for contracts expiring Nov 2015 and later; the Sep and Oct 2015 contracts kept 25. In force throughout 2019-02-14 → mid-2021 |
| 2021-04-30 → 2024-04-25 | **50** | **NSE/FAOP/47854**, dated 2021-03-31, effective 2021-04-30 | VERIFIED | **Applied by contract, not by trade date** (see below) |
| End of the 50 regime | 50 | NSE/FAOP/61415 (2024-04-02) | VERIFIED | Its "present market lot" is 50; 25 for every contract trading from 2024-04-26 (Step 2) |

How NSE/FAOP/47854 applied the 75 → 50 change:
- The July 2021 monthly (expiring 2021-07-29) and later monthlies: 50.
- Weeklies from the August 2021 series (first 2021-08-05): 50.
- The May and June 2021 contracts and the July 2021 weeklies (to 2021-07-22): kept 75.
- Existing long-dated options: revised 75 → 50 after the 2021-06-25 expiry.
- So **both lot sizes traded side by side from 2021-04-30 to 2021-07-22**.

Comparison with Step 3's turnover-implied lot, recomputed **per contract**:
- Every NIFTY expiry up to 2021-07-22 shows 75, including the July 2021 weeklies.
- The July 2021 monthly and every later expiry show 50.
- The September 2021 long-dated contract shows 75 before 2021-06-25 and 50 after.
- **This matches FAOP/47854 exactly.**
- Step 3's day-level reading ("50 from 2021-07-01") blended several contracts and is superseded. The
  turnover rows are kept in the CSV with status INFERRED_FROM_TURNOVER.
- One note on the CSV: it adds a `notes` column, beyond the six requested, to record the rule for
  existing contracts.

## PART D — event calendar 2019–2023 (`config/weekly_strangle/event_calendar_2019_2023.csv`)

Format:
- Same four columns as `config/event_calendar.csv` (date, event_type, description, source_url), plus a
  fifth column, `status`.
- **80 rows: 76 VERIFIED, 4 SECONDARY.**

| Event type | Rows | Primary source | Status |
|---|---|---|---|
| US Fed FOMC | 42 | federalreserve.gov statement page for each date; every URL returned HTTP 200, and the dates match the Fed's FOMC historical / calendar pages | VERIFIED |
| RBI MPC | 31 | rbi.org.in Governor's statement or MPC resolution, from RBI's Monetary Policy page (FY2018-19 to FY2023-24) | VERIFIED |
| Union Budget | 6 | PIB releases for 2021 and 2023; indiabudget.gov.in year pages for the other four | 2 VERIFIED, 4 SECONDARY |
| Lok Sabha Election Result | 1 | PIB release of ECI/PN/58/2019 | VERIFIED |

FOMC (42 rows):
- All scheduled meetings from 2019-01-30 to 2023-12-13.
- Plus the unscheduled 2020-03-03 and 2020-03-15 cuts, and the 2020-03-23 asset-purchase statement.
- Left out: the non-meeting 2019-10-11 bill-purchase, 2020-03-31 repo-facility and 2020-08-27 framework
  statements.
- The **date is the US date**. Statements come out at 2:00 pm ET, after the Indian close, so Indian
  markets react the next session.

RBI MPC (31 rows):
- Six a year, plus the off-cycle 2020-03-27, 2020-05-22 and 2022-05-04 decisions.
- The date is the announcement (last meeting) day, taken from the statement title or the dated minutes.
- Left out: two non-MPC Governor statements, an undated FY2020-21 one (Id 3853) and 2021-05-05.

Union Budget (6 rows):
- 2019-02-01 (interim), 2019-07-05, 2020-02-01, 2021-02-01, 2022-02-01, 2023-02-01.
- 2021-02-01 and 2023-02-01 are VERIFIED from PIB releases posted those days.
- The other four link to the official indiabudget.gov.in page for that year. That page does not print the
  presentation date (it's in the speech PDF, which wasn't read), so these rows are **SECONDARY**.

Lok Sabha Election Result (1 row):
- 2019-05-23. PIB carried ECI/PN/58/2019 on 2019-05-22: "The Counting of Votes … shall be held on 23rd
  May, 2019".

## Open items for the pre-registration

- Entry day cannot be pinned down for 37 of the 59 real legs (28 ambiguous, 9 no match) without trade
  dates. Contract notes would settle it.
- The 4 SECONDARY budget dates need the speech PDFs or PIB releases.
- No outcome or P&L has been looked at for any period. The pre-registration can still be written blind.
