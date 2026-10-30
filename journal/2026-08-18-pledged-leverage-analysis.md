# Research Journal — 2026-08-18 (pledged-leverage study, analysis phase)

This entry covers two runs and two design errors. The first run
(`outputs/pledged_leverage_analysis.csv`, commit `2a0ff3e`) was flawed
in how it booked P&L. The corrected run
(`outputs/pledged_leverage_analysis_v2.csv`, commit `43de021`) is the
result this project stands behind. Before that, the *predecessor* study
(`outputs/pledged_collateral_analysis.csv`, commit `27c4cd4`) was flawed
in a different and more fundamental way -- its design could not have
produced any answer other than the one it produced.

Neither flawed run has been edited, deleted, or patched. Both stay on
disk exactly as committed, each now with a companion warning note
(`*_WARNING.txt`) beside it pointing at what supersedes it. That is the
standing discipline in this project: a superseded finding stays visible,
because the fact that an error was found and corrected is itself part of
the record.

Every figure in this entry was recomputed directly from the CSV files in
a read-only verification pass before anything was written down. Where a
figure could not be confirmed, it is not quoted.

---

## Design error 1 -- cash defined as a fraction of margin

**Which study:** the pledged-collateral study, pre-registered
2026-08-17 (`a595a6b`), analyzed at `27c4cd4`.

**In plain language.** That study asked: if you fund this strangle's
margin by pledging shares instead of posting cash, could a bad day ever
force a margin call? To answer that it needed to know how much cash the
account holds. It set the cash `C` equal to a *fraction* of that same
trade's own margin requirement -- the base case used 50%.

That single choice destroyed the test. The available-margin formula was
`A = C + min(U, C)`, where `U` is the haircut-adjusted value of the
pledged shares. If `C` is defined as half the margin requirement, and
the pledged pot is big enough that `min(U, C)` returns `C` rather than
`U`, then `A = C + C = 2C =` the margin requirement, exactly. A margin
breach means the requirement exceeds `A`. But `A` was built to *equal*
the requirement. The breach could then only ever happen through
rounding -- never because a genuinely bad day strained the collateral.

Reporting "zero margin breaches across 137 trades" as a risk finding
would have been reporting the definition of `C` back to ourselves.

**The signature of the flaw, confirmed from the file.** In the 2,484
hedged rows at the 50%-cash base case, the minimum coverage ratio across
the entire sample is **exactly 1.0000**, and Type 1 breaches are
**0 of 2,484**. A real stress test produces a spread -- some trades near
the edge, some far from it. A minimum pinned at exactly 1.0000, for the
single worst trade out of 137, is the fingerprint of a quantity computed
from itself. At the 0%-cash sensitivity the mirror image appears: **all
2,484 rows breach**, coverage ratio 0.0 -- equally mechanical, equally
uninformative.

**The second, compounding problem: the pot was too big to bind.** The
pledged pot was Rs 10,00,000 against a largest single-trade hedged
margin requirement of **Rs 29,295** -- a ratio of **34.1x**, confirmed
from the file. A collateral pot 34 times larger than anything it needs
to cover cannot be stressed by anything in the sample, regardless of how
`C` is defined.

**What this invalidated.** Predictions 1, 2 and 4 of that study were
withdrawn as evidence -- not because the arithmetic was done wrong, but
because the design admitted no other answer. Prediction 4 in particular
("beta 1.3 produces more breaches than beta 0.7") could not have passed
under *any* beta: the collateral pot never entered the cash-breach test
at all, and the margin test was pinned by construction. A prediction
that cannot fail informatively is not a prediction. The study's reported
1,638% return-on-posted-cash headline was withdrawn for the same reason:
it is a capital-efficiency artifact of dividing by a small `C` that was
itself derived from a small margin requirement, not a risk-adjusted
result. You cannot report a return on something you never actually
stressed.

**The fix, in the replacement design.** Cash `C` became a *fixed account
balance chosen in advance* -- Rs 25,000 / 50,000 / 1,00,000 / 2,00,000,
each tested independently -- never derived from a trade's own margin
requirement. And the pot was resized to Rs 2,00,000, roughly 7-8x the
largest requirement rather than 34x, so it could actually bind. This was
pre-registered at `9137600` before any number for the new design existed.

---

## Design error 2 -- booking forced closes at the intraday-high ceiling

**Which study:** the pledged-leverage study's first run, `2a0ff3e`.

