# Weekly strangle study — Step 1: data inventory (read-only)

Study under consideration: **NIFTY weekly short strangle, held to expiry.**
Sell a deep-OTM call (~6–10% above spot) and a deep-OTM put (~8–14% below spot)
1, 2 or 4 trading days before expiry ("T-1 / T-2 / T-4"). Hold to expiry. Test at
1, 10 and 100 lots per leg.

Audit date: 2026-11-16. Nothing in the repo was modified. All numbers below were
computed directly from the files on disk by a throw-away script that read the 647
raw bhavcopy zips (kept outside the repo). No strategy or backtest code was written.

Definitions used throughout:
- **Spot** = `UndrlygPric` from the bhavcopy row. This is the NIFTY 50 index close
  for that trading day. On all 644 days that overlap the yfinance file, it equals
  the yfinance `Close` to within ₹0.001.
- **% OTM**: calls = strike / spot − 1. Puts = 1 − strike / spot.
- **Entry day T-k** = the k-th NSE trading day before the expiry date, counted
  through the trading dates that actually have a bhavcopy file.
- **Units** = `TtlTradgVol × NewBrdLotQty`. `TtlTradgVol` is in **contracts (lots)**,
  not units. This was checked on every traded row: `TtlTrfVal / (TtlTradgVol × (strike + premium))`
  divided by the lot size has a 1st/50th/99th percentile of 0.997 / 1.000 / 1.002.
  `OpnIntrst` is already in units.
- **Stale** = the day's `ClsPric` equals `PrvsClsgPric`, NSE's own previous-day
  close for the same contract.

---

## 1. Every data file / folder in the repo

| Path | Format | Rows | Date range | Size | Tracked in git? |
|---|---|---|---|---|---|
| `data/raw/BhavCopy_NSE_FO_0_0_0_YYYYMMDD_F_0000.csv.zip` (647 files) | Zipped CSV, NSE UDiFF "Common Bhavcopy Final", 34 columns. Whole F&O segment (all underlyings). | 25,046,464 in total; 27,170–65,847 per file (median 36,794). **NIFTY index-option rows: 1,062,340** (1,430–2,213 per day, median 1,608). NIFTY index-future rows: 1,941 | 2024-01-01 → 2026-08-14 (647 trading days: 246 in 2024, 249 in 2025, 152 in 2026) | 802,347,986 bytes (765 MiB). 828,139–2,061,804 bytes per file | No (gitignored, `data/raw/*.zip`) |
| `data/raw/download_all_days_manifest.csv` | CSV (date, status, http_status, timestamp) | 647 (448 downloaded, 199 already_present, 0 failed) | 2024-01-01 → 2026-08-14 | 30,842 B | Yes |
| `data/raw/download_manifest.csv` | CSV, expiry-day downloader log | 210 (109 success, 7 success_holiday_shifted, 62 skipped_existing, 32 failed) | 2023-01-05 → 2026-08-12 (all 2023 attempts are HTTP 404) | 43,150 B | Yes |
| `data/raw/nifty50_daily.csv` | CSV: Date, Adj Close, Close, High, Low, Open, Volume (yfinance `^NSEI`) | 2,613 | 2016-01-04 → 2026-08-11 | 235,864 B | No (gitignored) |
| `data/raw/nifty50_daily_SOURCE.txt` | Text provenance note (Yahoo Finance, downloaded 2026-08-12) | — | — | 163 B | Yes |
| `data/raw/BhavCopy_..._20260811_F_0000.csv_SOURCE.txt` | Text provenance note (NSE archive URL, downloaded 2026-08-12) | — | — | 171 B | Yes |
| `data/processed/nifty_expiry_day_chains.csv` | CSV, 13 columns: TradDt, XpryDt, StrkPric, OptnTp, OHLC, TtlTradgVol, OpnIntrst, UndrlygPric, NIFTY_Open, NIFTY_Close | 27,822 | 2024-01-04 → 2026-08-11, **136 dates, same-day-expiry rows only** (TradDt = XpryDt on every row). It is missing 2025-10-20, which `src/build_corrected_baseline.py` adds separately. | 2,898,528 B | No (gitignored) |
| `config/lot_size_history.csv` | CSV, date-range lot-size table with circular URLs | 5 | 2024-01-01 → open-ended | 2,568 B | Yes |
| `config/event_calendar.csv` | CSV, cited scheduled events | 47 | 2024-02-01 → 2026-07-30 | 9,156 B | Yes |
| `config/*.json` (7 files) | Strategy / experiment parameters | — | — | — | Yes |
| `outputs/` (31 files) | Result artifacts from earlier studies: CSV, TXT, MD, PNG. Not input data. | e.g. `backtest_trades_137.csv` 137 rows, `everyday_results.csv` 1,295 rows | 2016-01-07 (regime-extrapolation estimate) → 2026-08-14 | 7,988,089 B in total | Yes |

