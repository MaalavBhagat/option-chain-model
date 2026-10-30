# Research Journal — 2026-08-16 (event-day case studies)

New script: `src/event_day_study.py`. Output: `outputs/event_day_case_studies.csv`.
No existing file was modified -- `config/strategy.json`, `backtest_strangle.py`,
`download_bhavcopy.py`, `extract_chain.py`, `RESULTS.md`,
`outputs/backtest_trades.csv`, and `outputs/paper_blotter.csv` are all
untouched by this entry.

## Correction to the task's own premise (found before writing anything else)

The task that produced this script described the existing -Rs 50,479
figure for 2024-06-04 as **"previously ESTIMATED from a linear fit."**
That's not accurate, and it's worth correcting plainly rather than
quietly going along with it: that figure was **already a real-data
measurement**, not a linear-fit estimate. It came from the 2026-08-13
stress test (`journal/2026-08-13-baseline-analysis.md`, "Experiment 2:
stress test"), which downloaded 2024-06-04's actual bhavcopy, found its
real nearest expiry (2024-06-06), and computed P&L from real `OpnPric`/
`ClsPric` values -- exactly the same underlying method this new script
uses, just done by hand for one date instead of systematically for 28.
The genuinely linear-fit-derived numbers in this project live in a
*different, unrelated* entry -- `journal/2026-08-14-regime-extrapolation.md`,
which extrapolates to 2016-2023 and never touches 2024-06-04 at all
(2024 already has real option data, so it was never in scope for that
extrapolation).

The likely source of the mix-up: the 2026-08-13 entry and `RESULTS.md`
both use the word "estimate" for the 2024-06-04 figure, but they mean
*"an estimate of what a same-day-expiry trade would have looked like,
since we used the nearest-available expiry as a proxy"* -- not
*"a statistically fitted approximation."* That's a real ambiguity in
how the earlier work was worded, and it's reasonable that it read as
"linear fit" on a fresh pass. Flagging it here so it doesn't propagate
further.

**What this script actually adds, then, is not "estimate becomes
measurement" for 2024-06-04 specifically** -- confirmed below, the
number doesn't move at all. What it adds is turning a one-off, by-hand
calculation into a **systematic, code-reusing, comprehensive study
across all 28 qualifying scheduled event dates**, with proper download-
failure handling, volume-filter reporting, and DTE tracking -- none of
which existed as a reusable script before this entry.

## Why only scheduled dates (no hindsight selection)

Every date studied comes from `config/event_calendar.csv` -- 47 rows,
each with a source URL, built in the 2026-08-13/14 sessions from
official RBI/Fed/government sources and dated news coverage of the
Election Commission's published schedules. No date was added because
it turned out to be a big-move day. This matters because the entire
point of this exercise is to distinguish "the strategy got unlucky
with the calendar" from "we went looking for bad days after the fact" --
the second would be hindsight selection and would make every number
here meaningless as risk analysis, however interesting it looked.

Of the 47 calendar rows, 46 unique dates remained after deduplication.
15 were already inside the existing 136-trade backtest (real expiry
days), and 3 were not NSE trading days per the yfinance index data --
leaving **28 dates studied here**, none chosen after the fact.

## The measured 2024-06-04 result

| | |
|---|---|
| Prior figure (real data, by-hand, 2026-08-13) | -Rs 50,479.00 |
| This script's result (same method, automated) | -Rs 50,479.00 |
| Difference | Rs 0.00 |

Exact match, as expected once the correction above is understood -- both
used 2024-06-04's real bhavcopy, the same nearest expiry (2024-06-06,
2 DTE), the same strike-selection rule, and the same entry/exit prices.
This is a consistency check that passed, not a new finding.

## The other 27 dates: genuinely new information

Sorted worst to best (zero-cost), the other 27 scheduled event dates
that were never expiry days:

- **2024-06-07** is the second-worst at -Rs 10,166.00 (6 DTE) -- an RBI
  MPC date that happened to fall right after the Lok Sabha result
  week, so some of that week's volatility likely carried over.
- Every other date -- 25 of the remaining 27 -- falls between about
  -Rs 3,500 and +Rs 12,500, a much tamer range in line with the sizes
  seen in the real 136-trade backtest.
- The best result, **2024-07-23 (full Union Budget 2024-25), made
  Rs 12,460.50** -- a reminder that "scheduled event" does not mean
  "bad for this strategy" on its own; this echoes the 2026-08-13/14
  finding that the event filter as a blanket rule made results worse,
  not better.

Full detail, including DTE, strikes, and both cost variants, in
`outputs/event_day_case_studies.csv`.

## The time-value caveat (restated, because it matters for every number above)

None of the 28 trades studied here are same-day-expiry trades. The
strikes were priced off whatever weekly expiry was nearest on that
date -- 1 to 6 days out -- so the closing price used to exit each leg
still contains real time value, not just the pure intrinsic value a
same-day expiry would have. **These 28 P&L figures are not directly
comparable to the 136-trade backtest's win rate or P&L distribution,
and must never be pooled with it.** The CSV carries this warning as its
literal first line, and the script carries it as a top-of-file comment,
specifically so this can't be forgotten by whoever opens the file next.

## Lot size convention

`config/strategy.json`'s `lot_size` (65) was applied as a flat constant
across all 28 dates, including several from 2024 and early 2025 --
before the point where NIFTY's lot size was reportedly 75. This matches
`backtest_strangle.py` exactly: it also applies `lot_size` as a single
constant with no date-dependent logic anywhere in the code. This
script does not "fix" that inconsistency, because doing so would give
these 28 case studies a different lot-size convention than the
136-trade backtest they're meant to sit alongside, which would make
comparisons *less* trustworthy, not more. Flagged here as a known,
unaddressed limitation in the underlying pipeline -- not something this
script attempted to resolve on its own, per the instruction not to
modify any existing file.

## What surprised me / what failed

- **Nothing failed.** All 28 downloads succeeded on the first attempt
  (no holiday-rollback needed, since the exact scheduled date is what
  we want and no substitution is allowed), and all 28 passed the
  1,000-contract volume filter comfortably -- the smallest of the 56
  leg-volumes observed was still in the hundreds of thousands of
  contracts. Scheduled-event days, it turns out, are liquid days.
- **Two dates' nearest expiry landed on an unexpected weekday**:
  2024-04-05's nearest expiry (2024-04-10) is a Wednesday, and one
  other date similarly resolved to a Monday, both against the
  Thursday/Tuesday regime expectation. This isn't a bug -- it's the
  same holiday-shift behavior already documented in `download_bhavcopy.py`
  (an expiry due on a holiday moves to the previous trading day), just
  observed here from the demand side (reading whatever expiry NSE
  actually lists) rather than the supply side (the downloader's own
  rollback logic). Both cases are flagged in the `notes` column rather
  than silently accepted.
- **The 2024-06-04 exact-match result** was itself the most useful
  surprise of this entry, in the sense that it forced the correction
  above -- a good reminder to check what a cited number's methodology
  actually was before describing it as being replaced.