**In plain language.** The new design added a forced-close rule: if the
worst intraday mark-to-market loss exceeds your cash `C`, you cannot sit
there quietly until the close -- the position gets shut. That rule is
correct and necessary; without it the levered arm could book profits on
a path it could not have survived to collect.

The error was in *what price the forced close got booked at*. The run
measured the intraday worst case by taking each short leg at its own
daily High price. It then used that same worst-tick price as the
**realized exit price** for the trade.

Why that is not defensible: the call's daily high and the put's daily
high do not have to occur at the same moment. A short strangle is hurt
by the index moving hard in *one* direction -- which pushes one leg's
price up while pushing the other's down. Taking both legs at their
individual daily highs simultaneously describes a moment that, on most
days, never existed. The study's own pre-registration said exactly this,
in advance: method (b) is "a conservative upper bound on a price path
that may never have actually existed, not a measured worst moment. It's
a ceiling, not an observation."

The run then treated that ceiling as an observation anyway. Using a
never-observed price as a *trigger* for "this position would have been
in trouble" is conservative and reasonable. Using it as the *price you
actually got filled at* records an impossible loss as a real one.

**The fix, in v2.** One change and one change only: when a forced close
triggers under any measure, the P&L booked always uses the observed
close-based price (`call_exit` / `put_exit`), never the intraday high.
The high-based ceiling still decides *whether* a close triggers; it no
longer decides *how much you lost*. The corrected run separates this
into three explicit scenarios instead of the original's two-value
measure column:

- **S1** -- no forced closes at all. The upper bound; the calm-market
  picture.
- **S2** -- close-triggered, close-booked. Numerically identical to the
  original run's close-measure rows.
- **S3** -- high-triggered, close-booked. **The primary corrected
  result.**

**Confirmation that only the booking changed.** S3's forced-close counts
reproduce the original run's high-based counts exactly. The base-case S3
counts verified here (Arm A = 2 at every cash level; Arm B = 15 / 18 /
19 / 19) multiply by the nine beta-by-haircut cells to give 18 / 135 /
162 / 171 -- the totals recorded in `43de021`. The trigger formula is
untouched; only the price at which the loss is recorded moved.

**What survived the flaw and what did not.** Forced-close *counts* under
both measures were always valid -- counting "did the peak loss exceed
`C`" does not depend on what price you book the exit at. The close-based
totals were always valid, since a closing price is a real observed
number. What was invalid was every high-based *rupee and points total*
in the first run.

---

## A claim from discussion that the verification pass corrected

Recorded because this project treats a corrected claim as part of the
record, not something to quietly drop.

In discussion of this write-up I was given the claim that the original
run's **high-based total rupee figures were negative at every cash
level**. The read-only verification pass checked this directly against
`outputs/pledged_leverage_analysis.csv` and it is **half right**:

- **Arm B (levered): negative at every cash level** -- and not only in
  the base case, but in all 36 beta-by-haircut-by-cash cells.
  Base-case totals: −90,550 (C=25,000), −336,090 (C=50,000),
  −765,637 (C=1,00,000), −15,69,840 (C=2,00,000).
- **Arm A (unlevered): positive at every cash level**, in all 36 cells.
  Base-case totals: +49,242, +155,485, +402,824, +846,917.

So the blanket phrasing is wrong and must not be repeated. The correct
statement is that **the flawed booking hit the levered arm
disproportionately, because Arm B holds double the lots** -- the same
impossible per-lot loss, applied to twice the position, was enough to
drive Arm B's totals negative while leaving Arm A's positive. The commit
messages' shorthand that the high-based totals "came out large and
negative" is a fair description of what motivated the correction, but it
describes Arm B, not both arms.

---

## What the corrected run shows

Base case throughout: beta 1.0, haircut 9% (the SEBI floor), scenario
S3, 137 trades, 2024-01-04 to 2026-08-11. Hedged iron condor only.

**Position size roughly doubled, as designed -- but see the
integer-lot qualification below.** `min(U, C)` caps the pledged shares'
contribution at exactly the cash amount, so `A <= 2C` always. Verified
across all 14,796 rows of v2 and all 9,864 rows of the original: **zero
violations**, maximum `A_t / 2C` ratio exactly 1.000000. This study
structurally cannot produce a result implying unlimited leverage.