**Not present anywhere in the repo:** any option data before 2024-01-01, any intraday
data, any bid/ask or order-book data, any India VIX file, and any NIFTY futures
file other than the IDF rows inside the bhavcopies.

## 2. Frequency of each dataset

| Dataset | Frequency |
|---|---|
| NSE F&O bhavcopy (options + futures) | **End-of-day only**: one row per contract per trading day, session `F1`. There are no intraday bars. |
| `nifty50_daily.csv` | End-of-day (daily OHLC) |
| `nifty_expiry_day_chains.csv` | End-of-day (derived from the bhavcopy) |
| Anything 1-minute or tick-level | **None in the repo** |

Each option row has an open and a close for that day, but nothing in between. Intraday
stop-losses, intraday entry times and the intraday path of a position therefore cannot be
reconstructed from this data.

## 3. Option chain coverage

### 3a. Non-expiry days (T-1, T-2, T-4)

**Yes.** Every trading day from 2024-01-01 to 2026-08-14 is on disk, not only expiry
days. Each file carries the full NIFTY option chain for every listed expiry: 167
distinct expiries appear, the furthest dated 2031-06-24.

There are 137 weekly expiries with same-day-expiry rows, 2024-01-04 → 2026-08-11.
Each expiry's own contracts were checked on the trading days before it:

| Entry day | Expiries whose chain is present on that day | Calendar days held (min / median / max) |
|---|---|---|
| T-1 | **137 / 137** | 1 / 1 / 4 |
| T-2 | **137 / 137** | 2 / 2 / 5 |
| T-4 | **136 / 137** (the only miss: the 2024-01-04 expiry, whose T-4 falls before 2024-01-01) | 5 / 6 / 8 |

That gives 410 usable (expiry, entry-day) pairs.

Caveats on how the entry days fall:
- 35 of the 136 T-4 entry days are themselves the previous week's expiry day.
- The T-k count runs through three special sessions that NSE published as normal bhavcopies:
  Saturday 2025-02-01 (Budget day), 2024-11-01 and 2025-10-21 (Muhurat sessions,
  which were the two lowest-volume days in the dataset). 2024-11-01 is T-4 for the
  2024-11-07 expiry, and 2025-10-21 is T-4 for the 2025-10-28 expiry.
- The new study's pre-registration must decide whether these sessions count as trading days.

**Requested sample periods:** Mar 2020 and Feb–Mar 2022 are **not present**. NSE's
UDiFF archive starts at 2024-01-01, and every 2023 probe in `download_manifest.csv`
returned HTTP 404. Jun 2024 is present: the 2024-06-06 expiry is included below, and
its T-2 entry day is 2024-06-04, the −5.59% election-result day.

### 3b. Furthest OTM strike listed on each entry day — 10 sample expiries

The sample is 10 expiries evenly spaced across the 137, with the nearest one swapped
for 2024-06-06. In every case below, the furthest *listed* strike was also the furthest
strike with non-zero volume.

