# Weekly strangle engine (Step 6)

This package holds the code for the weekly NIFTY short-strangle study. Its rules come from
`docs/weekly_strangle/04_preregistration.md` (including Amendment 1),
`config/weekly_strangle/prereg_params_amendment_1.json` and
`config/weekly_strangle/step6_decisions.json`.
**Step 6 does not run the backtest.** Only the correctness gates were run (`scripts/weekly_strangle/run_gates.py`).

## What each module does

- **`data.py`**: loads the option prices from two sources:
  - the 2019–2023 file (old NSE bhavcopy format);
  - the 2024+ daily UDiFF zips.

  Both are put into one table with the same column names. Rows that are never needed are
  dropped, and the rest are saved to `data/processed/ws_options_cache.parquet`, with a spot
  file next to it; both are gitignored. The module also loads India VIX.

  It also holds the **look-ahead guard**, `rows_as_of()`, which stops with an error if any row
  dated after the entry day reaches the selection code. Finally, it gives the lot size of each
  contract:
  - from the bhavcopy from 2024;
  - from `lot_size_pre2024.csv` before that (75 up to the 2021-07-22 expiry, then 50).
- **`calendar.py`**: defines a trading day as a day with an option file, minus Muhurat sessions.
  2021-03-30 counts as a trading day, but it has no file, so trades touching it are skipped.
  The module also:
  - builds the weekly expiry calendar from the data;
  - moves a holiday expiry to the previous trading day;
  - finds the entry day T-k;
  - labels each expiry as in-sample (2019-02-14 to 2023-12-28) or out-of-sample (2024-01-04 to 2026-11-09).
- **`strikes.py`**: picks the strikes.
  - **V1:** the strike closest to 7% OTM for calls and 10% for puts, never more than 2 points
    closer to spot; ties go further out.
  - **V2:** the strike whose |delta| is closest to 0.04. Delta comes from Black-Scholes with
    r = 0, using IV solved from each strike's entry close.
  - **V4:** the wings, chosen nearest to W points beyond each short strike.

  Only strikes that traded on the entry day with a close of at least 0.05 can be chosen.
- **`costs.py`**: computes every charge for each order, using the rate in force on the trade date:
  - brokerage A, B, C or D;
  - STT on sale;
  - NSE transaction charge and IPFT;
  - SEBI fee;
  - stamp duty on buys;
  - GST on brokerage, transaction charge and SEBI fee.

  It also covers:
  - **Slippage:** a sell fills `s` ticks below the close, a buy `s` ticks above.
  - **Freeze limit:** orders are split at the freeze limit, which matters only for brokerage D.
  - **Expiry:** settlement is not an order. A worthless leg costs nothing.
  - **In-the-money settlement (decision D9):** a leg that settles in the money pays the SEBI fee
    on its notional (settlement spot × units) plus GST on that fee. A long wing also pays STT on
    exercise. There is no exchange transaction charge at settlement.
- **`settlement.py`**: computes each leg's intrinsic value at the expiry-day spot close. A short
  leg pays it and a long wing receives it.
- **`variants.py`**: holds the remaining variant rules:
  - **V3:** stop-loss, checked end-of-day.
  - **V5:** VIX filter.
  - **V6:** event filter. It loads the three event calendars and moves US-dated FOMC rows to the
    next Indian trading day (Amendment 1A). It marks `event_calendar.csv` rows VERIFIED or
    SECONDARY (1B), and uses only FOMC, RBI MPC, Union Budget and Lok Sabha result events (1D).
- **`engine.py`**: builds one trade (`build_trade`), or every trade of one combination of
  variant, entry day, brokerage and slippage (`run_combo`). It returns a per-trade table with
  net rupees and net points per unit at 1, 10 and 100 lots per leg. Every skipped week and
  skipped leg is logged with its reason.

## Commands

```bash
.venv/bin/python -m pytest tests/weekly_strangle -q
```

```bash
.venv/bin/python scripts/weekly_strangle/run_gates.py
```

The first run builds the cache, which takes about 40 seconds.