**The cap is on available margin, not on lots.** Lots are whole
numbers, so Arm B gets `floor(2C / m)` lots against Arm A's
`floor(C / m)`, and the first is generally MORE than twice the second.
The aggregate lot ratio reaches **2.42x at C=Rs 25,000**, and on **18
individual trades Arm B holds 3x Arm A's lots**, not 2x -- the cases
where Arm A can afford exactly one lot and Arm B can afford three.
"Roughly doubled" is an accurate aggregate description at the larger
cash levels and an understatement at the smallest. Full detail in the
prediction 1 addendum at the end of this entry.

**Forced closes multiplied.** Arm A: **2** of 137 at every cash level.
Arm B: **15 / 18 / 19 / 19** as cash rises from Rs 25,000 to
Rs 2,00,000. Under S1 -- the no-forced-close scenario -- both arms
record **zero** forced closes, across every single row of the file, at
every beta and haircut.

**Net rupees, Arm A vs Arm B:**

| Cash `C` | Arm A | Arm B | Arm B's edge |
|---|---|---|---|
| Rs 25,000 | 77,946 | 157,183 | **+79,237** |
| Rs 50,000 | 212,891 | 288,565 | **+75,674** |
| Rs 1,00,000 | 517,637 | 568,789 | **+51,152** |
| Rs 2,00,000 | 10,87,872 | 11,09,754 | **+21,882** |

Arm B is ahead at every cash level tested, but the edge shrinks
monotonically as the account gets bigger -- from +79,237 down to
+21,882.

**Worst single trade: exactly 2.00x.** In both arms the worst trade is
**2026-02-03**, at every cash level, and the ratio is exactly 2 (checked
as an exact fraction, not a rounded decimal). Arm A / Arm B:
−36,777 / −73,554, then −73,554 / −147,108, then −147,108 / −294,216,
then −294,216 / −588,432. Both arms are force-closed that day and Arm B
holds precisely double the lots. This is what leverage does: the same
bad day, twice the size.

**The cost of forced exits.** Using the sign convention **S3 minus S1**
-- the P&L hit from imposing forced closes on the no-forced-close
baseline, so a negative number means money lost to being shut down --
at C=Rs 2,00,000: **Arm A −131,921, Arm B −12,97,938**. Arm B pays
roughly ten times what Arm A pays for the same rule.

---

## The participation effect at C=Rs 25,000 -- read this before quoting the +79,237 figure

Arm B's largest edge, +Rs 79,237 at C=Rs 25,000, is **not** clean
evidence that "leverage helps small accounts most."

Verified directly from both files: at C=Rs 25,000 -- and only at that
cash level -- **Arm A cannot fund a single lot on 30 of the 137
trades.** Arm B trades all 137. Those 30 dates account for 810 rows in
v2 and 540 rows in the original file, every one of them carrying
`cash_insufficient_1lot_A = True` and contributing exactly Rs 0.00 to
Arm A's totals.

So a substantial part of that +79,237 is Arm B **being able to show up
on days Arm A cannot participate in at all** -- not Arm B earning more
per trade on the days both arms traded. The flag is in the data and is
not silent, but the headline number is misleading without it. Any future
summary quoting +79,237 must quote the 30-trade participation gap
alongside it.

---

## Predictions -- reported honestly, not softened

Pre-registered at `9137600`, judged on the corrected S3 base case.

1. **Arm B's gross premium close to 2x Arm A's at every C** --
   **FAILED**, on the upside. Gross ratios (S1, base case): **2.61x /
   2.37x / 2.10x / 1.97x**. Two of the four cash levels fall outside a
   +/-10% band. Adjudicated after the fact -- see the addendum at the
   end of this entry for the figures, the threshold problem, and the
   mechanism.
2. **After forced closes, Arm B's advantage is less than 2x** --
   **FAILED at C=Rs 25,000 only** (ratio 2.02x), **PASSED at the other
   three** (1.36x, 1.10x, 1.02x). Note that the single failure sits at
   exactly the cash level where the participation effect above is
   operating.
3. **Arm B suffers more forced closes than Arm A at every C** --
   **HELD.** 15/18/19/19 against 2/2/2/2.
4. **At the lowest C, Arm B's net result is WORSE than Arm A's** --
   **FAILED.** Arm B made Rs 157,183 against Arm A's Rs 77,946 at
   C=Rs 25,000. The prediction expected leverage to be punished hardest
   where cash is thinnest; instead the thin-cash case is where Arm B
   won by the most. The participation effect is the likely reason, and
   that is a reason the prediction did not anticipate.
5. **There exists a C above which Arm B beats Arm A on net rupees** --
   **HELD**, though trivially: Arm B beats Arm A at *every* C tested, so
   the prediction is satisfied without discriminating between them.
