# Weekly strangle study — Step 6: engine and correctness gates

**The backtest was not run.**
- No aggregate P&L, win rate, total, mean, drawdown or CVaR was computed for any variant or period.
- The only per-trade results computed are the six Gate 4 hand-check trades.
- Gate 2 computes intrinsic values for the real legs and prints only a pass count.

**Run on 2026-11-17.**
- Gate script: `scripts/weekly_strangle/run_gates.py`.
- Code: `src/weekly_strangle/` (plain-English guide in its `README.md`).
- Tests: `tests/weekly_strangle/`.

**Rules followed:**
- `04_preregistration.md`, including Amendment 1.
- `config/weekly_strangle/prereg_params_amendment_1.json`.
- `config/weekly_strangle/step6_decisions.json`: decisions D1–D8, adopted 2026-11-17 ("Take all recommended").

## Files added

- **Code (`src/weekly_strangle/`):** `__init__.py`, `data.py`, `calendar.py`, `strikes.py`, `costs.py`,
  `settlement.py`, `variants.py`, `engine.py`, `README.md`.
- **Gates:** `scripts/weekly_strangle/run_gates.py`.
- **Tests (`tests/weekly_strangle/`):** `conftest.py`, `test_calendar.py`, `test_strikes.py`, `test_costs.py`,
  `test_settlement.py`, `test_variants.py`, `test_data.py`, `test_engine.py`.
- **Config:**
  - `config/weekly_strangle/step6_decisions.json`: decisions D1–D8.
  - `config/weekly_strangle/charge_rates_pre2024.csv`: decision D2, sourced as below.
- **`.gitignore`:** one line added, `data/processed/*.parquet`.
  - It covers the option cache (1,089,889 rows) and the spot cache (1,943 days).
  - No existing `src/` or `config/` file was changed.
- **Environment:** `pyarrow` 26.0.1 was installed in `.venv` for the parquet cache.

## Pre-2024 charge rates (decision D2), from primary sources

- **STT on option sale:**
  - 0.05% up to 2023-03-31, then 0.0625% from 2023-04-01.
  - Source: NSE/FATAX/56235 (Finance Act 2023). VERIFIED.
- **STT on exercise:**
  - 0.125%, payable by the purchaser.
  - Charged on intrinsic value from 2019-09-01 (NSE/FATAX/41919). VERIFIED.
  - Before 2019-09-01 it was charged on "the settlement price". Reading that as underlying × units is an
    interpretation, so that row is SECONDARY.
  - It applies only to V4 long wings.
- **NSE options transaction charge:** the first incremental slab, i.e. what clients are typically billed
  (decision D3).
  - 0.050% up to 2020-12-31.
  - 0.053% from 2021-01-01 (NSE/FA/46730).
  - 0.050% from 2023-04-01 (NSE/FA/56129).
  - All VERIFIED.
- **IPFT:**
  - ₹0.01 per crore up to 2023-03-31. The start date wasn't read, so this row is SECONDARY.
  - ₹50 per crore from 2023-04-01 (NSE/FA/56129).
- **SEBI fee:**
  - ₹15 per crore before 2019-04-01. SECONDARY: the SEBI board decision was not opened.
  - ₹10 per crore from 2019-04-01 (Gazette, via NSE/FA/40632). VERIFIED.
  - ₹5 per crore from 2020-06-01 to 2021-03-31, a 50% relief (Gazette, via NSE/FA/44514). VERIFIED.
  - ₹10 per crore from 2021-04-01.
- **Not available:**
  - Stamp duty before 2020-07-01, which was state-wise.
  - The NIFTY freeze limit before 2023-04-03.
  - The engine stops with `MissingRateError` if either is needed. See the open decisions below.

## Unit tests

- `pytest tests/weekly_strangle`: **46 passed, 0 failed.**
- The existing `tests/test_lot_size.py` still passes: 4 passed.

## Gate 1 — cost model (decision D1: match Step 2's "predicted from rates" column within ₹1)

- **Inputs:** 66 statement rows (symbol, quantity and amount columns only) and 653 lots, priced at Step 2's
  rate date, 2026-06-01.
- **STT:** costs.py ₹42.48 vs Step 2 ₹42.48, diff ₹0.00. **PASS.**
  - The statement lists ₹73.00, ₹30.52 more: a known underestimate.
- **TOC NSE (transaction charge + IPFT):** ₹10.53 vs ₹10.53, diff ₹0.00. **PASS.**
  - The statement lists ₹16.32, ₹5.79 more.
- **TOC BSE:** ₹0.45 vs ₹0.45, diff ₹0.00. **PASS.**
  - The statement lists ₹0.98, ₹0.53 more.
