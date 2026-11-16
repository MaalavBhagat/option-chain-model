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

(none)