| Expiry | Entry | Entry date | Spot | Lot | Furthest call | Call % OTM | Furthest put | Put % OTM | Strikes listed |
|---|---|---|---|---|---|---|---|---|---|
| 2024-01-11 | T-1 | 2024-01-10 | 21,618.70 | 50 | 23,450 | 8.47 | 19,400 | 10.26 | 82 |
| 2024-01-11 | T-2 | 2024-01-09 | 21,544.85 | 50 | 23,450 | 8.84 | 19,400 | 9.96 | 82 |
| 2024-01-11 | T-4 | 2024-01-05 | 21,710.80 | 50 | 23,300 | 7.32 | 19,400 | 10.64 | 79 |
| 2024-06-06 | T-1 | 2024-06-05 | 22,620.35 | 25 | 25,000 | 10.52 | 20,150 | 10.92 | 98 |
| 2024-06-06 | T-2 | 2024-06-04 | 21,884.50 | 25 | 25,000 | 14.24 | 20,200 | 7.70 | 97 |
| 2024-06-06 | T-4 | 2024-05-31 | 22,530.70 | 25 | 24,700 | 9.63 | 20,200 | 10.34 | 91 |
| 2024-08-08 | T-1 | 2024-08-07 | 24,297.50 | 25 | 26,750 | 10.09 | 22,250 | 8.43 | 91 |
| 2024-08-08 | T-2 | 2024-08-06 | 23,992.55 | 25 | 26,750 | 11.49 | 22,300 | 7.05 | 90 |
| 2024-08-08 | T-4 | 2024-08-02 | 24,717.70 | 25 | 26,750 | 8.22 | 22,550 | 8.77 | 85 |
| 2024-11-21 | T-1 | 2024-11-19 | 23,518.50 | 25 | 26,600 | 13.10 | 21,700 | 7.73 | 99 |
| 2024-11-21 | T-2 | 2024-11-18 | 23,453.80 | 25 | 26,600 | 13.41 | 21,800 | 7.05 | 97 |
| 2024-11-21 | T-4 | 2024-11-13 | 23,559.05 | 25 | 26,600 | 12.91 | 22,150 | 5.98 | 90 |
| 2025-03-06 | T-1 | 2025-03-05 | 22,337.30 | 75 | 25,500 | 14.16 | 20,350 | 8.90 | 104 |
| 2025-03-06 | T-2 | 2025-03-04 | 22,082.65 | 75 | 25,500 | 15.48 | 20,350 | 7.85 | 104 |
| 2025-03-06 | T-4 | 2025-02-28 | 22,124.70 | 75 | 25,500 | 15.26 | 20,800 | 5.99 | 95 |
| 2025-06-19 | T-1 | 2025-06-18 | 24,812.05 | 75 | 26,900 | 8.42 | 22,800 | 8.11 | 83 |
| 2025-06-19 | T-2 | 2025-06-17 | 24,853.40 | 75 | 26,900 | 8.23 | 22,800 | 8.26 | 83 |
| 2025-06-19 | T-4 | 2025-06-13 | 24,718.60 | 75 | 26,900 | 8.82 | 22,800 | 7.76 | 83 |
| 2025-09-30 | T-1 | 2025-09-29 | 24,634.90 | 75 | 30,000 | 21.78 | 17,000 | 30.99 | 106 |
| 2025-09-30 | T-2 | 2025-09-26 | 24,654.70 | 75 | 30,000 | 21.68 | 17,000 | 31.05 | 106 |
| 2025-09-30 | T-4 | 2025-09-24 | 25,056.90 | 75 | 30,000 | 19.73 | 17,000 | 32.15 | 106 |
| 2026-01-13 | T-1 | 2026-01-12 | 25,790.25 | 65 | 28,100 | 8.96 | 23,950 | 7.14 | 84 |
| 2026-01-13 | T-2 | 2026-01-09 | 25,683.30 | 65 | 28,100 | 9.41 | 24,000 | 6.55 | 83 |
| 2026-01-13 | T-4 | 2026-01-07 | 26,140.75 | 65 | 28,100 | 7.50 | 24,000 | 8.19 | 83 |
| 2026-04-28 | T-1 | 2026-04-27 | 24,092.70 | 65 | 27,700 | 14.97 | 20,100 | 16.57 | 153 |
| 2026-04-28 | T-2 | 2026-04-24 | 23,897.95 | 65 | 27,700 | 15.91 | 20,100 | 15.89 | 153 |
| 2026-04-28 | T-4 | 2026-04-22 | 24,378.10 | 65 | 27,700 | 13.63 | 20,100 | 17.55 | 153 |
| 2026-08-11 | T-1 | 2026-08-10 | 24,583.80 | 65 | 27,200 | 10.64 | 21,600 | 12.14 | 113 |
| 2026-08-11 | T-2 | 2026-08-07 | 24,570.65 | 65 | 27,200 | 10.70 | 21,600 | 12.09 | 113 |
| 2026-08-11 | T-4 | 2026-08-05 | 24,624.65 | 65 | 27,200 | 10.46 | 21,600 | 12.28 | 113 |

