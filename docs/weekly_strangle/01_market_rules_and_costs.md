# Weekly strangle study — Step 2: market rules, charge rates, real-statement reconciliation

Research and documentation only. No backtest code was written.

- Audit date: 2026-11-16.
- Every source below was accessed on 2026-11-16.
- Machine-readable tables:
  - `config/weekly_strangle/charge_rates.csv` (23 rows)
  - `config/weekly_strangle/market_rules.csv` (23 rows)
  - Each row carries rate, base, side, effective dates, source URL, date accessed and status.

Status meanings:
- **VERIFIED**: the primary source itself was read. That means an NSE circular PDF, a SEBI circular PDF,
  the CBDT statute page, or an official NSE rules page.
- **SECONDARY**: only a broker/blog page, an official explainer that is not the governing text, or a
  primary source that confirms part of the row but not all of it (the notes column says which part).
- **UNVERIFIED**: no source found.

How the sources were read:
- NSE circulars were fetched as PDFs from `nsearchives.nseindia.com` / `archives.nseindia.com` and read
  in full.
- The SEBI circular, CBDT, PIB and NSE web pages were read in the built-in browser.
- Several government hosts (indiabudget.gov.in, indiacode.nic.in, incometaxindia.gov.in root, SEBI
  listing pages) refused automated fetching. Those documents were not read.

---

## 0. Privacy

- `data/private/` was appended to `.gitignore`. That is the only change to an existing file.
- `git check-ignore -v data/private/real_pnl_fy2026-27.xlsx` returns `.gitignore:24:data/private/`, so
  the file is ignored.
- The statement was copied into `data/private/` later on 2026-11-16, and git shows it as ignored (`!!`).
  It is not in any commit.
- The client name and client code were never printed or written to any doc. The script skips the header
  area and the "Client Code" column.

## 1. Charges (2024-01-01 → 2026-11-16)

### a. STT on option sale (on premium, paid by the seller)

- **0.0625%** from 2024-01-01 to 2024-09-30.
  - SECONDARY: exchange notice MSE/F&A/16075/2024 and broker notices.
- **0.10%** from 2024-10-01 to 2026-03-31.
  - The rate and the end date are confirmed by NSE's STT table ("rates upto March 31, 2026") and by
    PIB release 2221416 (Ministry of Finance, 2026-02-01, "present rate of 0.1 percent").
  - The **start date 2024-10-01 is secondary only**, so the row is marked SECONDARY.
- **0.15%** from 2026-04-01.
  - VERIFIED: CBDT Section 98, Table entry 4(a), "0.15 per cent … Seller", page last reviewed 2026-10-26:
    https://wm.incometaxindia.gov.in/w/section-98-55
  - Also NSE's STT table, "rates w.e.f. April 1, 2026":
    https://www.nseindia.com/static/invest/first-time-investor-sebi-turnover-fees-stt-other-levies

### b. STT on options exercised / settled in the money

- **0.125%** to 2026-03-31, then **0.15%** from 2026-04-01.
- Charged on the **intrinsic value** (since 2019-09-01, per NSE).
- **Payable by the purchaser**, i.e. the long holder whose option is exercised. CBDT Section 98 entry 4(b)
  says "Purchaser".
- **A short (written) option that finishes ITM does not pay this STT.** For a short strangle held to
  expiry, the only STT is the 4(a) sale STT at entry.
- VERIFIED: CBDT, NSE and PIB.

### c. NSE exchange transaction charge (index options, on premium, each side)

- **2024-01-01 → 2024-09-30**:
  - NSE charged *members* a monthly slab: flat ₹2,500 up to ₹3 cr of premium, then ₹50.00/lakh down to
    ₹30.00/lakh. VERIFIED from NSE/FA/56129 (2023-03-24).
  - Clients typically paid **0.0495%**. That rate was set by each broker; SECONDARY.
- **2024-10-01 → 2026-02-28: 0.03503%**.
  - ₹35.03 each side per lakh of premium, the same for every member (SEBI "true to label").
  - VERIFIED: NSE/FA/64232 (2024-09-27), https://nsearchives.nseindia.com/content/circulars/FA64232.pdf
- **2026-03-01 → today: 0.0355299%**.
  - ₹3,552.99 each side per crore. IPFT moved into the transaction charge; the total stays ₹3,553 per crore.
  - VERIFIED: NSE/FA/73061 (2026-02-27), https://nsearchives.nseindia.com/content/circulars/FA73061.pdf

### d. SEBI turnover fee