- **Clearing:** not modelled (decision D4). The statement lists ₹1.45.
- **GST, for information:** costs.py gives ₹3,528.18 at brokerage A (₹19,590), against the statement's
  CGST + SGST of ₹3,529.28: diff −₹1.10.
  - Step 2 has no "predicted from rates" GST figure, so this line is not scored.
  - The gap comes from the unmodelled clearing charge and the listed TOC lines being higher.
- **SEBI fee and stamp duty:** ₹0.03 and ₹0.08, matching Step 2.
- **GATE 1: PASS.**

## Gate 2 — settlement replay

- Real NIFTY legs held to expiry: 54, as expected.
- Intrinsic value at the expiry-day spot close: 0 for all 54; non-zero for none.
- **GATE 2: PASS.**

## Gate 3 — no look-ahead

- Every selection, filter and entry function receives rows through `rows_as_of()` / `series_as_of()`,
  which stop with `LookAheadError` on any row dated after `as_of`.
- The tests feed a future row to:
  - the row guard;
  - the spot/VIX guard;
  - strike selection;
  - the VIX filter.

  They also check that rows up to the entry day are accepted.
- `pytest -k lookahead`: **5 passed**, 41 deselected.
- **GATE 3: PASS.**

## Gate 4 — hand check (V1 / T-1 / brokerage C / s = 1)

- **Sampling:**
  - Seed 20261117.
  - The six expiries were drawn from the expiry lists before any trade was built: IS 2019-12-12,
    2020-04-01, 2022-06-09; OOS 2026-01-06, 2026-04-07, 2026-09-29.
  - All six ended with both legs out of the money, so none hit the open rule for an in-the-money
    settlement.
- **Recomputation:** the script recomputes each net figure independently from the printed fields. All six
  **MATCH**.
- **By hand:** the check against the printout below is still yours to do.
- **Charge lines:** printed at 1 lot. The 10- and 100-lot lines scale exactly, because brokerage C is zero
  and every other charge is proportional.
- **GATE 4: PASS** (arithmetic re-check).