The 2025-09-30 expiry is a monthly contract, which is why its strike range is far wider.
The 2026-04-28 expiry is the last Tuesday of April 2026.

**All 410 entry days (not only the sample): furthest listed strike, % OTM**

| Entry | Call min | Call median | Put min | Put median |
|---|---|---|---|---|
| T-1 | 6.38 | 9.12 | 5.98 | 10.65 |
| T-2 | 6.12 | 9.31 | 6.02 | 10.57 |
| T-4 | 5.85 | 9.13 | 5.64 | 10.38 |

How often the target bands exist at all (out of 410 entry days):
- No call is listed at ≥10% OTM on **242** days. No call is listed at ≥6% OTM on **1** day.
- No put is listed at ≥14% OTM on **333** days. No put is listed at ≥8% OTM on **61** days.
- Call band 6–10%: at least one strike is listed on 409 / 410 days.
  Put band 8–14%: at least one strike is listed on **349 / 410** days.
- Strike spacing inside the 6–14% band is 50 points (one exception, a 1,000-point gap).

### 3c. Zero volume, zero OI and stale prices for strikes 6–14% OTM

**10 sample expiries × 3 entry days, both sides, 6–14% OTM: 1,189 rows** (705 calls, 484 puts)

| | Count | % of rows |
|---|---|---|
| Zero volume | 14 | 1.2% |
| Zero OI | 14 (the same 14 rows: every zero-volume row also has zero OI and zero open/high/low) | 1.2% |
| Stale (close = previous close) | 82 | 6.9% |
| Any of the three | 82 | 6.9% |

All 14 zero-volume rows are on the 2024-06-06 expiry (2 call rows at T-2, 3 call rows at
T-4, 9 put rows at T-4).

**All 410 entry days, study bands**

| Band | Entry | Rows | Zero volume | Zero OI | Stale | Any |
|---|---|---|---|---|---|---|
| Call 6–10% | T-1 | 1,872 | 16 | 16 | 123 | 123 |
| Call 6–10% | T-2 | 1,865 | 0 | 0 | 96 | 96 |
| Call 6–10% | T-4 | 1,817 | 3 | 3 | 80 | 80 |
| Put 8–14% | T-1 | 1,813 | 0 | 0 | 49 | 49 |
| Put 8–14% | T-2 | 1,768 | 0 | 0 | 54 | 54 |
| Put 8–14% | T-4 | 1,728 | 12 | 12 | 48 | 48 |

What the stale rows actually are: across both study bands there are 450 stale rows.
**419 of them traded on the day**. Their close simply printed the same as the previous
close, at a median of 0.75 points (90th percentile 1.40). Only 31 are truly untraded.
On traded rows, `SttlmPric` equals `ClsPric` 99.97% of the time.

**Premium level is the bigger issue.** Closing price, in points, of the study-band
strikes on entry days:

| Band | Entry | 10th pct | Median | 90th pct | % of rows below 1.00 pt |
|---|---|---|---|---|---|
| Call 6–10% | T-1 | 0.30 | 0.55 | 1.20 | 83.1% |
| Call 6–10% | T-2 | 0.40 | 0.80 | 1.75 | 59.1% |
| Call 6–10% | T-4 | 0.75 | 1.20 | 2.55 | 30.4% |
| Put 8–14% | T-1 | 0.25 | 0.50 | 1.20 | 85.3% |
| Put 8–14% | T-2 | 0.50 | 0.90 | 1.95 | 57.7% |
| Put 8–14% | T-4 | 1.05 | 1.75 | 4.21 | 7.5% |