- **₹10 per crore (0.0001%)** on purchases and sales, both sides.
- SECONDARY: from NSE's official levies page. The SEBI fee regulation itself was not read.
- That it applies to *premium* turnover for options is not confirmed by a primary source.

### e. Stamp duty on options

- **0.003% of premium, buyer only**, from 2020-07-01 (Finance Act 2019 amending the Indian Stamp Act).
- SECONDARY: NSE levies page. The Stamp Act and gazette text were not read.
- For a short strangle held to expiry, there is **no buy order**, so there is no stamp duty. A buy-back
  pays stamp duty.

### f. GST

- **18%** (CGST 9% + SGST 9%, or IGST 18%).
- It applies to brokerage, exchange transaction charges, clearing charges and the SEBI fee.
- It does **not** apply to STT or stamp duty.
- Whether IPFT is in the GST base is not confirmed.
- SECONDARY: NSE levies page ("Stock brokers services 18%") and SEBI's home page ("SEBI fees attract GST
  @ 18%"). The CBIC notification was not read.

### g. Other line items

- **NSE IPFT**, on premium, each side:
  - ₹50 per crore (0.0005%) from 2023-04-01 to 2026-02-28.
  - ₹0.01 per crore from 2026-03-01.
  - VERIFIED: NSE/FA/56129 and NSE/FA/73061.
- **BSE transaction charge (SENSEX options)**:
  - ₹3,250 per crore (0.0325%) from 2024-10-01.
  - SECONDARY: broker summary. The BSE notice was not read, and later BSE revisions were not checked.
- **Clearing charges ("CLG CHGS")**: UNVERIFIED. No primary schedule was found. The script implies the
  rate from the statement.

### h. NSE quantity-freeze limit for NIFTY (maximum units per order)

| Period | Limit | Status | Source |
|---|---|---|---|
| 2023-04-03 → 2025-01-31 | **1,800** | SECONDARY | NSE/FAOP/56223 (1,800 from 2023-04-03) and NSE/FAOP/66428 (1,800 from 2025-02-01) both read; the 2024 interim circulars were not read |
| 2025-02-01 → 2026-10-04 | **1,800** | VERIFIED | Read: NSE/FAOP/66428, 68834, 71540, 73531, 74942, 75521. All say 1,800 |
| 2026-10-05 → 2026-11-01 | **3,510** | VERIFIED | NSE/FAOP/76693 (2026-10-01). Computed methodology suspended for indices |
| 2026-11-02 → today | **1,800** | VERIFIED | NSE/FAOP/77189 (2026-10-30). Methodology reinstated |

- A 100-lot NIFTY leg is 6,500 units at lot 65, so it needs **⌈6500/1800⌉ = 4 orders** per side today
  (2 orders during the 3,510 window).
- A 10-lot leg (650 units) needs 1 order.
- The SENSEX freeze limit is UNVERIFIED.

### Brokerage (not regulated; modelling scenarios only)

- **discount**: ₹20 per executed order.
- **implied_real**: **₹30 per lot traded**, implied from the real statement (Section 3). It reproduces the
  listed GST to within ₹0.29. Status SECONDARY: it is inferred, not taken from a broker tariff document.

## 2. Market rules

### a. Expiry weekday

- **Thursday** for contracts expiring on or before 2025-08-31. **Tuesday** for contracts expiring on or
  after 2025-09-01. Monthly expiries moved to the last Tuesday.
- Sources, all VERIFIED:
  - NSE/FAOP/68589 (2025-06-17).
  - NSE/FAOP/68747 (2025-06-25), which has an annexure.
  - Both are issued under SEBI/HO/MRD/TPD-1/P/CIR/2025/76 (2025-05-26). The SEBI document itself was
    not read.
- The annexure lists the last Thursday weekly as 2025-08-21, the last Thursday monthly as 2025-08-28 and
  the **first Tuesday weekly as 2025-09-02**.
- **This matches the data-derived calendar exactly** (Thursday until 2025-08-28, Tuesday from 2025-09-02).
- Holiday handling (expiry moves to the previous trading day) is only shown by example in the circular
  ("24-Dec-25, since 25-Dec-25 is holiday"). SECONDARY.

### b. Lot-size circulars (all VERIFIED; dates match the project's data)

- **NSE/FAOP/61415** (2024-04-02): NIFTY lot 50 → 25, effective 2024-04-26.
  - Only the April 2024 monthly (expiring 2024-04-25) kept 50.
  - The circular says all contracts "available for trading from trade date of April 26, 2024, onwards
    will be with the revised market lot size".
  - **So existing weekly contracts did change lot size mid-life.** This confirms the data: the
    2024-05-02 contract was 50 on 2024-04-25 and 25 from 2024-04-26.
  - The note in `config/lot_size_history.csv` (existing contracts keep their original lot size) is
    **wrong for this change**. It is not edited here; this document records the correction.
