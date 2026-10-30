# Research Journal — 2026-08-18 (pledged-leverage study, pre-registration)

**No number has been computed for this study. No backtest, download, or
analysis script has been run.** This entry records why the previous
pledged-collateral design (pre-registered 2026-08-17 at commit `a595a6b`,
analyzed at commit `27c4cd4`) is being superseded, and the new question,
design, and predictions for the design that replaces it -- all written
down and committed BEFORE any P&L, margin figure, or breach count exists
for this new design. Full machine-readable version:
`config/pledged_leverage_experiment.json`.

**This entry does not touch, edit, or delete anything from the 2026-08-17
entry or its outputs.** `journal/2026-08-17-pledged-collateral-preregistration.md`,
`config/pledged_collateral_experiment.json`,
`src/pledged_collateral_analysis.py`, and
`outputs/pledged_collateral_analysis.csv` all stay exactly as committed.
The flawed design is part of the record and stays visible, not erased.

## Why the first design failed

In plain terms first, for the record: the first study asked "would
pledged collateral, funding the SAME position size as before, ever get
margin-called or run out of cash?" To answer that it needed a cash
number `C` for each of the 137 trades. It set `C` as a fraction (the
base case used 50%) of that same trade's own margin requirement.

That choice broke the test before it started. The available-margin
formula was `A = C + min(U, C)`, where `U` is the haircut-adjusted
value of the pledged shares. If `C` is already defined as roughly half
of the trade's margin requirement, and the collateral pot `U` is large
enough to be at least that same size (it was -- Rs 10,00,000 against a
largest single-trade requirement of Rs 29,295), then `A` comes out
equal to the margin requirement almost by definition. A margin breach
(Type 1) requires the requirement to exceed `A`. If `A` is built to
already equal the requirement, a Type 1 breach can only happen because
of rounding, never because a bad day actually strained the collateral.
Zero Type 1 breaches across 137 trades wasn't a finding about risk --
it was the arithmetic consequence of how `C` was defined.

The tell was sitting in the original output the whole time: the
**minimum coverage ratio across the entire 137-trade sample was
exactly 1.0000.** A coverage ratio of exactly 1, for the single worst
trade out of 137, is not what a real stress test produces -- real
stress tests produce a distribution, with some trades closer to the
edge than others. A ratio pinned at exactly 1.0000 for the minimum is
the signature of a quantity computed from itself.

This has a second consequence that matters as much as the breach
count: **beta could not have affected either breach test, at all,
under this design.** Type 1 was pinned at 0 (or, at cash_fraction=0%,
at 137 -- also mechanical, not a finding) regardless of how the
collateral pot moved with the index. Type 2 (cash breach) compared
peak MTM loss only to `C` directly -- the collateral pot and its beta
never entered that comparison either. So when the original prediction
4 ("beta 1.3 produces more breaches than beta 0.7") failed in the
actual run, that failure told us nothing. It could not have passed
under *any* beta value, by construction. A prediction that cannot
fail informatively is not a prediction, and reporting its failure as
if it were a finding would have been a mistake.

**Predictions 1, 2, and 4 from the original pre-registration are
therefore withdrawn as evidence** -- not because the numbers were
computed wrong, but because the design could not have produced any
other answer. **Predictions 3 (high-based MTM measure produces at
least twice as many breaches as close-based) and 5 (the 2024-06-04
stress case breaches at base case) are unaffected by this flaw and
stand** -- neither one depended on how `C` was defined relative to the
margin requirement.

One more problem, independent of the `C`-as-fraction issue: the
collateral pot itself, Rs 10,00,000, was roughly 34x the largest
single-trade margin requirement in the whole sample (Rs 29,295). A pot
that many multiples larger than anything it needs to cover can never
be meaningfully stressed, no matter how `C` is defined. The collateral
side of the model was never actually tested under that sizing.

**The reported 1,638% return-on-posted-cash headline figure from the
original analysis is withdrawn.** It's a capital-efficiency artifact
of defining a small `C` as a fraction of an already-small margin
requirement, not a risk-adjusted result. Reporting a return without
having actually stressed the thing it's a return *on* isn't
meaningful.

## What this new design asks instead

**Research question:** pledging shares lets you sell more contracts on
the same cash. Does the extra premium survive the extra risk that
leverage brings?

**The framing, recorded verbatim because it's the honest one:**

> Pledging is leverage. It buys position size, not skill. The
> strategy's per-lot points P&L is identical either way. The question
> is whether the additional premium from the larger position survives
> the additional loss on bad days and the additional cash strain,
> given that SEBI requires mark-to-market losses to be met in cash.

This reframes the study around **position size**, not around whether a
fixed position's margin gets breached. That's the structural fix: cash
is now fixed in advance and never derived from a trade's own margin
requirement, so it cannot make the answer true by definition the way
the first design did.

## Design — two arms, same 137 trades, same cash

