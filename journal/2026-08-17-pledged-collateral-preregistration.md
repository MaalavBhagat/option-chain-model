# Research Journal — 2026-08-17 (pledged-collateral study, pre-registration)

**No number has been computed for this study. No backtest, download, or
analysis script has been run.** This entry records the question, the
regulatory facts it rests on, and the model and predictions -- all
written down and committed BEFORE any P&L, margin figure, or breach
count exists. Full machine-readable version:
`config/pledged_collateral_experiment.json`.

## What this study is and isn't

**Research question:** if the margin for this strangle were funded by
pledging an existing long-term equity holding rather than by fresh
cash, would the overlay ever have forced a sale of those pledged
shares -- and how much cash must sit idle for it not to?

**The framing, recorded verbatim because it's the honest one:**

> Pledging does not change the strategy's P&L by a single point. It
> changes capital efficiency and it changes what is at risk. This
> study measures the tail-risk price of that capital efficiency. It is
> not a study of whether the strangle is profitable -- that question is
> already answered elsewhere in this project and this study may not
> claim credit for it.

In plain terms: this is not another "is the strategy good" study. The
137-trade baseline already answered that. This study asks a narrower,
different question -- if you funded the margin with pledged shares
instead of cash, could a bad day force you to sell those shares (or
leave you short of cash) even though the strangle's own points-based
P&L is completely unaffected by how the margin was funded?

## Regulatory basis

**Primary source:** SEBI Master Circular Chapter 4, "Comprehensive
Risk Management for Cash Market and Debt Segment," December 2024 --
<https://www.sebi.gov.in/sebi_data/commondocs/dec-2024/RE_Chapter%204%20-%20Comprehensive%20Risk%20Management%20for%20Cash%20Market%20and%20Debt%20SegmeFINAL_p.pdf>

**Verified directly against that document (PRIMARY-VERIFIED):**

1. Para 1.1.13.4 -- clearing members must maintain at least 50% of
   total collateral as cash or cash equivalents; SEBI states
   explicitly this requirement may **NOT** be applied at individual
   client level.
2. Para 1.1.2, liquid assets table, "Other Liquid Assets" note 1 and
   note iv -- non-cash collateral **cannot** be used to meet
   mark-to-market losses; MTM must be met in cash or cash equivalents.
3. Para 1.1.2 -- equity shares as collateral carry a VaR-based haircut
   of 6 sigma, subject to a minimum of **9%**. The haircut is dynamic
   and widens with volatility.
4. Para 1.1.2 -- total Other Liquid Assets may not exceed total Cash
   Equivalents.

**NOT primary-verified -- recorded as SECONDARY only:**

