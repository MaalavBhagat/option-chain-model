# Weekly strangle study — Step 5: PRE-REGISTRATION

**Status: LOCKED once committed.** Every rule below is fixed before any P&L, payoff or
outcome has been computed for any period (confirmed in Steps 1–4). Any later change
is made only as a dated, numbered amendment at the bottom of this file, with the reason,
and is reported alongside the original result. Nothing is deleted.

Authority: technical design by Claude (flagged "[C]"), finance and strategy calls by
Goggy (flagged "[G]"). Goggy has final say on strategy questions.

---

## 1. The question

Does selling deep out-of-the-money NIFTY weekly options, the way the real account did
in 2026, make money after all costs, and how badly can it fail?

## 2. Data and sample

- Option prices: NSE F&O bhavcopy, end-of-day only.
  - 2019-02-14 → 2023-12-29: legacy format (`data/processed/nifty_options_2019_2023.csv`)
  - 2024-01-01 → 2026-11-09: UDiFF format (`data/raw/BhavCopy_*.zip`)
- Spot: bhavcopy `UndrlygPric` (2024+), yfinance `^NSEI` close (2019–2023). VIX: NSE file.
- **In-sample (IS): weekly expiries 2019-02-14 → 2023-12-28.** Contains the COVID crash and
  2022, i.e. 23 of the 26 stress weeks with data.
- **Out-of-sample (OOS): weekly expiries 2024-01-04 → 2026-11-09.** Calm period, 3 stress
  weeks, and the period of the real account.
- **No parameter is chosen from results.** Every primary value below is fixed now. Grid
  values are reported as sensitivity, for both IS and OOS, and are never "selected". [C]
  (Reason: the earlier strike-grid study showed the in-sample winner ranked 6th out-of-sample.)

### Calendar rules [C]
- Trading days = days with a bhavcopy, **excluding Muhurat sessions** (2019-10-27,
  2020-11-14, 2021-11-04, 2022-10-24, 2023-11-12, 2024-11-01, 2025-10-21, 2026-11-08).
  Budget-day Saturday sessions count as normal trading days.
- Expiry calendar is data-derived. If a contract's labelled expiry date was a holiday
  (e.g. 2023-06-29 → traded to 2023-06-28), it settles on the actual last trading day
  before it, at that day's spot close.
- Any trade whose entry day or expiry day falls on a day with no option file
  (2021-03-30) is **skipped and logged**.

## 3. Common trade mechanics (all variants)

- **One trade per weekly expiry**: sell 1 call + 1 put of that week's expiry.
- **Entry**: at the entry day's **close** (`ClsPric` / legacy `CLOSE`).
  Primary entry day: **T-1** (1 trading day before expiry). Sensitivity: T-2, T-4. [C, from
  Step 4: most unambiguous real legs matched T-1]
- **Eligible strike**: traded on the entry day (volume > 0) with close ≥ 0.05.
- **Exit**: hold to expiry unless the variant says otherwise.
- **Settlement**: cash-settled at the expiry day's NIFTY spot close.
  Short call pays max(0, S_T − K); short put pays max(0, K − S_T).
  S_T = spot close on expiry day, K = strike.
- **Lot size**: per contract, from the bhavcopy (2024+) or
  `config/weekly_strangle/lot_size_pre2024.csv` (2019–2023, by contract, not by trade date).
  If lot size changes during a trade, **units stay constant**.
- **Primary unit: points per unit (per 1 share-equivalent).** Rupees are reported at
  1, 10 and 100 lots per leg. [G: 1 / 10 / 100]

### Strike selection, primary (V1) [C, from Step 4 real-trade profile]
- **Call target: 7% OTM. Put target: 10% OTM**, from entry-day spot close.
  (Real legs: call median 7.05% at T-1, put median 10.81% at T-1.)
- Pick the eligible strike whose % OTM is **closest to the target**, but never more than
  **2.0 percentage points closer to spot** than the target (calls ≥ 5%, puts ≥ 8%).
  Ties go to the further OTM strike.
- **If no eligible strike exists, skip that leg** (the week becomes one-sided, as in 7 of
  the real weeks). Report the number of skipped legs per year.

## 4. Costs

### Brokerage scenarios [G]
| Code | Brokerage | Role |
|---|---|---|
| A | ₹30 per lot per executed order | The real broker, implied by the GST lines |
| B | ₹20 per lot per executed order | Cheaper per-lot broker |
| C | ₹0 | Best case (statutory charges still apply) |
| D | ₹20 per executed order | Reference only (typical discount broker) [C] |