```
--- IS 2019-12-12; entry T-1 = 2019-12-11; spot 11910.15; settlement spot 11971.80
  CE: 34 eligible; 8 strikes >= 5% OTM; chosen 12700 (6.6317% OTM); close 0.25; volume 1571; lot 75; fill 0.20; intrinsic 0.00
      1 lot (75 units): premium Rs 15.00; brokerage 0; STT 0.0075; NSE txn 0.0075; IPFT 0.000000; SEBI 0.000015; stamp 0; GST 0.0014; total 0.0164
  PE: 33 eligible; 4 strikes >= 8% OTM; chosen 10800 (9.3210% OTM); close 0.45; volume 17; lot 75; fill 0.40; intrinsic 0.00
      1 lot (75 units): premium Rs 30.00; brokerage 0; STT 0.0150; NSE txn 0.0150; IPFT 0.000000; SEBI 0.000030; stamp 0; GST 0.0027; total 0.0327
  net: 1 lot Rs 44.95 (gross 45.00, charges 0.0491); 10 lots Rs 449.51; 100 lots Rs 4,495.09; 0.5993 points/unit
--- IS 2020-04-01; entry T-1 = 2020-03-31; spot 8597.75; settlement spot 8253.80
  CE: 86 eligible; 53 >= 5% OTM; chosen 9200 (7.0047% OTM); close 3.85; volume 78729; lot 75; fill 3.80; intrinsic 0.00
      1 lot: premium Rs 285.00; STT 0.1425; NSE txn 0.1425; IPFT 0.000000; SEBI 0.000285; GST 0.0257; total 0.3110
  PE: 68 eligible; 33 >= 8% OTM; chosen 7750 (9.8601% OTM); close 7.80; volume 3251; lot 75; fill 7.75; intrinsic 0.00
      1 lot: premium Rs 581.25; STT 0.2906; NSE txn 0.2906; IPFT 0.000001; SEBI 0.000581; GST 0.0524; total 0.6342
  net: 1 lot Rs 865.30 (gross 866.25, charges 0.9452); 10 lots Rs 8,653.05; 100 lots Rs 86,530.48; 11.5374 points/unit
--- IS 2022-06-09; entry T-1 = 2022-06-08; spot 16356.25; settlement spot 16478.10
  CE: 90 eligible; 43 >= 5% OTM; chosen 17500 (6.9927% OTM); close 0.85; volume 369848; lot 50; fill 0.80; intrinsic 0.00
      1 lot (50 units): premium Rs 40.00; STT 0.0200; NSE txn 0.0212; IPFT 0.000000; SEBI 0.000040; GST 0.0038; total 0.0451
  PE: 83 eligible; 15 >= 8% OTM; chosen 14700 (10.1261% OTM); close 0.25; volume 2690; lot 50; fill 0.20; intrinsic 0.00
      1 lot: premium Rs 10.00; STT 0.0050; NSE txn 0.0053; IPFT 0.000000; SEBI 0.000010; GST 0.0010; total 0.0113
  net: 1 lot Rs 49.94 (gross 50.00, charges 0.0563); 10 lots Rs 499.44; 100 lots Rs 4,994.37; 0.9989 points/unit
--- OOS 2026-01-06; entry T-1 = 2026-01-05; spot 26250.30; settlement spot 26178.70
  CE: 81 eligible; 11 >= 5% OTM; chosen 28100 (7.0464% OTM); close 0.35; volume 7889; lot 65; fill 0.30; intrinsic 0.00
      1 lot (65 units): premium Rs 19.50; STT 0.0195; NSE txn 0.0068; IPFT 0.000097; SEBI 0.000019; GST 0.0012; total 0.0277
  PE: 74 eligible; 4 >= 8% OTM; chosen 24000 (8.5725% OTM); close 0.60; volume 170699; lot 65; fill 0.55; intrinsic 0.00
      1 lot: premium Rs 35.75; STT 0.0357; NSE txn 0.0125; IPFT 0.000179; SEBI 0.000036; GST 0.0023; total 0.0507
  net: 1 lot Rs 55.17 (gross 55.25, charges 0.0784); 10 lots Rs 551.72; 100 lots Rs 5,517.16; 0.8488 points/unit
--- OOS 2026-04-07; entry T-1 = 2026-04-06; spot 22968.25; settlement spot 23123.65
  CE: 123 eligible; 50 >= 5% OTM; chosen 24600 (7.1044% OTM); close 0.75; volume 155838; lot 65; fill 0.70; intrinsic 0.00
      1 lot: premium Rs 45.50; STT 0.0683; NSE txn 0.0162; IPFT 0.000000; SEBI 0.000046; GST 0.0029; total 0.0874
  PE: 123 eligible; 21 >= 8% OTM; chosen 20650 (10.0933% OTM); close 1.45; volume 62719; lot 65; fill 1.40; intrinsic 0.00
      1 lot: premium Rs 91.00; STT 0.1365; NSE txn 0.0323; IPFT 0.000000; SEBI 0.000091; GST 0.0058; total 0.1748
  net: 1 lot Rs 136.24 (gross 136.50, charges 0.2621); 10 lots Rs 1,362.38; 100 lots Rs 13,623.79; 2.0960 points/unit
--- OOS 2026-09-29; entry T-1 = 2026-09-28; spot 22780.25; settlement spot 22716.20
  CE: 116 eligible; 71 >= 5% OTM; chosen 24350 (6.8908% OTM); close 1.15; volume 108137; lot 65; fill 1.10; intrinsic 0.00
      1 lot: premium Rs 71.50; STT 0.1072; NSE txn 0.0254; IPFT 0.000000; SEBI 0.000071; GST 0.0046; total 0.1373
  PE: 114 eligible; 8 >= 8% OTM; chosen 20800 (8.6928% OTM); close 0.50; volume 53125; lot 65; fill 0.45; intrinsic 0.00
      1 lot: premium Rs 29.25; STT 0.0439; NSE txn 0.0104; IPFT 0.000000; SEBI 0.000029; GST 0.0019; total 0.0562
  net: 1 lot Rs 100.56 (gross 100.75, charges 0.1935); 10 lots Rs 1,005.57; 100 lots Rs 10,055.65; 1.5470 points/unit
```

How to check by hand:
- Fill = close − 0.05.
- Points per unit = fill − intrinsic.
- STT = premium × rate on the entry date:
  - 0.05% in 2019–2022;
  - 0.10% on 2026-01-05;
  - 0.15% from 2026-04-01.
- NSE transaction charge = premium × rate:
  - 0.05% in 2019;
  - 0.053% in 2020-03 and 2022;
  - 0.03503% on 2026-01-05;
  - 0.0355299% from 2026-03.
- GST = 18% × (transaction charge + SEBI fee).

These six trades are not a sample result and say nothing about the strategy's outcome.

## Gate 5 — V6 events

| Year | Lok Sabha result | RBI MPC | US Fed FOMC | Union Budget | Total |
|---|---|---|---|---|---|
| 2019 | 1 | 6 | 8 | 2 | 17 |
| 2020 | 0 | 6 | 10 | 1 | 17 |
| 2021 | 0 | 6 | 8 | 1 | 15 |
| 2022 | 0 | 7 | 8 | 1 | 16 |
| 2023 | 0 | 6 | 8 | 1 | 15 |
| 2024 | 1 | 6 | 8 | 2 | 17 |
| 2025 | 0 | 6 | 8 | 1 | 15 |
| 2026 | 0 | 5 | 7 | 1 | 13 |