### 3d. Price fields present (bhavcopy)

| Field | Present? | Column |
|---|---|---|
| Open | Yes | `OpnPric` (0 on the 452,985 untraded NIFTY option rows) |
| High | Yes | `HghPric` (same) |
| Low | Yes | `LwPric` (same) |
| Close | Yes | `ClsPric` (never 0; carried forward when untraded) |
| Settle | Yes | `SttlmPric` |
| Last | Yes | `LastPric` |
| Previous close | Yes | `PrvsClsgPric` |
| **Bid** | **No** | — |
| **Ask** | **No** | — |
| Volume | Yes, in contracts | `TtlTradgVol`; also `TtlNbOfTxsExctd` (number of trades) and `TtlTrfVal` (notional turnover in ₹, strike + premium basis) |
| OI | Yes, in units | `OpnIntrst`, `ChngInOpnIntrst` |
| Underlying (spot) | Yes | `UndrlygPric` = NIFTY index close |
| Lot size | Yes, per contract per day | `NewBrdLotQty` |

### 3e. Liquidity for 100 lots (6,500 units at lot 65)

Daily traded volume in **units** on entry days, all 410 entry days:

| Band | Entry | Median units per strike per day | Median ÷ 6,500 | % of strike-days ≥ 6,500 | % ≥ 65,000 (where 100 lots ≤ 10% of the day's volume) |
|---|---|---|---|---|---|
| Call 6–10% | T-1 | 2,531,038 | 389× | 99.0% | 98.2% |
| Call 6–10% | T-2 | 2,784,300 | 428× | 100.0% | 99.5% |
| Call 6–10% | T-4 | 2,114,255 | 325× | 99.4% | 95.6% |
| Put 8–14% | T-1 | 1,545,825 | 238× | 100.0% | 97.3% |
| Put 8–14% | T-2 | 1,530,918 | 236× | 100.0% | 98.0% |
| Put 8–14% | T-4 | 1,329,755 | 205× | 98.3% | 89.5% |

- 10-expiry sample only: calls 6–10% have a median of 2,391,610 units (493 rows).
  Puts 8–14% have a median of 708,435 units (239 rows).
- By year (both bands combined), the median ranges from 853,050 units (2024 puts) to
  3,295,088 units (2025 calls).
- The most liquid strike inside the band, per entry day, has a median of 11.3M–17.5M units.
  Only 1 entry day had a best strike below 6,500 units (a call at T-1).
- **Caveat:** this is daily turnover from an EOD file. It does **not** show bid/ask
  spread or depth at the moment of entry. Below 1 point, a single 0.05 tick is 5–20% of
  the premium.

## 4. India VIX daily history

**Not present.** No VIX file exists anywhere in the repo.
`src/filter_analysis.py:33` (`VIX_TICKER = "^INDIAVIX"`) downloads only the VIX *open*
from yfinance at run time, with an NSE API fallback. It never saves the data to disk.
Date range on disk: none.

## 5. NIFTY spot daily history

**Present, two sources:**
- `data/raw/nifty50_daily.csv` (yfinance `^NSEI`): full daily OHLC from **2016-01-04 to
  2026-08-11**, 2,613 rows, no duplicate dates, no nulls, longest gap 5 calendar days.
  It is 3 trading days short of the bhavcopy set (2026-08-12/13/14 are missing).
- Bhavcopy `UndrlygPric`: spot **close only**, 2024-01-01 → 2026-08-14 (647 days). It
  matches yfinance Close exactly on all 644 overlapping days.
- `nifty_expiry_day_chains.csv` also carries `NIFTY_Open` / `NIFTY_Close`, but only on
  the 136 expiry days.

Spot **open** on non-expiry entry days comes only from the yfinance file.

## 6. Reusable modules

### 6a. Lot size

- `src/lot_size.py`: `get_lot_size_for_contract(trade_date, expiry_date)` (line 116)
  and `get_lot_size(trade_date)` (line 143).
  - It reads `NewBrdLotQty` from that day's bhavcopy for the given contract, which is
    authoritative. It falls back to `config/lot_size_history.csv` only when no zip is on
    disk.
  - It returns `(lot_size, source)`. It already accepts any expiry, not only same-day,
    so it works for T-k entries.
  - Valid where bhavcopies exist: 2024-01-01 → 2026-08-14. Tests:
    `tests/test_lot_size.py`, 4 tests, all passing on 2026-11-16.
- `config/lot_size_history.csv` (fallback table):

| effective_from | effective_to | lot_size | circular |
|---|---|---|---|
| 2024-01-01 | 2024-04-25 | 50 | FAOP61415 |
| 2024-04-26 | 2024-11-19 | 25 | FAOP61415 |
| 2024-11-20 | 2025-10-27 | 75 | FAOP64625 |
| 2025-10-28 | 2026-01-05 | 65 | FAOP70616 |
| 2026-01-06 | (open) | 65 | FAOP70616 |

- Lot size observed in the data on each weekly expiry's own expiry day:

| Expiries | Lot | Count |
|---|---|---|
| 2024-01-04 → 2024-04-25 | 50 | 17 |
| 2024-05-02 → 2024-12-26 | 25 | 35 |
| 2025-01-02 → 2025-01-23 | 75 | 4 |
| 2025-01-30 | 25 | 1 (grandfathered) |
| 2025-02-06 → 2025-12-30 | 75 | 48 |
| 2026-01-06 → 2026-08-11 | 65 | 32 |

- **Discrepancy found (flagged, not fixed):** the 2024-05-02 contract had lot size
  **50** on its T-4 day (2024-04-25) and **25** from 2024-04-26. Its lot size changed
  *during the contract's life*. This conflicts with the `lot_size_history.csv` note
  that existing contracts kept their original lot size until expiry. The note holds for
  the 25→75 and 75→65 increases, but not for the 50→25 decrease.
  - It is the only one of the 410 entry-day/expiry pairs where the lot size differs
    between entry and expiry.
  - It matters for a multi-day hold: a 1-lot position opened that day becomes 2 lots of 25.
  - `get_lot_size_for_contract` reads each day's own file, so it reports this correctly.

### 6b. Expiry calendar

- There is **no standalone calendar module.** The logic lives in
  `src/download_bhavcopy.py:44-48`: `EXPIRY_REGIME_CHANGE = 2025-09-02`, Thursday before
  and Tuesday from that date, and `MAX_HOLIDAY_LOOKBACK = 5`.
  - It rolls back only when NSE returns HTTP 404. Per the handover, it is known to miss
    2025-10-20.
- The reliable calendar is **data-derived**: expiry = any date with same-day-expiry
  NIFTY rows. That gives 137 weekly expiries, 2024-01-04 → 2026-08-11, valid only within
  the bhavcopy range.
- Expiry weekday by period, from the data:

| From | To | Weekday | Expiries |
|---|---|---|---|
| 2024-01-04 | 2024-04-04 | Thursday | 14 |
| 2024-04-10 | 2024-04-10 | Wednesday | 1 |
| 2024-04-18 | 2024-08-08 | Thursday | 17 |
| 2024-08-14 | 2024-08-14 | Wednesday | 1 |
| 2024-08-22 | 2025-04-03 | Thursday | 33 |
| 2025-04-09 | 2025-04-09 | Wednesday | 1 |
| 2025-04-17 | 2025-04-24 | Thursday | 2 |
| 2025-04-30 | 2025-04-30 | Wednesday | 1 |
| 2025-05-08 | 2025-08-28 | Thursday | 17 |
| 2025-09-02 | 2025-10-14 | Tuesday | 7 |
| 2025-10-20 | 2025-10-20 | Monday | 1 |
| 2025-10-28 | 2026-02-24 | Tuesday | 18 |
| 2026-03-02 | 2026-03-02 | Monday | 1 |
| 2026-03-10 | 2026-03-24 | Tuesday | 3 |
| 2026-03-30 | 2026-03-30 | Monday | 1 |
| 2026-04-07 | 2026-04-07 | Tuesday | 1 |
| 2026-04-13 | 2026-04-13 | Monday | 1 |
| 2026-04-21 | 2026-08-11 | Tuesday | 17 |

  The Wednesday and Monday entries are holiday shifts. Gaps between consecutive expiries:
  7 days ×119, 6 days ×8, 8 days ×8, 5 days ×1 (the regime change).

### 6c. Cost model

- Location: `src/backtest_strangle.py:72-121` (`run_backtest`), parameters in
  `config/strategy_with_costs.json`. Imported by `event_day_study.py`,
  `everyday_backtest.py` and others.
- Every charge it uses:

| Charge | Rate in model | How applied | Source / date recorded in repo |
|---|---|---|---|
| Brokerage | ₹20 per leg | **Flat per order**: always `20 × 4` = ₹80 per trade (2 entry legs + 2 exit legs), regardless of lots or turnover | None cited. Described as "standard costs" in `journal/2026-08-13-baseline-analysis.md` and RESULTS.md |
| STT | 0.1% (`stt_pct: 0.001`) | `0.001 × (call + put entry premium after slippage) × lot_size`, sell side only. `lot_size` is the config's flat 65, i.e. **one lot** | None cited ("the government's 0.1%…" in RESULTS.md); no effective date |
| Bid-ask slippage | 0.5 points per leg (`bid_ask_points_per_leg`) | Applied against the trade on all 4 legs (sell lower, buy back higher), so −2.0 points per strangle | Assumption; no source |
| Flat per-trade cost | ₹0 (`cost_per_trade_rupees`) | Legacy field | — |
| Exchange transaction fee | **Not modelled** | — | — |
| SEBI turnover fee | **Not modelled** | — | — |
| Stamp duty | **Not modelled** | — | — |
| GST | **Not modelled** | — | — |
| STT on exercise / ITM settlement at expiry | **Not modelled** | — | — |

## 7. Gaps

- **Missing weeks:** none. All 137 Mon–Fri weeks between 2024-01-01 and 2026-08-14 have
  at least one file, and every week has exactly one weekly expiry.
- **Missing trading days:** none found. The 38 weekdays without a file are market
  holidays. `download_all_days_manifest.csv` has 0 failures. One Saturday session is
  present (2025-02-01).
- **Missing expiries:** none in 2024-01-04 → 2026-08-11 (137 / 137). The first file
  (2024-01-01) has no expiry before 2024-01-04. The next expiry after the data ends
  (2026-08-18) is not on disk. `nifty_expiry_day_chains.csv` is missing 2025-10-20,
  136 vs 137.
- **Missing history:** everything before 2024-01-01 (NSE archive limit). This includes
  Mar 2020 and Feb–Mar 2022.
- **Duplicates:** 0 fully duplicated rows in 25,046,464 raw rows. 0 duplicate
  (instrument, symbol, expiry, strike, type) keys within any file. 0 duplicate
  (date, expiry, strike, type) NIFTY option rows. 0 duplicate dates in
  `nifty50_daily.csv` and `nifty_expiry_day_chains.csv`. `XpryDt` equals
  `FininstrmActlXpryDt` on every row. Every file holds a single `TradDt`.

---

## VERDICT

**The current data CAN support:**
- T-1, T-2 and T-4 entries for all 137 weekly expiries (136 for T-4), 2024-01-04 → 2026-08-11.
  That is 410 entry/expiry pairs, from real NSE EOD prices.
- Pricing the entry at that day's open or close (`OpnPric` / `ClsPric`, with `SttlmPric`
  as a cross-check), and settling at expiry against spot close (`UndrlygPric` on expiry day).
