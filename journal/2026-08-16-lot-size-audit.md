# Research Journal — 2026-08-16 (lot size audit)

New files only: `config/lot_size_history.csv`, `src/lot_size.py`. Nothing
existing was touched -- `config/strategy.json` still reads flat
`lot_size: 65`, `backtest_strangle.py` still applies it uniformly, and
`outputs/backtest_trades.csv` is unchanged. `src/lot_size.py` is not
imported anywhere yet.

## The documented assumption

`config/strategy.json` has always used a single flat `lot_size: 65` for
every trade in the 136-trade baseline, 2024-01-04 through 2026-08-11.
This was flagged as a known simplification back in the 2026-08-16
event-day-study entry, at the time believed to be a two-regime story
(65 now, reportedly 75 before some point in early 2026).

## What was actually asked to be checked, and what the exchange data says

This entry's task supplied a three-regime claim (25 until Nov 2024, then
75, then 65 from 2025-12-31), attributed to NSE/SEBI sources. Before
building anything from that citation, the raw bhavcopy files were
checked for a lot-size field -- and found one: **`NewBrdLotQty`**, a
real per-contract column present in every downloaded bhavcopy, listed
alongside the full column set in the terminal output for this task.
Per the task's own instruction, a field like this is more authoritative
than any inferred date, so it was used directly rather than trusting
either the supplied citation or this project's own prior assumption.

**The real history is four regimes, not two and not three:**