- An "executed order" is an entry sell, a stop/early buy-back, or a wing buy. Orders above
  the NSE quantity-freeze limit are split (limits per `charge_rates.csv`).
- **Expiry settlement is not an order**: no brokerage, no slippage. [C, flagged]

### Statutory charges [C]
- Every rate comes from `config/weekly_strangle/charge_rates.csv` **for the trade date**:
  STT on sale, STT on in-the-money settlement (if it applies to the short side, per Step 2),
  NSE transaction charge, SEBI fee, stamp duty (buy side), GST on brokerage + transaction +
  SEBI fee.
- Rounding: exact rates, no per-contract-note rounding (the rounding found in Step 2 is a
  broker effect and is noted as a known underestimate of ~₹0.5 per leg).

### Slippage [C]
- Every executed order fills **s ticks worse** than the close: sell at close − s × 0.05,
  buy at close + s × 0.05.
- **Primary s = 1.** Sensitivity: s = 2 and s = 4, always reported next to s = 1.
- If a sell price after slippage would be < 0.05, the leg is skipped.

## 5. Variants (exactly six, no combinations)

| ID | Variant | Primary value | Sensitivity |
|---|---|---|---|
| V1 | Baseline: % OTM strikes, hold to expiry | CE 7% / PE 10% | — |
| V2 | Delta strikes | \|delta\| = 0.04, accept 0.02–0.06, else skip leg | 0.03, 0.05 |
| V3 | Stop-loss | 3× sale price | 2×, 5× |
| V4 | Iron condor | wings 300 points beyond each short strike | 200, 500 |
| V5 | VIX filter (skip week) | entry-day VIX close > 18 → skip | 15, 20 |
| V6 | Event filter (skip week) [G's variant] | any listed event in [entry day, expiry day] → skip | — |

Every variant is also run at T-1 (primary), T-2 and T-4, under brokerage A/B/C/D and
slippage s = 1/2/4.

### V2 delta [C]
- Implied volatility from each eligible strike's entry close, Black-Scholes, r = 0, no
  dividends, time = calendar days from entry close to expiry close ÷ 365.
- Strikes whose IV cannot be solved are dropped. Flag: r = 0 changes delta negligibly
  at 1–6 days.

### V3 stop-loss (end-of-day approximation) [C]
- Checked on each trading day **after** the entry day, up to and including expiry day,
  only on days the contract traded.
- Trigger: that day's HIGH ≥ m × sale price (sale price = entry close before slippage).
- Fill: max(m × sale price, that day's OPEN) + s ticks. (Gap opens fill at the open.)
- Flag: EOD data cannot show whether the high came before or after a recovery; this
  treats every touch as a fill. For T-1 entries only the expiry day is checked.

### V4 iron condor [C]
- Buy a call W points above the short call and a put W points below the short put, same
  expiry, at entry close + s ticks, minimum 0.05 before slippage.
- If no eligible wing exists within W ± 100 points, **that side (short + wing) is skipped**
  for that week.

### V5 VIX filter
- Uses the NSE India VIX close on the entry day (known at entry).

### V6 event filter [G]
- Events: `config/event_calendar.csv` + `config/weekly_strangle/event_calendar_2019_2023.csv`
  + the Aug–Nov 2026 extension made in this step. VERIFIED and SECONDARY rows both count.
- US FOMC dates are moved to the **next Indian trading day** (announced after the Indian
  close).
- Only published, scheduled calendars are used. No date is added because of what the
  market did.

## 6. Hypotheses and predictions (recorded before any result)

- **H1 — edge (primary test).** V1, T-1, brokerage C, s = 1: mean weekly net P&L > 0,
  judged by the lower bound of a 95% block-bootstrap confidence interval (blocks of 4 weeks,
  10,000 resamples, seed 20261117), **in both IS and OOS**.
  - "Demonstrated edge" = H1 holds **and** still holds at s = 2.
  - Otherwise the verdict is "no demonstrated edge after costs".
- **H2 — Goggy's prediction.** V6 has positive total net P&L in both IS and OOS, and a
  smaller worst week than V1. Scored separately under brokerage A, B and C.
- **H3 — Claude's prediction.** (a) V6's worst IS week is within 20% of V1's worst IS week
  (the filter does not avoid the 2020 losses). (b) No variant has positive total net P&L
  under brokerage A in either period.
- **H4 — risk control.** V4 has a lower 99% CVaR than V1 in both periods, and lower total
  net P&L than V1 in OOS.

Every hypothesis is reported as HELD / FAILED with the numbers, without softening.

## 7. Metrics (for every variant × entry day × brokerage × slippage, IS and OOS separately)

- Total and mean weekly net P&L (points per unit; ₹ at 1/10/100 lots)
- Win rate, average win, average loss, win/loss ratio
- Worst week, worst 3 consecutive weeks
- Max drawdown and time to recover
- 95% and 99% CVaR of weekly P&L
- Weeks where a short strike was breached at expiry
- Weeks with a loss > **₹5,000** at 1/10/100 lots [G: max acceptable weekly loss ₹5k]
- Results with the worst 1, 2 and 3 weeks removed
- Skipped legs and skipped weeks, by reason
- Secondary (method fixed in a later amendment before computing): return on margin,
  Sharpe, Sortino, comparison with buy-and-hold NIFTY (price index, dividends excluded).
- Stress-period table: Mar–May 2020, Feb–Mar 2022, Jun 2024, Apr 2025, Oct–Nov 2026.

## 8. Correctness gates (must pass before any result is shown)

1. **Cost model**: reproduces Step 2's listed-charge reconciliation within ₹1.
2. **Settlement replay**: the 54 real NIFTY legs held to expiry, valued with the engine's
   settlement function, give the same expiry outcome as the statement (all expired with
   zero intrinsic value). Only the settlement function is checked; no strategy is run.
3. **No look-ahead**: strike selection, filters and entry price receive only data dated
   on or before the entry day (enforced in code and covered by a unit test).
4. **Hand check**: 3 random trades per period printed with every input and computed
   field, checked by hand.

## 9. Known limitations (stated in advance)

- End-of-day data only: entry at close; no bid/ask; stop-loss is approximate.
- Close prices of deep-OTM options may sit at the bid or the ask; slippage is assumed,
  not measured.
- Margin is estimated, not taken from NSE SPAN files (unless a later amendment adds them).
- 2016–2018 stress weeks have no option data; there were no NIFTY weeklies then.
- The real account's entry days are inferred (37 of 59 legs ambiguous or unmatched).

## 10. Parameters (machine-readable copy in `config/weekly_strangle/prereg_params.json`)

```yaml
is_expiries: [2019-02-14, 2023-12-28]
oos_expiries: [2024-01-04, 2026-11-09]
entry_day: {primary: 1, sensitivity: [2, 4]}         # trading days before expiry
strike_pct_otm: {call: 0.07, put: 0.10, max_closer_pp: 0.02}
eligible: {min_volume_contracts: 1, min_close: 0.05}
slippage_ticks: {primary: 1, sensitivity: [2, 4]}
tick: 0.05
brokerage:
  A: {per: lot_order, rupees: 30}
  B: {per: lot_order, rupees: 20}
  C: {per: none, rupees: 0}
  D: {per: order, rupees: 20, role: reference}
lots: [1, 10, 100]
max_weekly_loss_rupees: 5000
variants:
  V1: {}
  V2: {abs_delta: 0.04, accept: [0.02, 0.06], sensitivity: [0.03, 0.05], r: 0.0}
  V3: {stop_multiple: 3, sensitivity: [2, 5]}
  V4: {wing_points: 300, tolerance_points: 100, sensitivity: [200, 500]}
  V5: {vix_skip_above: 18, sensitivity: [15, 20]}
  V6: {fomc_shift_next_indian_day: true, include_secondary: true}
bootstrap: {block_weeks: 4, resamples: 10000, seed: 20261117, ci: 0.95}
muhurat_excluded: [2019-10-27, 2020-11-14, 2021-11-04, 2022-10-24, 2023-11-12, 2024-11-01, 2025-10-21, 2026-11-08]
```

---

## Amendments

### Amendment 1 — 2026-11-17, adopted before any outcome was computed

- **Decision:** Goggy adopted all four proposed fixes.
- **Evidence and rejected alternatives:** `docs/weekly_strangle/04a_amendment_1.md`.
- **Parameters:** `config/weekly_strangle/prereg_params_amendment_1.json` replaces
  `prereg_params.json` for all runs. The original JSON is kept unchanged.
- **Original wording:** everything above stays as locked in commit f41f1f4. Where it conflicts with this
  amendment, this amendment governs.
- **Not computed:** no P&L, payoff or outcome was needed to find these issues.

**1A. FOMC date shift (amends §5 V6, line 136) [C, TECHNICAL]**
- The shift applies **only** to FOMC rows that store the US date:
  `config/weekly_strangle/event_calendar_2019_2023.csv` and
  `config/weekly_strangle/event_calendar_2026_extension.csv`.
- The 21 FOMC rows of `config/event_calendar.csv` already store the Indian date and are used **as is**.
- "Next Indian trading day" = the first date strictly after the US date that is a trading day under §2's
  calendar rules (it has a bhavcopy and is not a Muhurat session).
  - Examples: Sunday 2020-03-15 → 2020-03-16; 2026-09-16 → 2026-09-17.

**1B. Event-calendar provenance (amends §5 V6, lines 134–135) [C, TECHNICAL]**
- `config/event_calendar.csv` has no status column. Its rows are treated as follows:
  - FOMC rows (federalreserve.gov) and the one row citing rbi.org.in: VERIFIED.
  - Every other row: SECONDARY.
- All rows still count for V6 (`include_secondary: true`). The set of V6 dates is unchanged.
- RBI's own Monetary Policy page confirms two dates sourced from 5paisa in that file:
  - 2026-06-05 (Governor's Statement, prid=62864).
  - 2026-08-05 (Governor's Statement, prid=63288).

**1C. STT on exercise (replaces the conditional in §4 "Statutory charges", line 84) [C, TECHNICAL]**
- STT on exercise is payable **only by the purchaser** (`charge_rates.csv` rows `stt_option_exercised`:
  0.125% to 2026-03-31, 0.15% from 2026-04-01). **Short legs never pay it.**
- A **long V4 wing** that settles in the money pays it on intrinsic value × units, at the rate in force
  on the expiry date.
- A wing that expires worthless pays nothing at expiry.

**1D. V6 event types (amends §5 V6 and the V6 row of the §5 table) [G, STRATEGY]**
- In both IS and OOS, V6 counts only these event types: `US Fed FOMC`, `RBI MPC`, `Union Budget` and
  `Lok Sabha Election Result`.
- `State Election Result` rows (5 in `config/event_calendar.csv`, 0 in the 2019–2023 file) are
  **ignored**, so the filter is the same rule in both periods.

### Amendment 2 — 2026-11-17, adopted before any outcome was computed

- **What it records:** the engine decisions D1–D12 taken in Step 6 / 6b.
  - D1–D9 as in `config/weekly_strangle/step6_decisions.json`. D1–D8 were committed in 6281ab4; D9 in
    69ef47d.
  - D10–D12 are new in Step 6b.
- **Who chose:**
  - D1–D8: Claude Code recommended them; Goggy accepted them as a set ("Take all recommended").
  - D9: Goggy chose "add SEBI fee"; Claude Code chose the notional basis.
  - D10–D12: Goggy chose them (Step 6b instruction).
- **Parameters:** `config/weekly_strangle/prereg_params_amendment_2.json` replaces
  `prereg_params_amendment_1.json` for all runs. Both earlier JSON files are kept unchanged.
- **Precedence:** where this amendment conflicts with the text above, this amendment governs.
- **Not computed:** no P&L, payoff, outcome or backtest result was computed to take these decisions.

**D1 — Gate 1 definition. CHANGES §8 Gate 1. [Claude Code recommended; Goggy accepted; TECHNICAL]**
- **Question:** §8.1 asks the cost model to reproduce Step 2's listed-charge reconciliation within ₹1. But
  §4 requires exact rates, and Step 2 showed exact rates do not match the statement's lines (STT ₹42.48 vs
  ₹73.00).
- **Choice:** Gate 1 checks that `costs.py` reproduces Step 2's "predicted from rates" column within ₹1 for
  STT, TOC NSE (transaction charge + IPFT) and TOC BSE.
  - The gap to the statement's listed lines is reported as a known underestimate, not fixed.
  - Clearing and GST are not scored.

**D2 — Charge rates before 2024. [Claude Code recommended; Goggy accepted; TECHNICAL]**
- **Question:** `charge_rates.csv` has no STT, transaction-charge, IPFT or SEBI-fee rows before 2024-01-01.
- **Choice:** a new file, `config/weekly_strangle/charge_rates_pre2024.csv`, from primary sources where
  found, with a status on each row.
  - Sources: NSE/FATAX/56235, NSE/FATAX/41919, NSE/FA/46730, NSE/FA/56129, and the SEBI Gazettes via
    NSE/FA/40632 and NSE/FA/44514.

**D3 — Which NSE transaction-charge row. [Claude Code recommended; Goggy accepted; TECHNICAL]**
- **Question:** two rows cover 2024-01-01 to 2024-09-30: the member slab (0.050 to 0.030%) and the client
  rate (0.0495%).
- **Choice:** the `client_typical` row (the first incremental slab, the rate clients are typically billed)
  where one exists for the date; otherwise the `statutory` row (true-to-label from 2024-10-01).

**D4 — IPFT, clearing and the GST base. [Claude Code recommended; Goggy accepted; TECHNICAL]**
- **Question:** §4 does not mention IPFT or clearing charges, and the GST base is not fully specified.
- **Choice:**
  - IPFT is charged.
  - Clearing charges are not modelled (no rate source).
  - GST = 18% of (brokerage + exchange transaction charge + SEBI fee), without IPFT.

**D5 — Missing spot. [Claude Code recommended; Goggy accepted; TECHNICAL]**
- **Question:** 2019-02-13 and 2019-03-29 have an option file but no spot price. §2 only covers a missing
  option file.
- **Choice:** skip the week and log the reason "missing spot".

**D6 — V4 wing choice. [Claude Code recommended; Goggy accepted; TECHNICAL]**
- **Question:** §5 does not say which wing to buy when several are within W ± 100 points, or whether the
  wing must have traded.
- **Choice:** the strike nearest to exactly W points beyond the short strike; ties go further out.
  Eligibility is the same as for short legs (volume ≥ 1, close ≥ 0.05).

**D7 — V2 tie-break. [Claude Code recommended; Goggy accepted; TECHNICAL]**
- **Question:** §5 does not say which strike wins when two are equally close to the target |delta|.
- **Choice:** the further-OTM strike, as in V1.

**D8 — Freeze limits before 2023-04-03. [Claude Code recommended; Goggy accepted; TECHNICAL]**
- **Question:** no freeze-limit row exists before 2023-04-03.
- **Choice:** to be handled in the D2 file. No primary source was found, so the row stayed NOT_AVAILABLE.
  **Superseded by D11.**

**D9 — Charges at an in-the-money settlement. [Goggy chose "add SEBI fee"; Claude Code chose the notional basis; TECHNICAL]**
- **Question:** §4 does not say whether the SEBI fee or an exchange charge applies when a leg settles in
  the money.
- **Choice:**
  - A leg that settles in the money pays the SEBI turnover fee on its notional value, whether it is short
    (assigned) or long (exercised), plus 18% GST on that fee.
  - A long leg also pays STT on exercise (Amendment 1C).
  - No brokerage, no slippage and no exchange transaction charge apply at settlement.
- **Notional basis = settlement spot × units. This is a conservative assumption.**
  - The SEBI Gazette (SEBI/L.A.D.-N.R.O./G.N./2019/03, Schedule V Part B, Explanation (B)) adds the "notional
    value of option contracts exercised or assigned" to a stock broker's turnover. It does not define
    notional value.
  - There is **no primary source** that the fee is passed through to the client, or for spot × units as the
    basis.

**D10 — Stamp duty before 2020-07-01. [Goggy chose; TECHNICAL; status APPROXIMATION]**
- **Question:** before 2020-07-01 stamp duty was set by each state, so there is no single rate.
- **Choice:** 0.003% of buy-side premium, the national rate in force from 2020-07-01.
  - It affects V3 buy-backs and V4 wing buys before that date.

**D11 — NIFTY freeze limit before 2023-04-03. [Goggy chose; TECHNICAL; status SECONDARY]**
- **Question:** no primary source was read for the freeze limit before 2023-04-03.
- **Choice:** 1,800 units, for brokerage D only (the only cost that depends on the number of orders).
  - It is chosen as the conservative value: a lower limit gives more orders and more brokerage.

**D12 — NSE transaction charge, Jan–Mar 2024. [Goggy chose; TECHNICAL]**
- **Question:** the existing `charge_rates.csv` row applies 0.0495% from 2024-01-01. A secondary source (a
  broker bulletin) says the cut from 0.050% to 0.0495% took effect only on 2024-04-01.
- **Choice:** keep the existing `charge_rates.csv` row. The secondary source is noted here.
  - The impact is 0.0005% of premium on trades entered 2024-01-01 to 2024-03-31.

### Amendment 3 — 2026-11-17, adopted before any outcome was computed

- **What it fixes:** the secondary-metric methods left open in §7 (set by Goggy), plus 12 method choices for
  §6/§7 that Claude Code recommended and Goggy accepted ("Take all, then run").
- **Parameters:** `config/weekly_strangle/prereg_params_amendment_3.json` replaces
  `prereg_params_amendment_2.json` for all runs. The earlier JSON files are kept unchanged.
- **Not computed:** no P&L, payoff, outcome or backtest result had been computed when this was adopted.

**3A. Secondary-metric methods [Goggy]**
- **Margin per trade** (an approximation; no NSE SPAN files):
  - **Short legs without wings** (one- or two-sided): m × entry spot × units of ONE side, the side with more
    units. m = 0.10 primary; sensitivity 0.07 and 0.13.
  - **V4 iron condor:**
    - margin = max over sides of (wing width × units) − total net credit received, floored at 0;
    - a side with no wing uses the naked rule for that side.
- **Return on margin:** per week = net P&L / margin. Annualised = mean weekly × 52.
- **Sharpe and Sortino:**
  - Sharpe = mean / std of weekly return on margin × √52.
  - Sortino uses the downside deviation instead of the std.
  - Risk-free rate = 0. Skipped weeks count as 0 return.
- **Benchmark:** NIFTY price index buy-and-hold.
  - Weekly returns run from expiry close to expiry close over the same expiries.
  - Dividends are excluded, which understates the benchmark.

**3B. Method choices for §6 and §7 [Claude Code recommended; Goggy accepted]**
1. **H2 and H4 settings:** T-1, s = 1, primary values, points per unit.
   - H2 is scored separately under brokerage A, B and C. "A smaller worst week than V1" must hold in both IS
     and OOS.
   - H4 uses brokerage C (the H1 setting).
2. **H3a and H3b settings:**
   - **H3a:** brokerage C, T-1, s = 1, points per unit. HELD if |V6 worst IS week − V1 worst IS week| ≤ 0.20 ×
     |V1 worst IS week|.
   - **H3b:** all six variants at primary values, T-1, s = 1, brokerage A. HELD only if no variant has a
     positive total in IS and none has one in OOS.
3. **H1 bootstrap:**
   - Moving-block bootstrap: overlapping blocks of 4 consecutive weeks with uniformly drawn starts, joined and
     cut to n weeks. 10,000 resamples, numpy `default_rng(20261117)`.
   - The statistic is the mean weekly net points per unit. The bound is the 2.5th percentile of the resampled
     means.
   - Run separately for IS and OOS. "Demonstrated edge" also requires the same test to pass at s = 2.
4. **Skipped weeks** (V5 or V6 skips, or every leg skipped):
   - They count as 0 in totals, means, CVaR, drawdown, worst runs and the bootstrap.
   - Win rate, average win and average loss are computed over traded weeks only. A win is net > 0; a loss is
     net < 0.
5. **CVaR c:** the mean of the worst ⌈(1 − c) × n⌉ weekly results, reported as P&L (a negative number).
   - "Lower CVaR" (H4) means a smaller tail loss, i.e. a less negative number.
6. **Sharpe and Sortino formulas:**
   - Sharpe uses the sample standard deviation (n − 1 divisor).
   - Sortino's downside deviation = √(mean of min(r, 0)²) over all weeks.
7. **Drawdown:** measured on cumulative rupees at 10 lots per leg, separately for IS and OOS.
   - % of margin = max drawdown ÷ the median weekly margin (m = 0.10) over traded weeks.
   - Weeks to recover = expiries from the trough to the next new high, or "not recovered".
8. **Worst runs and breaches:**
   - Worst 3-week run = the worst sum of 3 consecutive expiries, with skipped weeks counting as 0.
   - Strike breach = a short leg whose strike is beyond the expiry spot, counted even if V3 stopped it out
     earlier.
9. **Brokerage D:**
   - Its points per unit are reported at 1, 10 and 100 lots, and its other metrics at 10 lots.
   - Return on margin uses rupees at 10 lots for every brokerage.
10. **Stress-period membership:** a week belongs to a stress period if its expiry date falls in the listed
    months.
11. **EXPLORATORY real-account comparison sizing:**
    - Each V1 leg (T-1, brokerage A, s = 1) is sized at the real account's total units on that side for that
      expiry. A side the account did not trade gets 0 units.
12. **EXPLORATORY comparison figure:** the statement's per-leg gross from its P&L column, summed by expiry,
    for the same expiries.
    - Only symbol and amount rows are read; nothing from the header area.
