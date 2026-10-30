# Research Journal — 2026-08-16 (missing expiry day, found by the every-day extension's correctness gate)

**No P&L for 2025-10-20 has been computed or seen while writing this
entry.** The inclusion decision below is recorded before that number
exists, on purpose.

## How this was found

Phase B of the every-day extension (`src/everyday_backtest.py`, Step 1
correctness gate) required the DTE=0 subset of the `nearest_weekly`
variant to reproduce the existing 136-trade baseline exactly, trade
for trade, before any further analysis was permitted to run. It did
not: **all 136 overlapping trades matched exactly** (same strikes,
same entry/exit prices, same P&L in points, to the last decimal), but
the every-day extraction also found a 137th same-day-expiry date --
**2025-10-20** -- that the baseline does not contain at all. Per
instruction, the script halted immediately: no Step 2, no Step 3, no
output files, no P&L for the missing date computed or reported.

**This is a completeness gap, not a calculation error.** Every trade
both datasets have in common agrees perfectly. The baseline's
strike-selection and P&L logic is not in question here; what's missing
is one entire input row it never had a chance to see.

A full scan of all 647 downloaded bhavcopy files (2024-01-01 onward,
committed in `060e104`) confirms this is the *only* such gap: 137
dates have same-day-expiry NIFTY rows in total, the 136-trade baseline
is a clean subset of those 137, and no baseline date is absent from
the scan.

## Root cause

The original expiry-day downloader (`src/download_bhavcopy.py`) only
ever requests the *expected* weekday for a given date's regime
(Thursday before 2025-09-02, Tuesday from that date on). Its
holiday-rollback logic exists specifically to handle a market that's
fully closed that day -- it triggers only on an HTTP 404 from NSE's
archive, and walks backward to the previous trading day when it fires.

2025-10-21 (the expected Tuesday that week) never triggered it,
because the market was **not** fully closed that day.

**VERIFIED FROM DATA:** the 2025-10-21 bhavcopy file exists and
downloads successfully (HTTP 200, not 404). Checked directly against
the raw file: it contains **zero** rows where TckrSymb=NIFTY and
XpryDt=2025-10-21 -- no genuine same-day-expiry NIFTY contract that
day. The 2025-10-20 bhavcopy, by contrast, contains **186** such rows.
The genuine weekly expiry that week was Monday 2025-10-20, not the
expected Tuesday. Since the downloader only ever targets the
*expected* weekday and 2025-10-20 is a Monday, it was never requested
by the original campaign at all. Monday only entered this project's
data for the first time via Part 2's every-single-trading-day download
(`060e104`).

**NOT VERIFIED:** the explanation for *why* 2025-10-21 has a real,
downloadable bhavcopy with zero genuine expiries -- that 21 October
2025 was an official NSE trading holiday for Diwali Laxmi Pujan, on
which NSE ran a ceremonial one-hour "Muhurat Trading" session -- is a
plausible hypothesis, consistent with well-known NSE/BSE conventions
around Diwali, but it has **not** been checked against NSE's official
holiday calendar or any cited primary source. It came from
general/secondary knowledge at the time this was written, not a
citation. Flagged in `PROJECT_HANDOVER_V2.txt`'s open-questions
section as something to verify against NSE's own holiday calendar
before being treated as confirmed -- the data-verified fact above (no
genuine expiry that day, real expiry on Monday) stands independently
of whether this specific explanation for it turns out to be correct.

**This exact anomaly was already visible and already flagged, twice,
without being explained.** The 2026-08-13 pipeline-extension entry and
the 2026-08-14 baseline-analysis entry both recorded 2025-10-21 as an
"expiry_candidate" date with zero same-day-expiry rows -- noted as an
anomaly at the time, attributed loosely to the Thursday-to-Tuesday
regime transition, and left unresolved. It was not that; it was this.

## The decision, recorded before any result is known

**2025-10-20 meets the original pre-registered rule -- "trade every
weekly expiry day" -- exactly as written.** It is a genuine same-day
NIFTY expiry with real, tradeable option data. Excluding it would mean
applying the strategy's own entry rule inconsistently: every other
week's expiry gets traded regardless of which specific weekday it
landed on, and this week's should be no different just because the
gap in coverage happened to hide it until now.

**Decision: 2025-10-20 is included as a data completeness correction,
not a parameter change.** No rule of the strategy is being altered --
strike distance, volume filter, entry/exit timing are all unchanged.
What changes is that the baseline's *input data* gains one row it
should have had from the start. This decision is made and recorded
here before its P&L is computed, so it cannot be influenced by
whether that number turns out to be favorable or unfavorable.

## A known limitation, documented rather than silently patched

`src/download_bhavcopy.py`'s holiday-rollback only triggers on HTTP
404. It has no way to detect "the market was nominally open but ran a
ceremonial session with no real expiry that day" -- a rarer, more
specific failure mode than a full closure, and one this project only
discovered by accident, via downloading literally every trading day
for an unrelated experiment. This limitation is recorded here, not
fixed by editing `download_bhavcopy.py` in this entry: per this task's
constraints, no protected file is touched, and a proper fix (e.g.
cross-checking every targeted date's same-day-expiry row count against
the official NSE holiday calendar, not just its HTTP status) is a
separate, deliberate task, not a quiet patch folded into finding the bug.

## What happens next

Per explicit instruction, this task stops here. The corrected baseline
(including 2025-10-20) has not been run. `RESULTS_EXTENSIONS.md` has
not been updated. That is deliberately left for a subsequent task.
