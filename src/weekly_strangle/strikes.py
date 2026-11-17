"""Strike selection: % OTM (V1), delta (V2) and iron-condor wings (V4).

Every function here receives option rows through data.rows_as_of(), so it can only
see prices dated on or before the entry day (`as_of`).

Definitions used throughout:
  % OTM for a call = strike / spot - 1        (e.g. 0.07 = 7% above spot)
  % OTM for a put  = 1 - strike / spot        (e.g. 0.10 = 10% below spot)
  Eligible strike  = traded on the entry day (volume >= 1) with close >= 0.05.
"""

import functools
import math

from .data import rows_as_of


def pct_otm(strike, spot, option_type):
    """How far out of the money a strike is, as a fraction of spot."""
    if option_type == "CE":
        return strike / spot - 1
    return 1 - strike / spot


def eligible_chain(rows, as_of, labels, option_type, min_volume=1, min_close=0.05):
    """Eligible contracts of one type, for one expiry, priced on the entry day `as_of`."""
    rows = rows_as_of(rows, as_of)
    same_day = rows[rows["trade_date"] == as_of]
    chain = same_day[same_day["expiry_label"].isin(labels) & (same_day["type"] == option_type)]
    chain = chain[(chain["volume"] >= min_volume) & (chain["close"] >= min_close)]
    return chain.copy()


def select_pct_otm(chain, spot, option_type, target, max_closer):
    """V1: the eligible strike whose % OTM is closest to `target`.

    A strike may not be more than `max_closer` closer to spot than the target
    (calls >= 5%, puts >= 8% for the primary values). Ties go to the further-OTM strike.
    Returns (row or None, explanation text).
    """
    if chain.empty:
        return None, "no eligible strike on the entry day"
    chain = chain.copy()
    chain["otm"] = [pct_otm(k, spot, option_type) for k in chain["strike"]]
    floor = target - max_closer
    allowed = chain[chain["otm"] >= floor - 1e-12]
    if allowed.empty:
        return None, f"no eligible strike at or beyond {floor:.2%} OTM"
    allowed = allowed.assign(distance=(allowed["otm"] - target).abs())
    # closest to target first; on a tie, the larger % OTM (further from spot) wins
    allowed = allowed.sort_values(["distance", "otm"], ascending=[True, False])
    best = allowed.iloc[0]
    why = (f"closest eligible strike to the {target:.0%} OTM target among {len(allowed)} strikes "
           f">= {floor:.0%} OTM; its % OTM is {best['otm']:.4%}")
    return best, why


def normal_cdf(x):
    """Standard normal cumulative distribution, using the error function."""
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def black_scholes_price(spot, strike, years, vol, option_type):
    """Black-Scholes option price with r = 0 and no dividends (pre-registration V2)."""
    if years <= 0 or vol <= 0:
        if option_type == "CE":
            return max(0.0, spot - strike)
        return max(0.0, strike - spot)
    d1 = (math.log(spot / strike) + 0.5 * vol * vol * years) / (vol * math.sqrt(years))
    d2 = d1 - vol * math.sqrt(years)
    if option_type == "CE":
        return spot * normal_cdf(d1) - strike * normal_cdf(d2)
    return strike * normal_cdf(-d2) - spot * normal_cdf(-d1)


def black_scholes_delta(spot, strike, years, vol, option_type):
    """Black-Scholes delta with r = 0: N(d1) for a call, N(d1) - 1 for a put."""
    d1 = (math.log(spot / strike) + 0.5 * vol * vol * years) / (vol * math.sqrt(years))
    if option_type == "CE":
        return normal_cdf(d1)
    return normal_cdf(d1) - 1


@functools.lru_cache(maxsize=None)
def implied_vol(price, spot, strike, years, option_type, low=1e-4, high=5.0, tolerance=1e-8):
    """Volatility that makes the Black-Scholes price equal `price` (bisection).

    Returns None when no volatility between `low` and `high` fits (the strike is then dropped).
    Results are remembered (the same inputs always give the same answer).
    """
    if years <= 0:
        return None
    if not (black_scholes_price(spot, strike, years, low, option_type) <= price
            <= black_scholes_price(spot, strike, years, high, option_type)):
        return None
    for _ in range(200):
        mid = (low + high) / 2
        if black_scholes_price(spot, strike, years, mid, option_type) < price:
            low = mid
        else:
            high = mid
        if high - low < tolerance:
            break
    return (low + high) / 2


def select_delta(chain, spot, option_type, years, target, accept_low, accept_high):
    """V2: the eligible strike whose |delta| is closest to `target`, within [accept_low, accept_high].

    IV is solved from each strike's entry close. Strikes with no IV solution are dropped.
    Ties go to the further-OTM strike (Step 6 decision D7). Returns (row or None, text).
    """
    if chain.empty:
        return None, "no eligible strike on the entry day"
    records = []
    for _, row in chain.iterrows():
        vol = implied_vol(float(row["close"]), float(spot), float(row["strike"]), float(years), option_type)
        if vol is None:
            continue
        delta = abs(black_scholes_delta(spot, row["strike"], years, vol, option_type))
        records.append((row, vol, delta))
    inside = [r for r in records if accept_low <= r[2] <= accept_high]
    if not inside:
        return None, f"no strike with |delta| in [{accept_low}, {accept_high}] ({len(records)} IVs solved)"
    inside.sort(key=lambda r: (abs(r[2] - target), -pct_otm(r[0]["strike"], spot, option_type)))
    row, vol, delta = inside[0]
    row = row.copy()
    row["iv"] = vol
    row["abs_delta"] = delta
    return row, f"|delta| {delta:.4f} closest to {target} (IV {vol:.4f}, {len(inside)} strikes in range)"


def select_wing(chain, short_strike, option_type, wing_points, tolerance_points):
    """V4: the long wing W points beyond the short strike.

    Candidates: eligible strikes within W +/- tolerance points beyond the short strike.
    Choice: nearest to exactly W points away; ties go further out (decision D6).
    Returns (row or None, text).
    """
    if chain.empty:
        return None, "no eligible wing strike on the entry day"
    chain = chain.copy()
    if option_type == "CE":
        chain["distance"] = chain["strike"] - short_strike
    else:
        chain["distance"] = short_strike - chain["strike"]
    near = chain[(chain["distance"] >= wing_points - tolerance_points) &
                 (chain["distance"] <= wing_points + tolerance_points)]
    if near.empty:
        return None, f"no eligible wing within {wing_points} +/- {tolerance_points} points"
    near = near.assign(miss=(near["distance"] - wing_points).abs())
    near = near.sort_values(["miss", "distance"], ascending=[True, False])
    best = near.iloc[0]
    return best, f"wing {best['distance']:.0f} points beyond the short strike (target {wing_points})"