- Day-by-day mark-to-market between entry and expiry, at EOD close only, for every
  calendar day held.
- Call legs at ~6–9% OTM on almost every day (409 / 410 entry days have a listed strike
  in 6–10%).
- Put legs at ~8–10.5% OTM on most days (349 / 410 have a listed strike in 8–14%).
- 1, 10 and 100 lots on *daily-volume* grounds: the median band strike trades 205×–428×
  the 6,500-unit 100-lot size.
- Correct per-contract lot size on every date via `src/lot_size.py`, plus a data-derived
  expiry calendar.

**The current data CANNOT support, and what would be needed:**
- **Any period before 2024** (Mar 2020 COVID crash, Feb–Mar 2022 Ukraine sell-off).
  - Needed: pre-2024 NIFTY option EOD data from NSE's old-format F&O bhavcopy archive
    (`fo<DDMMMYYYY>bhav.csv.zip`), or a licensed vendor.
  - Without it, the sample has no real tail test. Across the 410 pairs, the largest
    spot move from entry-day close to expiry-day close is −2.14% / +2.55% (T-1),
    −4.18% / +4.28% (T-2) and −3.91% / +6.48% (T-4; 2025-04-09 → 2025-04-17).
  - No pair moves 8% or more in either direction, so no 8–14% put is ever tested
    against a crash in-sample.