| Lot size | First observed (same-day-expiry) | Last observed | Baseline trades |
|---|---|---|---|
| 50 | 2024-01-04 (start of this project's data) | 2024-04-25 | 17 |
| 25 | 2024-05-02 | 2025-01-30 | 36 |
| 75 | 2025-01-02 | 2025-12-30 | 51 |
| 65 | 2026-01-06 | 2026-08-11 (latest data) | 32 |

Neither this project's flat-65 assumption nor the supplied three-regime
citation was correct. The citation was closer (it had the right *shape*
-- multiple transitions, correct approximate 75 and 65 values) but
missed the 50-lot regime entirely and had the wrong date for the
65-lot transition (the real one is late October 2025 / early January
2026, not December 2025).

Real NSE circulars were found and cited for all three transitions
(`config/lot_size_history.csv`):
- **FAOP61415** -- 50 -> 25, effective 2024-04-26 (first affected weekly
  expiry: 2024-05-02, exactly matching this project's own data)
- **FAOP64625** -- 25 -> 75, effective 2024-11-20
- **FAOP70616** (NSE/FAOP/70616, Ref 176/2025, dated 2025-10-03) -- 75 ->
  65, effective EOD 2025-10-28, with the circular itself stating the
  change is reflected from the 2026-01-06 weekly expiry -- again
  exactly matching this project's own data.

## How it was found

1. Checked the full column list of one raw bhavcopy file --
  `NewBrdLotQty` present, populated, single-valued per contract series.
2. Scanned every raw bhavcopy already downloaded (199 files) for
  `NewBrdLotQty` on NIFTY index options, tracking where the observed
  value set changed -- this surfaced the 50-lot regime and the
  transition windows before any web search was done.
3. For precision, matched each of the 136 baseline trades to its own
  specific same-day-expiry contract's `NewBrdLotQty` (not a date-level
  average or a global "what's listed today" value) -- 136/136 resolved
  to exactly one lot size each, no ambiguity at the individual-trade
  level.
4. Searched for and cited the underlying NSE circulars afterward, to
  document *why* the data looks the way it does, not to determine the
  dates themselves -- the data was already authoritative.

## Which results are affected, and in which direction

Recomputed read-only (no files touched):

| | Reported (flat 65) | Corrected (actual per-trade lot size) | Difference |
|---|---|---|---|
| 136-trade baseline total P&L | Rs 171,473.25 | **Rs 148,660.25** | **-Rs 22,813.00** |
| 2024-06-04 stress-test figure | -Rs 50,479.00 | **-Rs 19,415.00** | **+Rs 31,064.00** |

By regime, the baseline P&L moves in both directions depending on
whether the true historical lot size was above or below 65:

| Lot size | Reported (at 65) | Corrected | Direction |
|---|---|---|---|
| 50 | Rs 20,858.50 | Rs 16,045.00 | overstated |
| 25 | Rs 42,318.25 | Rs 16,276.25 | overstated |
| 75 | Rs 52,276.25 | Rs 60,318.75 | understated |
| 65 | Rs 56,020.25 | Rs 56,020.25 | correct (no change) |

The headline baseline total is overstated overall (-Rs 22,813, about
13%), but that net figure hides a much larger effect at the individual
period level: the 25-lot era's P&L is currently reported at **2.6x**
its real rupee value, and the 2024-06-04 stress scenario -- this
project's single most-cited finding -- is overstated by **2.6x** too
(both use the same 65-vs-25 ratio, since that trade's contract was also
lot size 25).

## The time-value / grandfathering limitation this table can't fully resolve

`config/lot_size_history.csv` and `src/lot_size.py` use clean
`effective_from`/`effective_to` date ranges, matching what was asked
for. But the underlying reality is not a clean calendar cutover --
NSE's grandfathering rule lets an already-listed contract keep its
original lot size until its own expiry, so two different lot sizes can
genuinely coexist across different expiries on the very same trade
date. This was verified directly, not just inferred: **2025-01-02's
same-day-expiry contract was already 75, while 2025-01-30's was still
25** -- a later date with the *older* lot size, because that particular
week's contract had been listed before the 2024-11-20 cutover and
simply hadn't expired yet.

Running `src/lot_size.py` confirms the table gets this specific case
wrong: `get_lot_size('2025-01-30')` returns **75** (correct per the
clean date-range table) but the *actual* traded contract that day was
lot size **25**. This is flagged prominently in both the CSV's `notes`
column and the script's module docstring: the lookup is reliable
outside the roughly 2-3 month windows around each transition, and
should not be trusted alone inside them -- `NewBrdLotQty` from the
actual bhavcopy is the only fully correct source for a specific
contract in that window.

## Update: the bug above is fixed

The version of `get_lot_size()` described above shipped knowing it could
silently mislead -- it only ever consulted the date-range table, so
`get_lot_size('2025-01-30')` returned 75 with no indication that the
real answer was 25. That's now fixed:

- `get_lot_size()` returns **`(lot_size, source)`**, never just a bare
  number, so a caller can never mistake an approximation for ground
  truth without deliberately ignoring the second value.
- **Primary path**: reads `NewBrdLotQty` directly from that date's own
  downloaded bhavcopy, for the specific same-day-expiry NIFTY contract
  -- the same per-contract lookup used to build the corrected figures
  in this entry. Source reported as `"bhavcopy"`.
- **Fallback path**: the `config/lot_size_history.csv` date-range table,
  used *only* when no bhavcopy zip is available locally for that date.
  Source reported as `"lot_size_history.csv"`, so it's always visibly
  labeled as the weaker of the two.
- Verified: `get_lot_size('2025-01-30')` now returns `(25, "bhavcopy")`
  -- correct, and honestly sourced. `get_lot_size('2024-06-04')` returns
  `(25, "lot_size_history.csv")`, correctly falling back, because
  2024-06-04 wasn't an expiry day at all -- there is no same-day-expiry
  contract for the bhavcopy path to find, so the fallback is the right
  behavior there, not a bug.
- `tests/test_lot_size.py` adds a regression test asserting
  `2025-01-30` returns `(25, "bhavcopy")` specifically, plus three
  supporting tests (the 2025-01-02 contrast, that every result reports
  a source, and spot checks against all four known regimes). All four
  pass (`.venv/bin/python -m pytest tests/test_lot_size.py -v`).

The fallback path itself still carries the same transition-window risk
described above -- it's a fallback, not a second source of truth. But
it can no longer be reached and mistaken for the primary path without
the caller actively ignoring the `source` return value, which is the
actual fix: not eliminating the approximation, but making it
impossible to silently trust.

## Why points-based reporting should become the primary scale-invariant metric

Every rupee figure in this project's outputs depends on a lot size that
turns out to have been wrong for 104 of 136 baseline trades (76%) --
in three different, non-uniform ways depending on era. **P&L in
options points (before multiplying by any lot size) is unaffected by
any of this**: `pnl_points = (call_entry + put_entry) - (call_exit +
put_exit)` never touches `lot_size` at all, and is exactly reproducible
regardless of which lot-size story turns out to be correct. This is
the reason Task 1 of this entry's companion request added points
alongside rupees for the event-day case studies, and it's the reason
future output tables in this project should report points as the
primary, durable number, with rupees at whatever lot size is currently
believed correct shown alongside as a secondary, explicitly-dated
conversion -- so a lot-size correction like this one never requires
re-deriving the underlying result again, only rescaling it.

## What happens next is a decision, not an action taken here

This entry does not wire `src/lot_size.py` into `backtest_strangle.py`,
does not update `config/strategy.json`, and does not touch
`outputs/backtest_trades.csv` or `RESULTS.md` -- per the constraint on
this task, and because doing so is a real decision (how to handle the
grandfathering edge cases, whether to re-run and re-commit the whole
136-trade baseline, whether `RESULTS.md`'s headline numbers need
updating) that should be made explicitly, not as a side effect of an
audit.