6. **Arm B's worst single-trade loss is at least 1.8x Arm A's** --
   **HELD.** Exactly 2.00x at every cash level.

Three of six failed (predictions 1, 2 and 4 -- see the addendum below
for 1). Consistent with this project's track record (the
strike-distance grid, the pre-holiday hypothesis, four of five every-day
predictions), the failures are reported as failures.

---

## What this study does NOT establish

**There is no crash in this sample.** 2024-01-04 to 2026-08-11 contains
no event on the scale of 2024-06-04 (which is not an expiry day and is
not one of these 137 trades) or the 2020 COVID period (for which no real
option data exists anywhere in this project). The whole wrong-way-risk
question -- does the pledged collateral lose value at the exact moment
the strangle needs it most -- is the question that motivated this line
of work, and **this sample cannot answer it.**

**The beta and haircut sensitivities did not bind below C=Rs 2,00,000.**
Verified: at C=25,000 / 50,000 / 1,00,000, `A_t` equals `2C` on all 137
rows, meaning `min(U, C)` returned `C` every time -- the pledged pot was
never the binding constraint. Only at C=Rs 2,00,000 does the pot bind,
and there on 50 of 137 rows. The reason is direct: **the haircut-adjusted
pot never fell below Rs 1,17,796 anywhere in the entire grid** (that
floor occurs at the harshest corner tested, beta 1.3 with the unverified
40% haircut; at base-case beta 1.0 and the 9% SEBI floor the minimum is
Rs 1,79,429, on 2024-01-25). A pot that never drops below Rs 1,17,796
cannot be the binding constraint against cash of Rs 25,000 or
Rs 50,000. So 24 of the 36 grid cells carry no information about beta or
haircut at all. **The collateral-risk question this whole line of work
set out to answer remains untested.**

**The 40% haircut sensitivity rests on an unverified secondary source**
(Business Standard, 2026-03-31, reported April 2026 tightening), not on
any SEBI, NSE or RBI primary document. Labelled as such wherever it
appears.

**Data integrity checks, all clean.** Both leverage CSVs contain exactly
137 distinct trade dates spanning 2024-01-04 to 2026-08-11, including
the Monday **2025-10-20** correction, with a perfectly uniform row count
per date (108 in v2, 72 in the original), so no date is over- or
under-weighted in any total. Neither file contains a single NaN or
infinite value. `lots_B` is never zero. The only zero-lot rows are the
Arm A participation gap documented above, all flagged.

---

---

## Addendum -- prediction 1 adjudicated (added after commit `8ae638e`)

Prediction 1 was left open in the original write-up because its figures
had not been independently re-verified at that point. It has now been
computed and is closed here. This is the last open prediction from the
study.

**Basis:** `outputs/pledged_leverage_analysis_v2.csv`, beta 1.0,
haircut 9%, **scenario S1** -- the correct basis for a "before forced
closes" figure, confirmed two ways: forced closes are zero in both arms
across all 548 base-case S1 rows, and realized P&L equals gross P&L
exactly in both arms there.

### The figures

| Cash `C` | Arm A gross | Arm B gross | Ratio B/A | Deviation from 2x |
|---|---|---|---|---|
| Rs 25,000 | 94,044.25 | 245,088.50 | **2.61x** | +0.61 |
| Rs 50,000 | 245,088.50 | 582,032.25 | **2.37x** | +0.37 |
| Rs 1,00,000 | 582,032.25 | 12,19,793.25 | **2.10x** | +0.10 |
| Rs 2,00,000 | 12,19,793.25 | 24,07,692.25 | **1.97x** | −0.03 |

### Verdict: FAILED

Treating "close to 2x" as +/-10% (a 1.80x-2.20x band): C=Rs 25,000
**fails** at 2.61x, C=Rs 50,000 **fails** at 2.37x, C=Rs 1,00,000
**passes** at 2.10x, C=Rs 2,00,000 **passes** at 1.97x. The prediction
says "at every C," so two failures make it a failure as written.

**The prediction failed on the UPSIDE.** Arm B's gross premium was
*more* than double Arm A's, not less. The prediction's implicit
expectation -- that leverage delivers at most a doubling -- was too
conservative at low cash, not too generous.

### The threshold was set at adjudication time -- recorded as a weakness