- **The outer part of the target bands.**
  - Calls ≥10% OTM are not listed on 242 / 410 entry days. Puts ≥14% are not listed on
    333 / 410. Puts ≥8% are not listed on 61 / 410.
  - This is how NSE lists strikes, so more data cannot fix it. The study must
    pre-register a rule for days with no strike in band (e.g. use the furthest listed
    strike, or skip the day).
- **Realistic fills on sub-1-point premiums.**
  - 57–85% of T-1/T-2 band strikes close below 1.00 point, and there are no bid/ask fields.
  - Needed: historical bid/ask or order-book snapshots (NSE tick/snapshot data or a
    vendor) to measure spread and depth for a 6,500-unit order.
- **Intraday path or intraday stop-losses while holding.**
  - Needed: 1-minute (or finer) option and spot data. None is in the repo.
- **VIX-conditioned rules or VIX reporting.**
  - Needed: India VIX daily history saved to disk (NSE historical VIX, or yfinance
    `^INDIAVIX` with a `_SOURCE.txt` note). Nothing is stored now.
- **Spot open on 2026-08-12 → 2026-08-14.**
  - Needed: refresh `nifty50_daily.csv`. This is minor.

**Can the existing cost model be reused as-is for multi-day, hold-to-expiry trades? No.**
1. It always charges 4 legs, including a buy-back exit with 2 brokerage orders and
   2 × 0.5 points of exit slippage.
   - A hold-to-expiry trade that expires worthless has no exit order.
   - One that finishes in the money is cash-settled at expiry, and the model has no
     charge for that.