- **NSE/FAOP/64625** (2024-10-18): 25 → 75 for new contracts introduced from 2024-11-20.
  - Existing weekly and monthly contracts kept 25 until expiry: last weekly with 25 was 2024-12-19, last
    monthly 2025-01-30, first weekly with 75 2025-01-02.
  - Quarterly and half-yearly contracts were revised at 2024-12-26 EOD.
- **NSE/FAOP/70616** (2025-10-03): 75 → 65, effective 2025-10-28 EOD.
  - Weekly and monthly contracts kept 75 through the 2025-12-30 expiry: last weekly with 75 was
    2025-12-23, first weekly with 65 2026-01-06.
- The pattern: the lot-size *decrease* in 2024 was applied to existing contracts. The two later changes
  grandfathered existing weeklies and monthlies.

### c. SEBI's October 2024 measures

- Source: SEBI/HO/MRD/TPD-1/P/CIR/2024/132, dated 2024-10-01. The PDF was read in full. VERIFIED.

| Measure | Effective |
|---|---|
| Minimum contract value ₹15 lakh at introduction, ₹15–20 lakh at review (was ₹5–10 lakh) | 2024-11-20 |
| One weekly-expiry benchmark index per exchange | 2024-11-20 |
| Extra **2% ELM on short options** expiring that day (open at start of day, or opened that day) | 2024-11-20 |
| Calendar-spread benefit removed on expiry day for expiring contracts | 2025-02-01 |
| Upfront collection of net option premium from buyers | 2025-02-01 |
| Intraday monitoring of position limits (at least 4 snapshots a day) | 2025-04-01 |

### d. Margin for a short option (method and sources only; estimated in a later step)

- **Method**: SPAN initial margin plus Extreme Loss Margin (ELM).
  - SPAN covers 99% VaR over a 1-day horizon.
  - VERIFIED from NSE's margins page: https://www.nseindia.com/static/products-services/equity-derivatives-margins
- **SPAN parameters for index derivatives**:
  - Price scan range: 6σ × √2, capped at 9.3% of the underlying.
  - Volatility scan range: 25% of annualised EWMA volatility, minimum 4%.
  - Calendar spread charge: 1.75%.
  - VERIFIED from the SPAN page (updated 2024-07-04): https://www.nseindia.com/static/products-services/equity-derivatives-span-risk-parameter-files
- **ELM on short index options**, charged on notional (index value × quantity):
  - 2% normally.
  - **3% if the strike is more than 10% OTM against the previous close.** Many of the study's 8–14% puts
    are in this band.
  - 5% if residual maturity is over 9 months.
  - Plus 2% on expiry day under SEBI 2024/132.
  - The effective date of the 3% deep-OTM rule is not stated on the page.
- **Historical SPAN files**:
  - Daily begin-day, intraday and end-of-day risk-parameter files are linked from NSE's derivatives
    archives page: https://www.nseindia.com/resources/historical-reports-capital-market-daily-monthly-archives-derivative-market
  - File naming `nsccl.YYYYMMDD.*.spn` comes from circulars quoted on secondary sites.
  - How far back the files go was not tested. SECONDARY.

### e. Old-format NSE F&O bhavcopy archive (plain GET, status only, nothing saved)

| Date | URL file | HTTP |
|---|---|---|
| 2020-03-13 | `fo13MAR2020bhav.csv.zip` | **200**, application/zip (466,467 B) |
| 2022-02-24 | `fo24FEB2022bhav.csv.zip` | **200**, application/zip (873,686 B) |
| 2023-06-29 | `fo29JUN2023bhav.csv.zip` | **404** |
| 2023-06-28 (extra check) | `fo28JUN2023bhav.csv.zip` | 200, application/zip |
| 2023-06-30 (extra check) | `fo30JUN2023bhav.csv.zip` | 200, application/zip |

- The 404 on 2023-06-29 looks like a market holiday, since both neighbouring days return files.
- **The old archive is still downloadable for 2020, 2022 and 2023.** That makes the Mar 2020 and
  Feb–Mar 2022 periods reachable for a later, separately approved data step. No bulk download was done.

## 3. Real-statement reconciliation

Source and method:
- **Statement**: `data/private/real_pnl_fy2026-27.xlsx` (gitignored). Tax P&L for FY2026-27, one sheet
  "Future and Option", NIFTY and SENSEX weekly options, expiries from 30 Mar 2026 to 17 Nov 2026.
