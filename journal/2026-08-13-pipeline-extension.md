# Research Journal — 2026-08-13

Continuation of [2026-08-12-findings.md](2026-08-12-findings.md). This
entry covers extending the pipeline's date range and pre-registering the
backtest's baseline parameters before running it.

## Data-availability finding — NSE's UDiFF archive begins 2024-01-01

The general pipeline was extended to pull NIFTY expiry-day option chains
back to 2023-01-01, as originally intended. That extension failed for
all of 2023: every single date probed across January-June 2023 (26
expiry-candidate Thursdays plus normal-day comparisons, all in
`src/download_bhavcopy.py`'s first extended chunk) returned HTTP 404 from
NSE's archive server, even after the holiday-rollback retry logic
exhausted its lookback window on each one.

Before spending further requests confirming this across the rest of
2023, it was checked directly: dates spanning August through December
2023 (specific Thursday-expiry trading days, not holidays or weekends)
were probed one at a time and **all returned 404**, while every date
probed from **2024-01-01 onward returned a real file** (verified by
content-type and byte size, not just status code). The exact boundary
was narrowed to between 2023-12-29 (404) and 2024-01-01 (200).

**This is a data-availability constraint of NSE's UDiFF archive itself,
not a design choice made in this pipeline.** The original assumption --
that the gap was tied to the UDiFF-format transition on 8 July 2024 --
was wrong; the archive actually extends back to the start of calendar
2024, roughly six months earlier than that transition date, but not into
2023 at all. No alternate source was substituted for the missing period.

**Practical effect:** the processed dataset (`data/processed/nifty_expiry_day_chains.csv`)
now covers **136 distinct expiry dates, from 2024-01-04 to 2026-08-11**.
2023 is absent, not zero-filled or interpolated. Any future finding
computed from this dataset should be understood as covering ~2.6 years
(2024-2026), not the originally intended ~3.6 years back to 2023.

A residual data-quality note carried over from the prior extension: 4
expiry-candidate dates still show zero same-day-expiry rows
(2025-08-12, 2025-08-19, 2025-08-26, 2025-10-21), consistent with the
NIFTY weekly-expiry weekday transition from Thursday to Tuesday that the
downloader now models as occurring on 2025-09-02 -- these 4 dates sit at
or near that transition and are excluded from the 136-date count above,
same as noted in the prior journal entry.

## Pre-registered baseline parameters for the strangle backtest

Before running `src/backtest_strangle.py` for the first time or looking
at any of its output, the following baseline parameters are fixed and
recorded here:

- **Strike distance: 0.5%** -- short call = nearest available strike at
  or above `index_open * 1.005`; short put = nearest available strike at
  or below `index_open * 0.995`.
- **Minimum volume: 1,000 contracts** -- both legs must have
  `TtlTradgVol > 1000` on the expiry day, else the date is skipped and
  logged with a reason.

These are stored in `config/strategy.json`, not hard-coded, so they can
be changed later -- but the specific values above are the ones being
committed to *before* the first backtest run, precisely so that if the
results look disappointing there is no temptation to quietly retune
strike distance or the volume filter until the numbers look better.
Any future change to these parameters, after having seen this run's
results, should be treated as a new, separate experiment and labeled as
such -- not as a correction to this baseline.