- **Arm A (unlevered):** cash only. Position size = the largest whole
  number of lots that cash alone supports, given that trade's per-lot
  margin requirement.
- **Arm B (levered):** cash plus pledged shares. Available margin
  `A = C + min(U, C)`, per SEBI fact 4 (Other Liquid Assets may not
  exceed Cash Equivalents -- the same primary-verified fact the first
  design used, applied correctly here). Position size = the largest
  whole number of lots that `A` supports.

Both arms hold the **same fixed cash `C`**. This is the correction:
`C` is a fixed account balance chosen in advance, never a fraction of
margin. Four values are tested independently: Rs 25,000 / 50,000 /
1,00,000 / 2,00,000.

**The leverage ceiling, stated explicitly so no result can be misread:**
the levered position can never exceed 2x the unlevered one. `min(U, C)`
caps the shares' contribution at exactly the cash amount `C`, so
`A <= 2C` always, no matter how large the pledged pot or its beta is.
This study cannot produce a result implying unlimited leverage, by
construction, and any write-up must say so.

**Pledged share pot:** Rs 2,00,000 at inception (2024-01-04), floating
with NIFTY at beta 1.0 in the base case (sensitivities 0.7, 1.3).
Deliberately sized -- roughly 7-8x the largest single-trade margin
requirement rather than 34x -- so it can actually bind, unlike the
previous pot.

**Haircut:** 9% base case (the SEBI floor, primary-verified in the
first study). Sensitivities at 20% and 40% -- the 40% figure rests on
the unverified secondary source (Business Standard, 2026-03-31,
reported April 2026 tightening) and must be labelled as such
everywhere it's reported, same discipline as the first design.

**Position:** hedged iron condor only, primary case. Margin per lot =
`(max spread width x lot_size) - net credit at entry`, computed from
`outputs/backtest_trades_137.csv`'s real `lot_size` column, never a
flat assumption. **The naked position is excluded entirely from this
study** -- not run even as a sensitivity. Its 10%-of-notional margin
approximation is too crude to support a leverage conclusion either way.

## Forced-close rule (analysis-time decision, not pre-registered earlier)

If peak intraday MTM loss on the position exceeds cash `C`, the
position is closed at that point and P&L is taken there, not carried
to session close.

This is being labelled clearly as a decision made now, at
pre-registration time for THIS design, not something that was part of
the original 2026-08-17 pre-registration -- it didn't need to be there,
because the first design's `C`-as-fraction-of-margin choice meant cash
was never actually the binding constraint it could be under this new
design. Without this rule here, the levered arm could book profits on
a price path it could not have actually survived to collect -- once
cash is exhausted intraday, in reality the position doesn't get to
continue quietly to the close. The analysis phase must report how many
trades trigger this rule in each arm, separately.

## Peak MTM measurement

Same convention as the first design, reported as a **range**, never a
single number:

- (a) Close-based: `call_exit` / `put_exit` from the 137-trade
  baseline.
- (b) High-based upper bound: `HghPric` for both short legs from
  `data/processed/nifty_expiry_day_chains.csv`, with long wings valued
  at entry price throughout, to keep it a genuine ceiling.

**Caveat, pre-registered now, same as before:** the call's intraday
high and the put's intraday high don't necessarily happen at the same
moment, so method (b) is a conservative upper bound on a price path
that may never have actually existed, not a measured worst moment.

## Locked metrics

**Primary metric (nothing else may be used to judge the result):**
total points and total rupees, Arm B minus Arm A, after forced closes.
Plus the number of forced closes in each arm.

**Secondary metrics (reported, not selected on):** worst single-trade
rupee loss in each arm; number of trades where cash was insufficient
to support even 1 lot; return on `C` in each arm.

## Pre-registered predictions (write down now, report honestly later)

1. Arm B's gross premium before forced closes is close to 2x Arm A's
   at every `C`.
2. After forced closes, Arm B's advantage is less than 2x.
3. Arm B suffers more forced closes than Arm A at every `C`.
4. At the lowest `C` (Rs 25,000), Arm B's net result is WORSE than Arm
   A's.
5. There exists a `C` above which Arm B beats Arm A on net rupees.
6. Arm B's worst single-trade loss is at least 1.8x Arm A's.

None of these are softened if they fail -- same discipline as every
other prediction set in this project (the strike-distance grid, the
pre-holiday hypothesis, the every-day extension's 4-of-5 failures, and
now this study's own predecessor's contaminated predictions 1, 2, and
4 above).

## What this entry does not do

No margin figure, no position size, no forced-close count, and no
prediction pass/fail has been computed for this design. This entry and
`config/pledged_leverage_experiment.json` are the only two files
touched in this task. Nothing in the 2026-08-17 pre-registration, its
config file, its analysis script, or its output CSV was opened for
editing -- they remain the historical record of a design that turned
out to be flawed, which is itself part of the record and is not to be
erased or silently patched.