- **Script**: `scripts/weekly_strangle/reconcile_real_statement.py`, run on 2026-11-16. `openpyxl` was
  installed into `.venv` only; it was not added to `requirements.txt`.
- All figures below are printed by the script. Rates come from `charge_rates.csv`. Every rate used is
  constant over Apr–Nov 2026.

### Layout facts found in the file (they change how it must be read)

- **Charge lines**: labelled `*CGST*`, `*SGST*`, `*STT*`, `*TOC NSE EXCHANGE*`, `*TOC BSE EXCHANGE*`,
  `*CLG CHGS*` and `*ROUNDING*`, each with its signed amount in the "Profit and Loss" column.
  - The first script version missed them (asterisks, wrong column) and was corrected.
- **Average prices are rounded**, so premium must come from the Amount columns. For example,
  585 × 0.54 = 315.90, but the Sell Amount is 315.02.
- **Expiry rows**: legs held to expiry show a "buy" at ₹0. These are not trades and attract no charges.
- **Opening position**: 1 closed leg (NIFTY 30Mar2026 25800 CE) was sold in the previous FY. Its ₹552.50
  premium sits in "Opening Amount", and its P&L is in this statement.
- **Open legs**: **two rows** have non-zero Net Qty, not one. They are both legs of the 17 Nov 2026
  strangle (27900 CE −390, 22000 PE −715), which the statement counts as "1 open position".
  - Both are excluded from P&L.
  - Their *sales* happened in the period, so they are **included** when checking charges, because STT and
    exchange charges were levied on them.
- **Embedded price adjustment**: every NIFTY trade price sits **₹0.0115 per unit off the ₹0.05 tick**
  (sells lower, buy-backs higher). SENSEX prices have no such adjustment.
  - Total ₹443.68. It is already inside the statement's P&L column.
  - What it is remains unknown (UNVERIFIED).

### Reconciliation table

