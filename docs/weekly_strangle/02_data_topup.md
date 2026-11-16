# Weekly strangle study — Step 3: data top-up

Download and save only. No analysis or backtest code was written.

- Date of run: 2026-11-16.
- No existing source file or existing data file was modified.
  - `src/download_bhavcopy.py`, `nifty50_daily.csv`, the old manifests and the old zips are untouched.
  - The only edit to an existing file is four new `.gitignore` lines.
- Scripts (new):
  - `scripts/weekly_strangle/topup_data.py` (`vix`, `spot`, `bhav`)
  - `scripts/weekly_strangle/legacy_bhavcopy.py` (`download`, `build`)
  - `scripts/weekly_strangle/report_topup.py` (`vix`, `bhav`, `legacy`, `stress`). Read-only; every number
    below comes from it.
- Politeness rules applied to every request:
  - Browser-like headers: the existing `HEADERS` / `get_session()` from `src/download_bhavcopy.py`, reused
    unchanged.
  - At least 1.1 s between requests.
  - A failed request is retried at most twice. HTTP 404 is treated as a definite "no file" answer and is
    not retried, except for the one trading-day gap noted under Part C.
  - Every attempt is appended to a manifest CSV.
- Manifests (new, tracked):
  - `data/raw/download_vix_manifest.csv` (58 attempts)
  - `data/raw/download_topup_2026_manifest.csv` (68 attempts)
  - `data/raw/download_legacy_2019_2023_manifest.csv` (1,306 attempts)
- Every saved dataset has a `*_SOURCE.txt` next to it (URL, download date, rows, date range).

## Git hygiene

- `.gitignore` gained four lines: `data/raw/india_vix_daily.csv`, `data/raw/india_vix_daily_yfinance.csv`,
  `data/raw/nifty50_daily_v2.csv` and `data/raw/legacy/`.
- Already covered by existing rules: `data/raw/*.zip` (the new UDiFF zips) and `data/processed/*.csv`
  (the 2019–2023 options file).
- `git check-ignore` confirmed every data file is ignored before committing.
- The new manifests and `_SOURCE.txt` notes stay tracked, as provenance, following the repo's existing
  convention.

## PART A — India VIX daily history

### Source

- **NSE's historical India VIX API worked** and is the saved source:
  - URL pattern: `https://www.nseindia.com/api/historicalOR/vixhistory?from=DD-MM-YYYY&to=DD-MM-YYYY`
  - Saved to `data/raw/india_vix_daily.csv`, columns Date, Open, High, Low, Close.
- **Caveat found and fixed**: the API returns at most the first 70 rows of any window.
  - The first run used yearly windows and silently got only 1 Jan to mid-April of each year (770 rows).
  - The re-run used 90-day windows (45 requests), and no window hit the cap.
  - Both runs are in the manifest.
- **yfinance `^INDIAVIX`** was also saved, as a comparison copy: `data/raw/india_vix_daily_yfinance.csv`.

### Coverage

- **NSE: 2,692 rows, 2016-01-01 → 2026-11-13.**
  - Duplicate dates: **0**. Duplicate rows: 0. Empty cells: 0.
- **yfinance: 2,665 rows, 2016-01-01 → 2026-11-16.** The 2026-11-16 row is today's provisional value.
- **Missing trading days against `nifty50_daily.csv`** (2016-01-04 → 2026-08-11): **0** NIFTY days are
  missing from VIX. The same holds against `nifty50_daily_v2.csv` (to 2026-11-13).
- VIX has 15 dates that the yfinance NIFTY file lacks:
  - **Weekend special sessions**: 2016-10-30 (Sun), 2019-10-27 (Sun), 2020-02-01 (Sat), 2020-11-14 (Sat),
    2023-11-12 (Sun), 2024-01-20 (Sat), 2024-05-18 (Sat), 2026-02-01 (Sun), 2026-11-08 (Sun). These are
    Muhurat or Budget-day sessions or Saturday sessions.
  - **Weekdays yfinance's NIFTY series skips**: 2016-01-01, 2016-08-12, 2018-01-01, 2019-01-01,
    2019-02-13, 2019-03-29.

### NSE versus yfinance

- 2,664 dates are in both sources. 28 dates are NSE-only. The only yfinance-only date is 2026-11-16.
- Across all common dates, the close differs by a median of 0.0025 points. **99.9% agree to within 0.01**.
- Only 3 dates differ by 0.01 or more:

| Date | NSE close | yfinance close |
|---|---|---|
| 2018-11-07 | 17.8775 | 17.72 |
| 2021-02-12 | 23.0450 | 22.04 |
| 2021-03-30 | 20.6500 | 20.49 |