5. Broker practice reportedly passes the 50/50 requirement through to
   clients despite fact 1 above -- Zerodha states the clearing
   corporation requires the broker to fund any client cash shortfall;
   HDFC Securities charges daily interest on cash-component
   deficiency. This is broker-stated practice, not a SEBI/NSE
   confirmation that pass-through is itself required at client level
   (SEBI's own text says the opposite for the regulatory floor).
6. Reported April 2026 tightening: brokers required to hold 50% of
   F&O margin in cash, and RBI reportedly raising equity collateral
   haircuts to 40%. Source: Business Standard, 2026-03-31. **Not**
   checked against any SEBI, NSE, or RBI primary source.

Facts 5 and 6 are used only as clearly-labelled sensitivity cases in
the model below (the 40% haircut sensitivity, and the 50%
cash-fraction base case) -- never as the primary-verified regulatory
floor, which is facts 1-4.

## The pre-registered model

**Collateral:** a stylised NIFTY-tracking proxy. A fixed number of
units, bought once on 2024-01-04, whose value floats with the index
from there. Base case beta 1.0 (moves exactly with NIFTY); sensitivity
cases at beta 0.7 and 1.3. Base pot size Rs 10,00,000 at inception.

**Position:** 1 lot, **hedged (iron condor) version is the primary
case**. The naked version is a labelled sensitivity only -- its margin
uses the existing flat 10%-of-notional approximation (the same one in
`src/margin_return_analysis.py`), and no conclusion of this study may
rest on the naked case alone.

**Margin:** recomputed per trade from `outputs/backtest_trades_137.csv`
using that file's real `lot_size` column -- **not** a flat lot size,
and **not** reusing any rupee column from
`outputs/margin_return_analysis.csv`. Winged margin = (max spread
width x lot size) − net credit at entry.

**Haircut:** base case 9% (the SEBI floor, primary-verified fact 3).
Sensitivities at 20% and 40% -- the 40% figure rests on the unverified
secondary source (fact 6) and must be labelled as such everywhere it's
reported.

**Cash fraction:** base case 50% of margin held in cash (broker
practice, secondary fact 5). Sensitivity at 0% -- what the regulation
literally permits at the individual client level (primary-verified
fact 1).

**Available margin on day t:** A = C + min(U, C), where C is cash and
U is haircut-adjusted collateral value. The `min()` term is what
implements primary fact 4 (Other Liquid Assets can't exceed Cash
Equivalents) -- it's not an arbitrary conservatism, it's a direct
translation of that rule.

**Two breach types, always reported separately, never merged into one
number:**

- **Type 1, margin breach:** total margin requirement exceeds A.
- **Type 2, cash breach:** peak intraday mark-to-market loss exceeds C
  alone. This follows directly from primary fact 2 -- pledged shares
  cannot be used to meet an MTM call, only cash can.

**Peak MTM loss -- computed two ways, reported as a RANGE, never a
single number:**

- (a) Close-based: using `call_exit` / `put_exit` from the 137-trade
  baseline.
- (b) High-based upper bound: using `HghPric` for both short legs from
  `data/processed/nifty_expiry_day_chains.csv`.

**Caveat, pre-registered now:** the call's intraday high and the put's
intraday high do not necessarily happen at the same moment, so method
(b) is a conservative upper bound on a price path that may never have
actually existed on that day -- not a measured worst moment. It's a
ceiling, not an observation.

## Locked metrics

**Primary metric (nothing else may be used to judge the result):**
whether any Type 1 or Type 2 breach occurs across the 137 trades, and
the size in rupees of the worst shortfall of each type.

**Secondary metrics (reported, not selected on):** the minimum
coverage ratio across the sample; return on the cash actually posted.

## Rule departure: rupees, not points -- recorded and justified now

This study reports in **rupees**, breaking the project's standing
points-primary rule. **Justification:** collateral value, haircuts,
and cash buffers are inherently rupee quantities with no points
equivalent -- there's no way to express "how much cash you need to not
get margin-called" in points. **Mitigation:** every margin figure
still uses the real per-trade lot size from `backtest_trades_137.csv`,
never a flat assumption, so the rupee figures stay internally
consistent across all four lot-size regimes the same way the rest of
this project's rupee reporting does.

## The crash-day buying proposal, split into two claims

**Claim A (same-day margin relief): pre-registered as mechanically
FALSE.** Newly purchased shares settle T+1 and need further pledge
processing before they count as collateral -- they cannot meet a
same-day margin call or a same-day MTM call. This is documented here
as a mechanism, not something that needs a numerical test to disprove.

**Claim B (cost basis): testable.** Crash-day purchases are funded
from a ring-fenced cash pot held **separately** from the margin cash
C, so the two never get double-counted in the model. Recorded now,
before any computation: if this ring-fenced cash pot exists at all, it
could have been posted as margin instead of held in reserve -- the
proposal is partly self-cancelling, and the eventual write-up must say
so plainly rather than presenting "buy more on crash days" as a free
lunch.

## Crash threshold -- defined now, computed later

X = the 95th-percentile adverse open-to-close move in
`data/raw/nifty50_daily.csv` over **2016-01-01 to 2023-12-31** -- a
window deliberately outside the 2024+ period this study's 137 trades
come from, specifically so the threshold can't be tuned to the very
trades it's used to judge. X itself is **not computed in this entry**;
that happens in the analysis phase.

## Out-of-sample stress case

2024-06-04 is not an expiry day and is not one of the 137 baseline
trades. It will be run through this model and reported as a stress
scenario on its own, exactly as the rest of this project already
treats it (calendar-luck section, every-day extension) -- never pooled
into the 137-trade results.

## Pre-registered predictions (write down now, report honestly later)

1. Type 2 (cash) breaches will occur more often than Type 1 (margin)
   breaches.
2. At base-case parameters, at least one breach of some type occurs
   across the 137 trades.
3. The high-based peak-MTM measure produces at least twice as many
   breaches as the close-based measure.
4. Beta 1.3 produces more breaches than beta 0.7.
5. The 2024-06-04 stress scenario breaches at base-case parameters.

None of these are softened if they fail -- same discipline as every
other prediction set in this project (the strike-distance grid, the
pre-holiday hypothesis, the every-day extension's 4-of-5 failures).

## What this entry does not do

No margin figure, no breach count, no coverage ratio, no crash
threshold X, and no prediction pass/fail has been computed. This entry
and `config/pledged_collateral_experiment.json` are the only two files
touched in this task. `src/margin_return_analysis.py` and
`outputs/margin_return_analysis.csv` were not opened for editing --
their flat `LOT_SIZE = 65` is a known, already-documented
inconsistency, out of scope here, and this study deliberately
recomputes its own margin figures from `outputs/backtest_trades_137.csv`
instead of reusing that file's numbers, so the two don't need to agree.

## Text to paste into PROJECT_HANDOVER_V2.txt (not applied automatically)

The two secondary-source facts above (5 and 6) belong in the
handover's existing "Open questions -- claims to verify" and "Claims
verified from data vs claims taken from secondary sources" sections.
They are **not** applied to `PROJECT_HANDOVER_V2.txt` by this task --
paste the blocks below in by hand.

**Append to section 12, "OPEN QUESTIONS -- CLAIMS TO VERIFY," as new
items 5 and 6:**

```
5. BROKER PASS-THROUGH OF THE 50/50 CASH REQUIREMENT (pledged-
   collateral study, config/pledged_collateral_experiment.json): SEBI's
   Master Circular explicitly states its 50% cash-or-equivalent
   collateral requirement may NOT be applied at individual client
   level (Para 1.1.13.4, primary-verified). Broker practice reportedly
   passes this through to clients anyway -- Zerodha states the
   clearing corporation requires the broker to fund any client cash
   shortfall, and HDFC Securities charges daily interest on
   cash-component deficiency. This is SECONDARY broker-practice
   information, not a SEBI/NSE confirmation that client-level
   pass-through is itself regulatory-required (SEBI's own text says
   the opposite at the client level). TO DO: verify whether broker
   pass-through is contractual/discretionary or is itself mandated by
   NSE/NSCCL rules, from a primary source.

6. REPORTED APRIL 2026 MARGIN TIGHTENING (pledged-collateral study,
   config/pledged_collateral_experiment.json): Business Standard
   (2026-03-31) reportedly stated brokers would be required to hold
   50% of F&O margin in cash and that RBI was raising equity
   collateral haircuts to 40%. NOT verified against any SEBI, NSE, or
   RBI primary source. TO DO: check for the actual SEBI/NSE circular
   or RBI notification, if any, that this reporting refers to.
```

**Append to section 13, "CLAIMS VERIFIED FROM DATA VS CLAIMS TAKEN
FROM SECONDARY SOURCES," under "TAKEN FROM SECONDARY SOURCES, NOT YET
CHECKED AGAINST A PRIMARY SOURCE":**

```
  - Broker pass-through of the 50% cash-collateral requirement to
    individual clients (Zerodha, HDFC Securities statements), despite
    SEBI's own text saying this requirement does not apply at client
    level (pledged-collateral study, open question 5).
  - The reported April 2026 tightening -- 50% cash requirement
    enforcement and an RBI haircut increase to 40% -- per Business
    Standard, 2026-03-31 (pledged-collateral study, open question 6).
```

(Section 13's "VERIFIED FROM THIS PROJECT'S OWN DATA" and "CITED BUT
NOT INDEPENDENTLY FETCHED" buckets are unaffected -- the four
primary-verified SEBI facts this study relies on are a *new kind* of
verification this project hasn't used before, a directly cited and
quoted regulatory primary source rather than the project's own
re-derivable data. Whether that deserves its own bucket in section 13
is your call, not something this entry decides for you.)
