# Weekly strangle study — Amendment 1: evidence and rationale

**Status: ADOPTED 2026-11-17, before any outcome was computed.**
- Every **Proposed** fix below is adopted: Issues 1, 2 and 3, and extra finding A. The alternatives are
  kept for the record only.
- The binding text is "Amendment 1" under "## Amendments" in `docs/weekly_strangle/04_preregistration.md`.
  The rest of that file (locked in commit f41f1f4) is unchanged.
- The amended parameters are in `config/weekly_strangle/prereg_params_amendment_1.json`.
  `prereg_params.json` is unchanged.

**No P&L, payoff, outcome or backtest result was computed to find or check any issue below.**
- Only these were read: the pre-registration text, the event-calendar CSVs, `charge_rates.csv`, the Step 2
  doc, and RBI's and the Fed's own web pages.
- No option price, spot price or VIX value was read.

There are three issues, plus one extra finding (A) of the same kind, raised for a decision.

---

## Issue 1 — FOMC dates would be shifted twice

**1. Text concerned.** Section 5, "### V6 event filter [G]", line 136:
> "- US FOMC dates are moved to the **next Indian trading day** (announced after the Indian close)."

The JSON copy carries the same rule as `"V6": {"fomc_shift_next_indian_day": true}`.

**2. What is wrong, with evidence.** The three calendar files V6 uses do not store FOMC dates the same way.
- **`config/event_calendar.csv`: already shifted.**
  - All 21 `US Fed FOMC` rows (lines 28–48) store the next Indian trading day, not the US date.
  - For example, line 29 is `2024-03-21`, described as "announced Mar 20 2024 ET (flagged date is next
    India trading session)".
  - Line 28 is `2024-02-01` for the Jan 31 2024 decision.
- **`config/weekly_strangle/event_calendar_2019_2023.csv`** (42 FOMC rows) and
  **`event_calendar_2026_extension.csv`** (2 FOMC rows): these store the US date.
  - For example, `2019-01-30` is described as "US date, released after the Indian close".
- **Effect:** a single shift rule applied to all three files moves the 21 rows in `event_calendar.csv` one
  trading day too late, for example 2024-03-21 becomes 2024-03-22.
- With a T-1 entry, a one-day error can move an event out of the [entry day, expiry day] window or into
  the wrong week.
- The rule also never says what "next Indian trading day" means when the US date falls on a weekend.
  For example, the unscheduled FOMC cut of Sunday 2020-03-15 is in the 2019–2023 file.

**3. Fixes.**
- **Proposed:** apply the shift only to rows that store the US date, which are the rows of
  `event_calendar_2019_2023.csv` and `event_calendar_2026_extension.csv`.
  - Use the 21 FOMC rows of `config/event_calendar.csv` as they are.
  - "Next Indian trading day" = the first date strictly after the US date that is a trading day under
    section 2's calendar rules (it has a bhavcopy and is not a Muhurat session).
  - So 2020-03-15 (Sunday) maps to 2020-03-16, and 2026-09-16 maps to 2026-09-17.
- **Alternative:** build one new combined file, `config/weekly_strangle/event_calendar_v6.csv`, with a
  `date_basis` column (`US` or `IN`) and a computed `india_date` column.
  - V6 would read only that file.
  - No existing file would be edited.

**4. Type: TECHNICAL** (a fact about how each file stores its dates). It does not change which events count.

**5. No P&L or outcome was needed.** This was found by reading the description column of the calendar CSVs.

---

## Issue 2 — V6 relies on a status column that `config/event_calendar.csv` doesn't have

**1. Text concerned.** Section 5, "### V6 event filter [G]", lines 134–135:
> "- Events: `config/event_calendar.csv` + `config/weekly_strangle/event_calendar_2019_2023.csv`
> + the Aug–Nov 2026 extension made in this step. VERIFIED and SECONDARY rows both count."

The JSON copy carries `"include_secondary": true`.

**2. What is wrong, with evidence.**
- **No status column:** `config/event_calendar.csv` has only 4 columns (`date,event_type,description,source_url`).
  So "VERIFIED and SECONDARY" can't be read for its 47 rows.
- **Most of its non-FOMC rows cite secondary sources:**
  - 25 of its 26 non-FOMC rows cite news or broker sites: business-standard.com (10), indiatvnews.com (3),
    newsonair.gov.in (3), 5paisa.com (2), share.market (2), businesstoday.in (2), deccanherald.com,
    aljazeera.com and sundayguardianlive.com.
  - 1 row cites rbi.org.in.
  - The 21 FOMC rows cite the Fed's calendar page.
- **Two RBI rows have only a secondary source:** line 26 (`2026-06-05`) and line 27 (`2026-08-05`) both cite
  `https://www.5paisa.com/blog/rbi-mpc-meeting-schedule`.
  - RBI's own Monetary Policy page (rbi.org.in/Scripts/Annualpolicy.aspx, read on 2026-11-17) lists
    "Governor's Statement: June 05, 2026" (prid=62864) and "Governor's Statement: August 5, 2026"
    (prid=63288).
  - So both dates are correct; only their sourcing is secondary.