| Item | Statement | Predicted from Step 1 rates | Difference |
|---|---|---|---|
| Closed legs (NSE / BSE) | 64 (57 / 7) | — | — |
| Units sold, closed legs | 37,630 (incl. 650 sold last FY) | — | — |
| Sell premium in period, closed legs | ₹27,058.20 (+ ₹552.50 carried in) | — | — |
| Gross P&L, closed legs (statement column) | **₹24,917.54** | recomputed from amounts: ₹24,917.52 | ₹0.02 |
| Held to expiry / bought back | 61 / 3 | — | — |
| Trades in period (incl. open legs' sales) | 65 sells + 3 buy-backs | — | — |
| Executed orders | **68** (no leg above the 1,800 freeze; largest 1,105 units) | 68 with freeze split | 0 |
| Lots traded | **653** (NIFTY lot 65; SENSEX lot 20, implied) | — | — |
| Premium turnover (sells + buy-backs) | NSE ₹29,645.93; BSE ₹1,370.00 | — | — |
| STT | ₹73.00 | exact 0.15%: ₹42.48 | +₹30.52 (+71.8%) |
| | | rounded up per leg: ₹78.00 | −₹5.00 |
| | | rounded up per expiry: ₹60.00 | +₹13.00 |
| | | rounded up per trading day: **not testable** (no trade dates) | — |
| TOC NSE | ₹16.32 | 0.0355299% (+ IPFT): ₹10.53 | +₹5.79 (+54.9%); implied rate 0.05505% |
| TOC BSE | ₹0.98 | 0.0325%: ₹0.45 | +₹0.53 (+120%); implied rate 0.07153% |
| CLG CHGS | ₹1.45 | no verified rate | implied 0.00468% of premium turnover |
| SEBI fee | no line | ₹0.03 | — |
| Stamp duty | no line | ₹0.08 | — |
| ROUNDING | ₹3.57 credit | — | — |
| CGST + SGST | ₹3,529.28 → GST base ₹19,607.11 | — | — |
| GST-able listed lines (TOC NSE + TOC BSE + CLG) | ₹18.75 | — | — |
| **Unlisted brokerage implied** | **₹19,588.36** (₹19,588.33 if the SEBI fee is in the base) | — | — |

### Which brokerage scheme fits?

With one aggregate total, any one-parameter scheme fits exactly. So the error below is measured at the
nearest *round* value of X:

| Scheme | Fitted X | Nearest round X | Predicted GST | Error vs ₹3,529.28 |
|---|---|---|---|---|
| ₹X per order (68) | 288.0641 | 290 | ₹3,552.97 | +₹23.69 (+0.67%) |
| **₹X per lot traded (653)** | **29.9975** | **30** | ₹3,529.57 | **+₹0.29 (+0.01%)** |
| X% of premium turnover | 63.1558% | 63% | ₹3,520.58 | −₹8.70 (−0.25%) |

- **₹30 per lot traded fits almost exactly.**
- 63% of premium is not a plausible brokerage scheme.
- For comparison, the discount scenario (₹20 × 68 orders) would cost ₹1,360.00.

### Net P&L (closed legs)

| | Amount |
|---|---|
| Gross P&L (statement column) | ₹24,917.54 |
| Listed charge lines, net of the ₹3.57 rounding credit | ₹3,617.46 |
| **(a) Gross − listed charges** | **₹21,300.08** |
| Implied brokerage | ₹19,588.36 |
| **(b) (a) − implied brokerage** | **₹1,711.72** |

- In (b), the GST on the brokerage (₹3,525.91) is already inside the listed CGST + SGST, so it is not
  added again.
- Implied brokerage equals **78.6% of gross P&L** and **63.2% of premium turnover**.

### What the reconciliation shows

- The listed charge lines alone understate costs badly. The CGST + SGST lines imply about ₹19.6k of
  brokerage that never appears as its own line.
- On deep-OTM premiums that average under ₹1, a per-lot brokerage of ₹30 is the dominant cost.
- Compared with the statutory rates:
  - TOC lines are 55% (NSE) and 120% (BSE) higher than the true-to-label rates predict.
  - STT is higher than the exact rate. It is consistent with rounding up once per contract note, but
    that cannot be proven without trade dates.

## What this changes for the cost model (for the next step)

- For **hold-to-expiry** trades, sell-side charges dominate:
  - STT 0.15% of premium (from 2026-04-01; 0.10% and 0.0625% earlier).
  - NSE transaction charge about 0.0355% of premium.
  - SEBI fee 0.0001%.
  - GST on the GST-able items.
  - One brokerage order per freeze-limit slice.
- **When the position expires worthless, there are no buy-side charges and no exercise STT.**
- A buy-back exit adds the same exchange, SEBI and brokerage charges, stamp duty of 0.003%, and further
  order slices.
- Margin for deep-OTM short puts beyond 10% OTM carries 3% ELM, not 2%, plus 2% more on expiry day.
- **Brokerage must be modelled per lot as well as per order.** At the real broker (₹30 per lot), it took
  78.6% of gross P&L. At a discount broker (₹20 per order), the same trades would have cost ₹1,360.
- Statement-level effects to carry into the model:
  - STT rounding (listed is about 72% above exact).
  - TOC above the statutory rate.
  - A ₹0.0115 per unit adjustment inside the price on NIFTY trades.

## STILL UNVERIFIED (or only secondary)

- STT start date 2024-10-01 for 0.10%, and the 0.0625% rate before it. Only exchange and broker notices
  were seen; Finance (No. 2) Act 2024 text not read.
- Whether the Finance Act 2026 was enacted. It is inferred because the current CBDT statute page shows
  0.15% and NSE applies it from 2026-04-01. The Act and gazette text were not read.
- SEBI turnover fee of ₹10 per crore, and whether it is levied on option premium. NSE explainer only.
- Stamp duty of 0.003% on option buys. NSE explainer only; Stamp Act and gazette not read.
- The exact GST base, in particular whether IPFT is included. CBIC notification not read.
- BSE SENSEX option transaction charge of ₹3,250 per crore, and any 2025–2026 change. Broker summary only.
- Clearing charges ("CLG CHGS"): no rate source at all.
- NIFTY freeze limit during 2024. It is bounded by 1,800 on both sides, but the 2024 circulars were not
  read.
- SENSEX lot size and freeze limit (needed for the SENSEX legs of the statement).
- The client-level NSE transaction charge before 2024-10-01 (broker-set; 0.0495% is typical).
- The SEBI expiry-day circular of 2025-05-26 itself (known only as cited in NSE/FAOP/68589).
- Final settlement price of NIFTY options as the index closing value. Not checked against contract specs.
- Effective date of NSE's 3% ELM for short index options more than 10% OTM.
- How far back NSE's historical SPAN risk-parameter files go.
- The broker's actual brokerage tariff. ₹30 per lot is inferred from GST and has not been confirmed
  against a tariff sheet or contract notes.
- What the ₹0.0115 per unit price adjustment on NIFTY trades is.
- Why listed TOC NSE (0.05505%) and TOC BSE (0.07153%) exceed the true-to-label exchange rates.
- How STT is rounded. ₹73 lies between rounding up per expiry (₹60) and per leg (₹78); per trading day
  needs contract notes with dates.
