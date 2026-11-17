# NIFTY weekly short strangle — does it work? Final report

**Short answer:** before brokerage, there is a small, real edge. At the real account's
broker (₹30 per lot), there is none. In both cases, one badly timed crash day would wipe
out more than a decade of profit, and it returns less than simply holding NIFTY.

- Study period: weekly expiries 2019-02-14 → 2026-11-09 (405 weeks)
- Data: NSE F&O bhavcopy (end-of-day), NSE India VIX, NIFTY spot
- Method: every rule pre-registered and committed to git before any result was computed
  (`04_preregistration.md`, commit f41f1f4, plus Amendments 1–3, all before the run)
- Not financial advice. This is a research exercise.

---

## 1. The question

A real retail account sold deep out-of-the-money NIFTY weekly options in 2026 (calls about
7% above spot, puts about 10% below, ₹0.29–2.59 premium per unit (calls ₹0.29–1.24, puts
₹0.34–2.59), 3–17 lots, held to expiry). 63 of the 64 closed legs were profitable (2 legs were
still open; count from the statement's P&L column). Does the strategy actually work, and how badly can it fail?

## 2. What the real account really made

| | Amount |
|---|---|
| Gross profit (Apr–Nov 2026) | ₹24,918 |
| Charges listed on the tax P&L | ₹3,617 |
| Net as the statement shows it | ₹21,300 |
| Brokerage implied by the GST lines (≈ ₹30 per lot) | ₹19,588 |
| **True net** | **≈ ₹1,712** |

- Brokerage was about 79% of gross profit. It is not shown as its own line on the statement;
  it was found by working back from the 18% GST charged on it (`01_market_rules_and_costs.md`).

## 3. How the test was run

- **Baseline (V1)**, matching the real account: sell a call 7% above and a put 10% below
  spot at the close 1 trading day before expiry; hold to expiry.
- **Five other variants:** delta strikes (V2), stop-loss (V3), iron condor (V4),
  VIX filter (V5), event filter (V6).
- **Costs:** every statutory charge at the rate in force on each date (STT, NSE, SEBI, stamp
  duty, GST), plus slippage of 1 tick (₹0.05), with 2 and 4 ticks shown alongside.
- **Brokerage scenarios:** A = ₹30 per lot (real broker), B = ₹20 per lot, C = ₹0.
- **In-sample** 2019–2023 (includes COVID and 2022) and **out-of-sample** 2024–2026.
  No parameter was tuned on results.
- **Checks before results:** cost model reproduces the real statement's charges; settlement
  reproduces all 54 real held legs; no look-ahead (unit-tested); six trades re-computed field by
  field by script (the by-hand check of the printout is still open).
- **Engine vs reality:** run on the real account's 30 expiries and sizes, the baseline gives
  ₹21.2k gross / ₹2.3k net at ₹30 per lot, against the account's real ₹23.5k (NIFTY legs only)
  / ₹1.7k.

## 4. Results — baseline (V1), 10 lots, 1 tick slippage

| Brokerage | 2019–2023 net | 2024–2026 net | Return on margin 2024–26 (per year) |
|---|---|---|---|
| A: ₹30 per lot | ₹125,801 | **−₹1,152** | −0.7% |
| B: ₹20 per lot | ₹185,155 | ₹32,242 | — |
| C: ₹0 | ₹303,863 | ₹99,030 | 2.4% |
| NIFTY buy-and-hold (dividends excluded) | 16.1% per year | 5.8% per year | — |

Why brokerage decides it (2024–26, 10 lots):
- Average profit before brokerage: about **₹660 per week**.
- Brokerage at ₹30 per lot: 2 legs × 10 lots × ₹30 = ₹600, plus 18% GST = ₹708 in a week with
  both legs. 17 legs were skipped, so the 2024–26 average is about **₹668 per week**.
- The broker takes slightly more than the strategy earns.

Where the 2019–23 profit came from:
- At ₹30 per lot, 73% of the ₹125.8k (₹91.6k) came from 13 weeks in Mar–May 2020, when
  COVID fear made options expensive.
- Remove the best 10 weeks and the 2019–23 total falls to about ₹1k.

## 5. The other variants

| Variant | What happened |
|---|---|
| V2 delta strikes | Highest totals, but strikes sit much closer to spot. One week lost 352 points per unit, about 120 weeks of ₹0-brokerage profit |
| V3 stop-loss | Worse than V1. Stops trigger on spikes that would have expired worthless |
| V4 iron condor | Worst. The protective wings cost more than the premium left after costs |
| V5 VIX filter | Worse. Skipping high-VIX weeks skips the most profitable weeks |
| V6 event filter | Lower totals than V1 in 4 of 6 brokerage-period cells; higher in 2024–26 at ₹30 and ₹20 per lot. Skipped 69 weeks for events (52 in 2019–23, 17 in 2024–26); its worst week was the same as V1's in every case |

## 6. Pre-registered hypotheses

| | Prediction | Result |
|---|---|---|
| H1 | V1 has a positive mean after costs (₹0 brokerage) in both periods, also at 2 ticks | **HELD** |
| H2 (Goggy) | The event filter is profitable in both periods with a smaller worst week | **FAILED** under A, B and C |
| H3a (Claude) | The event filter does not avoid the worst 2019–23 week | HELD (trivially: both worst weeks were 0) |
| H3b (Claude) | No variant makes money at ₹30 per lot | **FAILED** (V1 2019–23, V2 in both periods and V6 2019–23 did) |
| H4 | The iron condor has a smaller 99% tail loss than V1 | **FAILED** |

## 7. The risk the backtest did not see

- At the baseline strikes, V1 never lost a week at ₹0 brokerage. That is partly **calendar luck**.
- NIFTY's largest one-day fall in the period, **−12.98% on Monday 23 Mar 2020**, was not an
  expiry day. About 21% of trading days are.
- Only 2 of the 30 largest one-day moves since 2016 would have gone through the V1 strikes:

| Day | Move | Loss if it had been an expiry day (spot 25,000, lot 65) | At 10 lots | At 100 lots |
|---|---|---|---|---|
| 2020-03-23 | −12.98% | 745 points per unit | **₹4.84 lakh** | ₹48.4 lakh |
| 2020-04-07 | +8.76% | 441 points per unit | ₹2.87 lakh | ₹28.7 lakh |

- The ₹4.84 lakh day equals:
  - about **678 weeks (13 years)** of best-case (₹0 brokerage) profit
  - about **4,500 weeks** of profit at ₹20 per lot
  - never recovered at ₹30 per lot, where the average week already loses
  - about **100 times** a ₹5,000 weekly loss limit, and about 280 times the real account's
    7-month true net
- Rough frequency: a move that size landing on an expiry day happened about once in 25 years
  in this history (≈ 4% per year for both sides combined). This rests on very few events and
  could easily be wrong in either direction.
- Circuit breakers pause trading but do not cap the settlement move. A 10% move halts trading
  for up to 45 minutes; a 15% move halts it for up to 1 h 45 min, or closes the market if it
  comes at or after 2 PM; a 20% move closes the market for the day.

## 8. Verdict

- **Is there an edge after costs?** Only with near-zero brokerage. At ₹0 the baseline earns
  about ₹700 a week at 10 lots, and that survives removing the best 10 weeks. At ₹30 per lot
  it loses money in 2024–26, and its 2019–23 profit depends on a handful of COVID weeks.
- **Best risk-adjusted variant:** the plain baseline (V1, day-before entry). None of the
  "safer" variants made it safer; they added cost or skipped the good weeks.
- **Is it worth the risk?** Even at ₹0 brokerage it earned 2.4% a year on margin in 2024–26,
  less than NIFTY itself (5.8% before dividends), while carrying a rare one-day loss of
  13+ years of profit. At ₹20 per lot, a rough estimate of the yearly cost of that tail is
  larger than the yearly profit.
- **For the real account:** at ₹30 per lot, the trades are working for the broker. The 2026
  result (₹1.7k true net) is what the backtest predicts, not bad luck.

## 9. Assumptions and how much each could change the result

| Assumption | Effect on results |
|---|---|
| Brokerage ₹30 per lot, inferred from GST (no contract note) | **Decisive.** ₹30 vs ₹0 moves 2024–26 from −₹1.2k to +₹99k at 10 lots |
| Entry at the day's close (end-of-day data only) | Unknown direction. Real fills happen during the day |
| Slippage 1 tick, not measured (no bid/ask data) | At 2 / 4 ticks, V1 ₹0-brokerage 2024–26 falls 9% / 26% in points per unit (8% / 25% in rupees) |
| No crash landed on an expiry day in the sample | **Largest.** One such day ≈ −₹4.8 lakh at 10 lots |
| Margin ≈ 10% of spot × units (no NSE SPAN files) | Return on margin 2.4% at 10%; 3.4% at 7%; 1.8% at 13% |
| Interest on margin money not counted | Would raise return on margin somewhat |
| Stop-loss fills whenever the day's high touches the stop | Pessimistic for V3 |
| Legs skipped when no strike is near the target | 17 legs skipped in 2024–26 (the real account went call-only too) |
| Clearing charges and per-contract-note STT rounding not modelled | Costs understated by about ₹0.5 per leg |
| Stamp duty before Jul 2020 at the later national rate; SEBI fee on in-the-money expiry | Negligible (paise per trade) |
| Benchmark excludes NIFTY dividends | Understates the index (dividend yield not measured in this study) |
| Lot sizes | Verified from NSE circulars, applied per contract |

## 10. What would make the study stronger

- A contract note to confirm the brokerage rate.
- Intraday data (1-minute bars and bid/ask) to measure slippage and test stops properly.
- NSE SPAN margin files for exact margin.
- Option data before 2019 (no NIFTY weeklies existed then) or another index for more crash
  days.

## Files

- Pre-registration and amendments: `docs/weekly_strangle/04_preregistration.md`, `04a_amendment_1.md`
- Results: `docs/weekly_strangle/06_results.md`, `outputs/weekly_strangle/results_grid.csv`
- Tail analysis (exploratory): `docs/weekly_strangle/07_exploratory_tail.md`
- Charts: `outputs/weekly_strangle/charts/`
- Code guide: `src/weekly_strangle/README.md`