- 20 random common dates (seed 7):

| Date | NSE close | yfinance close | Diff | NSE open | yfinance open | Diff |
|---|---|---|---|---|---|---|
| 2017-01-19 | 15.0200 | 15.0200 | 0.0000 | 15.1825 | 15.1800 | −0.0025 |
| 2017-07-11 | 10.8900 | 10.8900 | 0.0000 | 10.9125 | 10.9100 | −0.0025 |
| 2017-08-16 | 14.2375 | 14.2400 | 0.0025 | 14.3825 | 14.3800 | −0.0025 |
| 2017-09-06 | 13.1200 | 13.1200 | 0.0000 | 12.8875 | 12.8900 | 0.0025 |
| 2017-12-08 | 13.6725 | 13.6700 | −0.0025 | 14.2725 | 14.2700 | −0.0025 |
| 2018-03-05 | 15.3950 | 15.4000 | 0.0050 | 14.0725 | 14.0700 | −0.0025 |
| 2018-07-31 | 12.4800 | 12.4800 | 0.0000 | 12.5850 | 12.5900 | 0.0050 |
| 2018-09-11 | 15.3300 | 15.3300 | 0.0000 | 15.2025 | 15.2000 | −0.0025 |
| 2018-10-17 | 17.9800 | 17.9800 | 0.0000 | 17.3725 | 17.3700 | −0.0025 |
| 2020-11-04 | 23.2000 | 23.2000 | 0.0000 | 24.2400 | 24.2400 | 0.0000 |
| 2021-07-07 | 12.2125 | 12.2100 | −0.0025 | 12.2750 | 12.2800 | 0.0050 |
| 2021-07-08 | 13.5600 | 13.5600 | 0.0000 | 12.2125 | 12.2100 | −0.0025 |
| 2021-09-01 | 14.1850 | 14.1900 | 0.0050 | 14.5200 | 14.5200 | 0.0000 |
| 2023-03-27 | 15.4450 | 15.4500 | 0.0050 | 15.2400 | 15.2400 | 0.0000 |
| 2023-08-17 | 12.2400 | 12.2400 | 0.0000 | 12.1250 | 12.1300 | 0.0050 |
| 2024-06-27 | 14.1525 | 14.1500 | −0.0025 | 14.0450 | 14.0500 | 0.0050 |
| 2024-08-20 | 13.8200 | 13.8200 | 0.0000 | 14.3150 | 14.3200 | 0.0050 |
| 2025-01-02 | 13.7375 | 13.7400 | 0.0025 | 14.5075 | 14.5100 | 0.0025 |
| 2026-04-24 | 19.7100 | 19.7100 | 0.0000 | 18.5900 | 18.5900 | 0.0000 |
| 2026-07-31 | 11.7600 | 11.7600 | 0.0000 | 12.1550 | 12.1600 | 0.0050 |

- The differences are rounding: yfinance rounds to 2 decimals, while NSE reports 4.

## PART B — data brought up to date

### NIFTY spot

- New file `data/raw/nifty50_daily_v2.csv` (yfinance `^NSEI`): **2,678 rows, 2016-01-04 → 2026-11-16**.
- The old `nifty50_daily.csv` (to 2026-08-11) is unchanged.
- **Caveat**: the 2026-11-16 row has Volume 0. It is a provisional intraday value, not a final close.

### UDiFF F&O bhavcopies

- Covered 2026-08-17 → latest. Files are in `data/raw/` with the existing filename pattern. The URL and
  path come from `bhavcopy_url()` and `zip_path_for()` in `src/download_bhavcopy.py`, used unchanged.
- **Not used**: that module's `download_dates()`. It writes to the existing
  `data/raw/download_manifest.csv`, which this step was not allowed to modify, and it does not log
  retries. The new loop reuses the same session, header, URL and path functions instead.
- **New trading days added: 62 files.**
  - 61 weekdays from 2026-08-17 to 2026-11-13.
  - Plus Sunday **2026-11-08 Muhurat session** (HTTP 200). It was found through NSE's holiday page and
    requested separately.
  - Total 71,203,437 bytes. UDiFF files on disk now cover 2024-01-01 → 2026-11-13 (709 files including
    the Muhurat day).