- **FOMC dates:** 44 FOMC rows were moved to the next Indian trading day (Amendment 1A). The 21 rows from
  `event_calendar.csv` were used as stored.
- **Status:** 101 VERIFIED, 24 SECONDARY (Amendment 1B; all count).
- **Election rows:**
  - 2019-05-23 | Lok Sabha Election Result | VERIFIED | `event_calendar_2019_2023.csv` | ECI/PN/58/2019.
  - 2024-06-04 | Lok Sabha Election Result | SECONDARY | `event_calendar.csv`.
- **Event types:** none in the calendars falls outside the V6 include/ignore lists. The 5 State Election
  Result rows are ignored (1D).
- **GATE 5: PASS.**

## Gate 6 — coverage (V1 / T-1 / s = 1; counts only)

| Year | Expiries | T-1 found | T-1 with file and spot | Legs traded | No eligible strike | Sale < 0.05 after slippage | Missing file | Missing spot |
|---|---|---|---|---|---|---|---|---|
| 2019 | 46 | 46 | 45 | 88 | 0 | 2 | 0 | 2 |
| 2020 | 53 | 53 | 53 | 104 | 0 | 2 | 0 | 0 |
| 2021 | 52 | 52 | 52 | 104 | 0 | 0 | 0 | 0 |
| 2022 | 52 | 52 | 52 | 104 | 0 | 0 | 0 | 0 |
| 2023 | 52 | 52 | 52 | 103 | 1 | 0 | 0 | 0 |
| 2024 | 52 | 52 | 52 | 98 | 6 | 0 | 0 | 0 |
| 2025 | 53 | 53 | 53 | 101 | 5 | 0 | 0 | 0 |
| 2026 | 45 | 45 | 45 | 84 | 6 | 0 | 0 | 0 |
| **Total** | **405** | **405** | **404** | **786** | **18** | **4** | **0** | **2** |

- **Missing spot:** the one week skipped for missing spot is the first IS expiry, 2019-02-14 (T-1 =
  2019-02-13 has no spot). The other spot-less day, 2019-03-29, is a T-4 day and does not affect T-1.
- **Missing file:** 2021-03-30 only affects T-2 entries, so the count is 0 at T-1.
- **Accounting:** every expiry is accounted for (legs traded + skipped = 2 × expiries).
- **GATE 6: PASS.**

## Summary

- Gates 1–6: **all PASS.**
- Unit tests: 46/46 pass.

## Decisions I STOPPED on (not decided; the engine raises an error instead)

1. **Charges when a leg settles in the money: DECIDED after the run, as D9 (Goggy, 2026-11-17, "Add SEBI
   fee too").**
   - Section 4 doesn't say whether the SEBI fee or an exchange charge applies at an in-the-money
     settlement. The SEBI Gazette defines option "turnover" to include "notional value of option contracts
     exercised or assigned".
   - At the time of the gate run, `costs.settlement_charges` raised `UndecidedRuleError` for any leg with
     intrinsic > 0. None of the six Gate 4 trades hit it.
   - **D9 now applies.** An in-the-money leg pays the SEBI fee on notional plus 18% GST on that fee,
     whether it is short or long. A long leg also pays STT on exercise (Amendment 1C). There is no exchange
     transaction charge.
   - Notional is read as settlement spot × units. That is an interpretation of the Gazette wording.
   - Re-run after D9: unit tests 48 passed (one test replaced by three), with 5 look-ahead tests; Gates 1–6
     PASS, with output identical to the run above apart from the pytest count line.
2. **Stamp duty before 2020-07-01.** It was state-wise, so there is no single rate.
   - It blocks V3 buy-backs and V4 wing buys in 2019 to mid-2020 (`MissingRateError`).
3. **NIFTY freeze limit before 2023-04-03.** No primary source was read; a forum post says 2,800 → 1,800 from
   2022-11-01.
   - It blocks brokerage D (per order) before that date. Brokerage A, B and C don't need it.
4. **NSE transaction charge, Jan–Mar 2024.**
   - `charge_rates.csv` (existing, not edited) uses 0.0495% from 2024-01-01. A broker bulletin
     (secondary) says the cut from 0.050% to 0.0495% started on 2024-04-01.
   - The engine follows the existing row, per decision D3. The difference is 0.0005% of premium.
   - Fixing it would need a decision, because the existing file can't be edited.

## Open items, for the record

- Two pre-2024 rate rows are SECONDARY:
  - SEBI fee ₹15 per crore before 2019-04-01;
  - the basis of exercise STT before 2019-09-01.
- The GST line in Gate 1 is −₹1.10 against the statement. It is not scored under D1.