**The +/-10% band was chosen now, at adjudication, not in the
pre-registration.** This is a genuine weakness in the original
prediction's wording: "close to 2x" carries no number, so nothing
structurally prevented the threshold from being picked after the ratios
were visible. The band was fixed before the figures were examined, but
that is a matter of process discipline in one session, not something the
pre-registration enforced, and it should not be presented as though the
pre-registration had pinned it down. It did not.

How much the choice matters, stated plainly so the reader can judge it
independently:

- **The C=Rs 25,000 failure at 2.61x is robust.** No band a reasonable
  person would have written in advance -- +/-10%, +/-20%, even +/-25% --
  admits 2.61x as "close to 2x."
- **The C=Rs 50,000 failure at 2.37x is NOT robust.** A +/-20% band
  (1.60x-2.40x) would pass it, making the verdict 3-of-4 rather than
  2-of-4.

The overall FAIL survives either band, because of C=Rs 25,000. The
*count* of failing cash levels does not.

### The participation explanation was proposed, and is disconfirmed

In discussion it was proposed that the deviation from 2x is driven by
the Arm A participation gap -- Arm A sitting out trades it cannot fund,
suppressing its gross and inflating the ratio. **This adjudication
disconfirms that as the general explanation.**

| Cash `C` | Deviation | Arm A sit-out trades |
|---|---|---|
| Rs 25,000 | +0.61 | **30 of 137** |
| Rs 50,000 | +0.37 | 0 |
| Rs 1,00,000 | +0.10 | 0 |
| Rs 2,00,000 | −0.03 | 0 |

Sit-outs occur at C=Rs 25,000 and nowhere else. At C=Rs 50,000 Arm A
funds at least one lot on all 137 trades and the ratio is still 2.37x,
well outside the band, with no participation gap available to explain
it. Participation cannot be the common driver.

It does contribute at the smallest cash level. Restricting C=Rs 25,000
to the 107 dates Arm A could actually trade, the ratio falls from 2.61x
to **2.27x** -- so **roughly half the excess deviation there is
participation** (Arm B earned +Rs 31,606 gross on the 30 days Arm A sat
out), and the rest is not.

### The mechanism common to all four levels: integer lot rounding

Lots are whole numbers. Arm B gets `floor(2C / m)` lots against Arm A's
`floor(C / m)`, and `floor(2C / m)` is generally **more** than twice
`floor(C / m)`. The proportional gain from that rounding is largest when
lot counts are smallest -- i.e. at low cash.

Measured on tradeable rows only (`lots_A > 0`), so the participation gap
is removed entirely, `lots_B / (2 x lots_A)` runs:

**1.121 / 1.086 / 1.037 / 1.006** across C = 25,000 / 50,000 / 1,00,000
/ 2,00,000.

Monotone decreasing, and matching the deviation ordering exactly --
including at C=Rs 50,000, where participation explains nothing at all.
This is the mechanism.

### Consequence: a qualification to the "position size roughly doubled" headline

**Available margin is capped at `2C`, and this was verified with zero
violations across every row of both files.** That cap is real and it is
not what is being qualified here.

**Position size in lots is not capped the same way.** Because lots are
whole numbers, Arm B's lot count can exceed twice Arm A's:

- The **aggregate lot ratio reaches 2.42x at C=Rs 25,000** (400 lots
  against 165).
- On **18 individual trades, Arm B holds exactly 3x Arm A's lots** --
  the cases where Arm A can afford one lot and Arm B can afford three.
- The effect fades as cash grows: by C=Rs 2,00,000 the aggregate lot
  ratio is 2.013x, and the per-trade maximum is 2.17x.

So "pledging roughly doubled position size" is accurate at the larger
cash levels and an **understatement at the smallest**, where it
sometimes tripled it. Nothing already committed is contradicted --
`A <= 2C` holds everywhere -- but the headline describes margin capacity
more precisely than it describes lots, and a reader sizing a small
account from it would be misled in the direction of *more* risk than the
headline implies, not less.

## Files

Written this session: this entry (the prediction 1 addendum above was
added in a later commit, which also updated the corresponding
`RESULTS_EXTENSIONS.md` section), a new section in
`RESULTS_EXTENSIONS.md`, and two companion warning notes --
`outputs/pledged_collateral_analysis_WARNING.txt` and
`outputs/pledged_leverage_analysis_WARNING.txt`.

Not touched: `RESULTS.md`, both pre-registration journal entries, both
config files, all three analysis scripts, and all three output CSVs
(including the two flawed ones -- the warnings sit *beside* them as
separate files, never inside them).