- **The 5 weekday 404s**, checked against NSE's 2026 equities holiday list
  (https://www.nseindia.com/resources/exchange-communication-holidays). None of the four holiday dates
  has a NIFTY spot or VIX row either.

| Date | Day | NSE trading holiday? |
|---|---|---|
| 2026-09-14 | Mon | **Yes**, Ganesh Chaturthi |
| 2026-10-02 | Fri | **Yes**, Mahatma Gandhi Jayanti |
| 2026-10-20 | Tue | **Yes**, Dussehra |
| 2026-11-10 | Tue | **Yes**, Diwali-Balipratipada |
| 2026-11-16 | Mon | **No**. A trading day whose bhavcopy was not yet published when requested |

- **New weekly expiries found (data-derived: 13)**: 2026-08-18, 08-25, 09-01, 09-08, 09-15, 09-22, 09-29,
  10-06, 10-13, **10-19 (Mon)**, 10-27, 11-03, **11-09 (Mon)**.
  - The two Monday expiries are holiday shifts. Tuesdays 10-20 and 11-10 were holidays.
- **Statement coverage**: all **30** NIFTY expiries in the real statement up to 2026-11-10 now have a
  bhavcopy on disk **and** same-day-expiry NIFTY rows. Only the symbol column of the statement was read;
  expiry dates only are listed:
  - 2026-03-30 (Mon), 04-07, 04-28, 05-05, 05-12, 05-26, 06-02, 06-09, 06-16, 06-23, 06-30, 07-07, 07-14,
    07-21, 07-28, 08-04, 08-11, 08-18, 08-25, 09-01, 09-08, 09-15, 09-22, 09-29, 10-06, 10-13,
    10-19 (Mon), 10-27, 11-03, 11-09 (Mon).
  - 2026-03-30 is a Monday because 2026-03-31 was a holiday (Shri Mahavir Jayanti, per the same NSE list).

## PART C — pre-2024 NIFTY option data (2019–2023)

### Gate and download

- **Gate**: `config/weekly_strangle/market_rules.csv` records the Step 2 test of the old-format archive
  (`fo<DDMONYYYY>bhav.csv.zip`) as **HTTP 200** for 2020-03-13 and 2022-02-24. Part C was therefore run.
- **Download**: every weekday 2019-01-01 → 2023-12-31, into `data/raw/legacy/` (gitignored).

| | Count |
|---|---|
| Weekdays requested | 1,304 |
| Downloaded (HTTP 200) | **1,234** (742,206,394 bytes) |
| HTTP 404 | 70 |
| Request failures | 0 |
| Retries needed | 0 |

- One run covered all dates and finished cleanly, so no resume was needed.
- Of the 70 404s, 69 fall on days with no NIFTY trading in the spot calendar (holidays).
- **The only gap: 2021-03-30.** NIFTY did trade that day (both spot and VIX have it), but the archive
  returned 404, and still did on 2 logged retries. It is a genuine archive gap.
- Three legacy days are not in yfinance's NIFTY calendar (2019-01-01, 2019-02-13, 2019-03-29). They are
  kept, but have no spot price.

### Dataset `data/processed/nifty_options_2019_2023.csv` (gitignored)

- Filter: `INSTRUMENT == OPTIDX` and `SYMBOL == NIFTY`.
- **2,913,404 rows, 1,234 trading days, 2019-01-01 → 2023-12-29. 0 duplicate (date, expiry, strike, type)
  keys.**
- Columns: trade_date, expiry, strike, type, open, high, low, close, settle, contracts, oi, spot_close.
  - `spot_close` is joined from `nifty50_daily_v2.csv`. It is empty on the 3 dates above (8,602 rows).
- **No lot size column.** The old format has none, and none was invented.
- Weekly-expiry anchors derived from the data: 256 in 2019–2023. Before 2019-02-14 there are only monthly
  expiries (2019-01-31). Weekly NIFTY expiries appear from 2019-02-14.

### Coverage of the requested periods

- **Mar 2020**: 21 of 21 NIFTY trading days have a file.
- **Feb–Mar 2022**: 41 of 41 trading days have a file.
- **Every week with a >4% move between 2019 and 2023** (23 weeks, listed in the table below) has a file
  for every trading day.

### TODO: pre-2024 NIFTY lot-size circulars (needed before any rupee conversion)

The circulars still to find:
1. The NSE circular that set the **NIFTY lot of 75**, in force on 2019-01-01.
2. The NSE circular that revised **NIFTY 75 → 50** around mid-2021, including its rule for existing
   contracts (grandfathering).
3. Confirmation that NIFTY stayed at 50 from then until 2024-04-25. That is consistent with
   NSE/FAOP/61415, which gives the "present market lot" as 50 in April 2024.

Cross-check from the data only, **not written to the dataset**:
- Method: implied lot = VAL_INLAKH × 10⁵ ÷ (CONTRACTS × (STRIKE + SETTLE)), taking the daily median over
  traded NIFTY options.
- Result: **75 from 2019-01-01 to 2021-06-30** and **50 from 2021-07-01 to 2023-12-29**. Single-day
  readings of 74 (2020-03-12, 2021-06-17, 2021-06-25) and 50 (2021-06-24) appear around the switch.
- This is an inference and needs the circulars above to confirm it.

## STRESS WEEKS IN SPOT DATA 2016–2026

Method:
- Every week where NIFTY spot (`nifty50_daily_v2.csv`, close) moved more than 4% between one weekly-expiry
  close and the next.
- 562 anchors in total:
  - 2016–2018 (156): nominal Thursday, moved back to the previous trading day on holidays. NIFTY had no
    weekly options then.
  - 2019–2023 (256): data-derived from the legacy files.
  - 2024–2026 (150): data-derived from the UDiFF files.
- **30 weeks qualify.** "Option data" means a bhavcopy is on disk for every trading day of that week.

| From expiry | To expiry | NIFTY move | Anchor | Option data on disk |
|---|---|---|---|---|
| 2016-02-04 | 2016-02-11 | −5.78% | nominal Thu | no (pre-2019) |
| 2016-02-25 | 2016-03-03 | +7.24% | nominal Thu | no (pre-2019) |
| 2016-04-07 | 2016-04-13 | +4.03% | nominal Thu | no (pre-2019) |
| 2016-11-10 | 2016-11-17 | −5.23% | nominal Thu | no (pre-2019) |
| 2019-09-19 | 2019-09-26 | +8.09% | legacy | yes |
| 2020-03-05 | 2020-03-12 | −14.90% | legacy | yes |
| 2020-03-12 | 2020-03-19 | −13.83% | legacy | yes |
| 2020-03-19 | 2020-03-26 | +4.57% | legacy | yes |
| 2020-03-26 | 2020-04-01 | −4.49% | legacy | yes |
| 2020-04-01 | 2020-04-09 | +10.40% | legacy | yes |
| 2020-04-23 | 2020-04-30 | +5.86% | legacy | yes |
| 2020-04-30 | 2020-05-07 | −6.70% | legacy | yes |
| 2020-05-21 | 2020-05-28 | +4.22% | legacy | yes |
| 2020-05-28 | 2020-06-04 | +5.68% | legacy | yes |
| 2020-07-16 | 2020-07-23 | +4.43% | legacy | yes |
| 2020-09-17 | 2020-09-24 | −6.17% | legacy | yes |
| 2020-09-24 | 2020-10-01 | +5.66% | legacy | yes |
| 2020-11-05 | 2020-11-12 | +4.71% | legacy | yes |
| 2021-01-21 | 2021-01-28 | −5.30% | legacy | yes |
| 2021-01-28 | 2021-02-04 | +7.80% | legacy | yes |
| 2021-03-10 | 2021-03-18 | −4.07% | legacy | yes |
| 2022-02-17 | 2022-02-24 | −6.11% | legacy | yes |
| 2022-03-10 | 2022-03-17 | +4.17% | legacy | yes |
| 2022-05-05 | 2022-05-12 | −5.24% | legacy | yes |
| 2022-06-09 | 2022-06-16 | −6.78% | legacy | yes |
| 2022-07-14 | 2022-07-21 | +4.18% | legacy | yes |
| 2022-09-22 | 2022-09-29 | −4.60% | legacy | yes |
| 2025-04-09 | 2025-04-17 | +6.48% | UDiFF | yes |
| 2026-10-27 | 2026-11-03 | +4.66% | UDiFF | yes |
| 2026-11-03 | 2026-11-09 | +5.18% | UDiFF | yes |

Reading the table:
- 26 of the 30 stress weeks now have option data on disk. Only the four 2016 weeks have none.
- 23 of the 26 are in 2019–2023. Before this step, the dataset had **none** of them.
- The 2024–2026 sample has only 3 such weeks. The 2024-06-04 election crash does not appear, because NIFTY
  recovered before the 2024-06-06 expiry.
- The two 2026 up-weeks are after the earlier study's data ended.
- Two anchor gaps of more than 9 days (2018-12-27 → 2019-01-31 → 2019-02-14) come from the switch from
  nominal Thursdays to the monthly-only expiries of early 2019. Neither crosses 4%.

## Open items

- The pre-2024 NIFTY lot-size circulars (the Part C TODO).
- Re-download 2026-11-16 once NSE publishes it, and replace the provisional 2026-11-16 spot row.
- The 2021-03-30 legacy archive gap. There is no option data for that trading day; another source would
  be needed.
- yfinance's NIFTY series misses 6 weekday sessions (listed in Part A) that NSE VIX and the bhavcopies have.
  Spot for those days would need NSE's index history.