2. Its slippage is a fixed 0.5 points per leg, on premiums whose median is 0.50–1.75 points.
   - Entry slippage alone would take roughly 30–100% of a typical T-1/T-2 credit.
   - The slippage figure has no source and cannot be checked against the data, which
     has no bid/ask.
3. STT is computed on **one lot** at a flat 65. Brokerage is a flat ₹80 regardless of size.
   - At 10 and 100 lots, STT must scale with lots and the real `NewBrdLotQty`.
   - Brokerage must count the actual number of orders. A 100-lot (6,500-unit) order may
     need to be split under NSE's quantity-freeze limit. That limit is not in this repo
     and must be verified from a primary NSE source.
4. It omits the exchange transaction fee, SEBI turnover fee, stamp duty (buy side) and
   GST. It also omits STT on options that settle in the money at expiry.
   - None of the existing rates has a recorded source or effective date. In particular,
     the 0.1% STT is applied to all of 2024–2026 without a date check.
   - Every rate needs a primary-source citation and an effective-date range before the
     new study uses it.
5. **What is reusable:** the function structure, `lot_size.py`, and the points-first
   reporting convention.
   - The cost function itself needs a new, pre-registered multi-day/expiry-settlement
     version.
   - `src/backtest_strangle.py` and `config/strategy_with_costs.json` are protected, so
     the new version should be a separate file, not an edit to them.
