# Research Journal — 2026-08-16 (every-day extension, pre-registration)

**No data has been downloaded and no backtest has been run while writing
this entry or `config/everyday_experiment.json`.** This is Part 1 of a
two-part task; Part 2 (download only, no analysis) follows in a
separate commit after this one.

## The stated hypothesis going in, and why the predictions below contradict it

My hypothesis walking into this was **"more trading days should mean
more profit"** -- if the pre-registered strategy is profitable on
expiry days, trading the same entry rule every day should just multiply
the opportunity. Predictions (a) through (d) below all point the other
way. Whichever way this actually falls once real data is downloaded and
analyzed, the result gets reported as-is, not reconciled with the
hypothesis after the fact.

## Predictions, stated before any data is downloaded

**(a) Mean P&L per trade in points will DECLINE as DTE rises.** A 0 DTE
option is bought back (same day) at essentially pure intrinsic value --
nearly all its time value has already decayed away by the close. A 6
DTE option, sold and bought back the same day, still retains most of
its time value at the close; only one day's worth of theta has been
captured out of many remaining. Since the pre-registered strategy's
edge comes specifically from capturing terminal decay, spreading the
same entry rule across DTE 0-6 should capture progressively less of
that edge as DTE rises, because theta itself is slowest far from
expiry and accelerates only in the final few days.

**(b) Win rate will fall as DTE rises.** Following directly from (a) --
if less time value is captured per trade on average as DTE increases,
a larger share of trades should end up net negative.

**(c) Standard deviation of P&L in points will RISE with DTE.** Away
from expiry, the position still carries meaningful vega (sensitivity to
implied volatility changes) alongside theta. A 0 DTE option barely
responds to a same-day volatility spike -- there's almost no time value
left for IV to act on. A 6 DTE option responds to that same spike much
more, since more extrinsic value remains for IV to inflate or deflate.
More vega exposure should show up as more day-to-day variance in P&L.

**(d) After realistic costs, mean P&L for DTE >= 3 may be negative.**
If (a) holds, the average points captured per trade shrinks as DTE
rises; realistic costs (brokerage, STT, slippage -- unchanged from
`config/strategy_with_costs.json`) are roughly flat in points-equivalent
terms per trade regardless of DTE, so a shrinking gross edge combined
with a roughly constant cost should cross zero somewhere in the middle
of the DTE range. Three is a guess at roughly where, not a precise
prediction -- what matters is the *shape* (a crossover exists) more
than the exact DTE bucket it occurs at.

**(e) The DTE=0 subset of `nearest_weekly` must reproduce the existing
136-trade baseline exactly.** This isn't a prediction about markets --
it's a pipeline correctness check. If the every-day extension's DTE=0
trades don't match `outputs/backtest_trades.csv` trade-for-trade, the
extension's entry logic, strike selection, or data handling has a bug,
and nothing else it reports should be trusted until that's found and
fixed.

## Why two variants, and why DTE buckets are never pooled

`nearest_weekly` is what a trader would actually do every day --
always sell whatever weekly expires soonest. But that means DTE isn't
constant: it cycles 0 through 6 depending on which day of the week it
is and where the week falls relative to the (regime-dependent)
Thursday/Tuesday expiry weekday. `fixed_dte` holds DTE approximately
constant at 5 by construction, which isolates "does trading more often
help" from "does DTE itself matter" -- if `nearest_weekly`'s results
are driven entirely by its DTE mix rather than by anything about
trading every day per se, `fixed_dte` should look different from
`nearest_weekly`'s DTE=5 bucket in ways that reveal that.

Results are reported per DTE bucket, never pooled, because pooling
would average together trades with fundamentally different time-value
structure (per the research question above) into a single number that
describes none of the underlying trades accurately -- exactly the
mistake this project already flagged and avoided for the event-day
case studies (`src/event_day_study.py`'s own top-of-file warning).

## What happens next

Part 2 of this task downloads every NSE trading day's bhavcopy from
2024-01-01 onward, with no analysis performed. A future task will
build the actual every-day backtest against predictions (a)-(e), using
`src/lot_size.py` for rupee conversion and points as the primary scale,
per `config/everyday_experiment.json`.