- **Earlier, wrong wording:** the Step 5 report said 2026-08-05 was the only secondary-sourced row in this
  file. That was too narrow, as the counts above show.

**3. Fixes.**
- **Proposed:** state in the amendment that every row of `config/event_calendar.csv` counts as SECONDARY,
  except the FOMC rows (they cite federalreserve.gov) and the RBI row citing rbi.org.in.
  - Every row still counts for V6, as `include_secondary: true` already says.
  - Record in the amendment that RBI's primary page confirms 2026-06-05 (prid=62864) and 2026-08-05
    (prid=63288).
  - No file is edited, and the set of V6 dates stays the same.
- **Alternative:** create a new file, `config/weekly_strangle/event_calendar_2024_2026_verified.csv`, holding
  the same 47 events with a primary-source URL and a status for each.
  - Sources would be RBI, the Fed, PIB and ECI; a row with no primary source would stay SECONDARY.
  - V6 would read it instead of `config/event_calendar.csv`.
  - This takes more work. It changes provenance only, unless a date turns out to be wrong; any wrong date
    would be reported before use.

**4. Type: TECHNICAL** (provenance of the data). Counting SECONDARY rows is a strategy choice Goggy has
already made, and neither fix changes it.

**5. No P&L or outcome was needed.** This was found by reading the CSV header and the `source_url` column,
plus RBI's policy page.

---

## Issue 3 — STT on settlement is worded conditionally, and the iron-condor wings are missing from it

**1. Text concerned.** Section 4, "### Statutory charges [C]", line 84:
> "STT on sale, STT on in-the-money settlement (if it applies to the short side, per Step 2),"

**2. What is wrong, with evidence.**
- **Step 2 already settled the condition.** `config/weekly_strangle/charge_rates.csv` lines 5–6 cover
  `stt_option_exercised`:
  - 0.125% to 2026-03-31, then 0.15% from 2026-04-01.
  - `side` = `buy (purchaser/holder only)`, with the note "a short (written) option assigned ITM does not
    pay this STT".
  - `docs/weekly_strangle/01_market_rules_and_costs.md` §b (lines 54–60) says the same, citing CBDT Section 98
    entry 4(b): "Purchaser".
  - So for short legs it is ₹0, and the "if" should not be left to code.
- **V4 has long legs.** V4 (iron condor) **buys** wings and holds them to expiry, and nothing in the text
  covers them.
  - A wing that finishes in the money is an exercised long option, so it **does** pay this STT on its
    intrinsic value.
  - The current wording mentions only "the short side", so an engine could leave out a real cost on V4's
    long wings.

**3. Fixes.**
- **Proposed:** replace the conditional with the following.
  - "STT on exercise is payable only by the purchaser (`charge_rates.csv` rows `stt_option_exercised`).
    Short legs never pay it."
  - "A long wing (V4) that settles in the money pays it on intrinsic value × units, at the rate in force
    on the expiry date."
  - "A wing that expires worthless pays nothing at expiry."
- **Alternative:** charge STT on exercise to nobody, and list it under section 9 (Known limitations) as an
  understatement of V4's costs that applies only in weeks where a wing ends in the money.

**4. Type: TECHNICAL** (a statute fact, already established in Step 2).

**5. No P&L or outcome was needed.** This was found by reading `charge_rates.csv`, the Step 2 doc and the
pre-registration text. It was not checked whether any wing would actually finish in the money.

---

## Extra finding A (raised for a decision, not one of the three) — state elections are in the OOS calendar only

**1. Text concerned.** Section 5, "### V6 event filter [G]", lines 134–135 (same text as Issue 2).
> "any listed event in [entry day, expiry day] → skip" (section 5 table, V6 row).

**2. What is wrong, with evidence.**
- `config/event_calendar.csv` has 5 `State Election Result` rows (lines 7–11): 2024-10-08, 2024-11-23,
  2025-02-08, 2025-11-14 and 2026-05-04.
- `config/weekly_strangle/event_calendar_2019_2023.csv` has **0** of them (Step 4 Part D listed only FOMC,
  RBI MPC, Union Budget and the Lok Sabha result).
- So in OOS V6 skips state-election weeks, but in IS it doesn't. The filter is not the same rule in the two
  periods, which weakens H2's comparison across periods.

**3. Fixes.**
- **Proposed:** V6 counts only these event types in both periods: `US Fed FOMC`, `RBI MPC`, `Union Budget`
  and `Lok Sabha Election Result`. `State Election Result` rows are ignored.
- **Alternative:** add the 2019–2023 state-election result dates in a new file, with ECI or PIB primary
  sources, so state elections count in both periods.

**4. Type: STRATEGY** (which events V6 avoids). This is Goggy's call.

**5. No P&L or outcome was needed.** This was found by counting `event_type` values in the two CSVs.

---

## Adoption

- Decision (Goggy, 2026-11-17): "Adopt all proposed".
- **Pre-registration:** the amendment text was added under "## Amendments", replacing the "(none)"
  placeholder. No other line was changed.
- **JSON:** `prereg_params_amendment_1.json` is a full parameter set: the original keys plus the changes
  from Issues 1–3 and finding A.
