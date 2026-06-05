# Attribution Patterns Reference

This file catalogs common patterns found during performance attribution and how to
interpret each one. Use it when a pattern in the year-by-year or regime tables needs
a deeper read.

---

## Pattern 1 — The Single-Year Pillar

**What it looks like:** Remove the best year and the compounded return turns flat
or negative.

**Why it matters:** A strategy whose entire multi-year edge lives in one calendar
year has not demonstrated that the edge is persistent. If that year corresponded
to an unusual macro event, a sector that ran once, or a regime that is unlikely to
recur in the same form, the expectation of forward repetition is low.

**How to test it:** Compute the compounded return twice — once with all years, once
excluding the single best year. If the gap between the two figures is larger than
the average annual return across the remaining years, the single-year dependence is
material.

**Honest framing:** State this explicitly in the report: "The strategy's positive
compound return depends on [year X]. Excluding it, the remaining years
show [flat / negative / modest positive] results."

---

## Pattern 2 — The Single-Asset Carrier

**What it looks like:** One name accounts for a disproportionate share of profit.
The exclusion test shows its removal drops the total return by more than the per-name
expected share (e.g., for a 20-name universe, each name's "fair share" is roughly 5%;
a name accounting for 20%+ of total return is above-weight).

**Why it matters:** If the strategy claims to be a diversified momentum or quality
screener but one name is carrying the result, the diversification is cosmetic. The
real bet is concentrated in that name. If the strategy is deployed live and that name
underperforms or is not in the universe at the right time, the performance profile
changes dramatically.

**How to test it:** Run the backtest with the top contributor excluded. If a second
name now becomes the dominant contributor, the strategy has a structural tendency
toward concentration regardless of which specific name is on top. Check this for the
top two or three names.

**Honest framing:** "Asset X contributed approximately Y pp of the total Z-year
return. Its exclusion reduces the compounded return by approximately [delta]. This
represents a concentration risk that should be monitored in live deployment."

---

## Pattern 3 — Bear-Regime Bleed

**What it looks like:** The regime breakdown shows negative returns in bear conditions
despite the strategy claiming bear protection (e.g., inverse ETFs, reduced sizing,
tighter stops).

**Common causes:**
- The regime detector identifies the bear too late (lags by days or weeks after the
  regime has already cost money).
- Bear posture uses inverse instruments that themselves have timing and decay risks
  (especially leveraged instruments held through volatile counter-rallies).
- Position sizing in bear regime is not materially different from bull, so the
  "protection" is theoretical rather than operational.

**How to identify the lag problem:** Compare the date of the first significant drawdown
in a bear year to the date the strategy's regime detector switched to bear. If the switch
happened after the bulk of the drawdown, the detector is reactive rather than anticipatory.

**Note on inverse ETFs:** Strategies that rotate into short or inverse instruments in
bear regimes need to account for counter-rally risk. A strong bear trend interrupted
by a multi-week relief rally can generate large losses in 2x or 3x inverse products.
Shorter average hold periods in bear posture reduce this exposure but also reduce
the capture of the trend.

---

## Pattern 4 — Win Rate / Return Disconnect

**What it looks like:** A moderate or even low win rate (e.g., 40–50%) co-exists
with a positive total return because a small number of large winners dominate.

**Why it matters:** This pattern is not a flaw if it is by design (a trend-following
strategy explicitly relies on asymmetric payoffs). It is a flaw if the strategy was
designed to have balanced wins and the skew is coming from a few lucky oversized
positions.

**How to distinguish them:**
- Compute the average winner magnitude and average loser magnitude separately.
  A healthy payoff-ratio strategy has average winners that are 2x or more the average
  loser.
- If the win rate is below 50% and the payoff ratio is less than 2:1, the strategy
  is negative-EV on an average-trade basis and is relying on a few outliers.

**Honest framing:** If the disconnect is structural and intentional, say so: "The
strategy earns through a small number of large winners; this is expected for a momentum
approach." If it appears accidental, flag it: "Win rate is [X%] and the payoff ratio
is [Y:1], which implies [positive / negative] average trade EV. The total return depends
on [Z large trades]. Without those, the result is [describe]."

---

## Pattern 5 — Narrow Breadth Coincidence

**What it looks like:** The strategy's best years coincide closely with years when
the RSP-SPY divergence is strongly negative (equal-weight significantly underperforms
cap-weight), indicating narrow mega-cap market leadership.

**Why it matters:** A momentum or scoring strategy that naturally gravitates toward
large-cap technology names will look outstanding during periods of narrow breadth
because it is, effectively, running a concentrated mega-cap bet while appearing to
be a diversified system. When breadth normalizes and leadership rotates to mid-caps
or other sectors, the same strategy may structurally underperform.

**How to test it:** Annotate the year-by-year table with the RSP-SPY trailing
one-year divergence at year-end. Look for correlation between divergence level and
strategy performance. A correlation above 0.6 suggests the strategy's edge is
partially or largely explained by narrow breadth conditions.

**Honest framing:** "The strategy's strongest years (e.g., [year A], [year B])
coincide with periods of narrow market breadth (RSP underperforming SPY by
approximately [X pp]). In years when breadth was healthier, returns were [describe].
This does not disqualify the strategy but suggests that the forward return distribution
will vary with the breadth environment."

---

## Pattern 6 — Parameter-Regime Coupling

**What it looks like:** Performance degrades sharply whenever the regime detector
overrides or parameters change mid-year, but the year that benefited most from a
specific macro event cannot be reproduced without that event's settings.

**Why it matters:** This indicates that performance is sensitive to how regime
transitions are defined. If the date of a regime shift is chosen in hindsight (even
informally — "it seemed like the market changed around that time"), the attribution is
describing a backfitted label, not a repeatable signal.

**Note:** This is a design-bias disclosure, not a code bug. The strategy may be
perfectly time-gated in code and still rely on manually selected event dates that
could only have been chosen with knowledge of how the market resolved. Call it out
in the attribution report under the "honest story" section. Pair this with the
look-ahead-audit skill if there is any ambiguity about whether event dates are truly
prospective.

---

## Computing the regime breakdown in code

```python
import pandas as pd

def regime_breakdown(trades: list[dict]) -> pd.DataFrame:
    """
    trades: list of dicts with at least:
      - regime_at_entry: "bull" | "neutral" | "bear"
      - pnl_pct: float
      - won: bool
    Returns a summary DataFrame grouped by regime.
    """
    df = pd.DataFrame(trades)
    grouped = df.groupby("regime_at_entry").agg(
        trades=("pnl_pct", "count"),
        win_rate=("won", "mean"),
        avg_return=("pnl_pct", "mean"),
        total_pnl=("pnl_pct", "sum"),
    )
    grouped["win_rate"] = (grouped["win_rate"] * 100).round(1)
    grouped["avg_return"] = grouped["avg_return"].round(2)
    grouped["total_pnl"] = grouped["total_pnl"].round(2)
    return grouped
```

The `total_pnl` column summed across regimes is the arithmetic total return across
all trades (not compounded). Divide each regime's contribution by the total to get
the percentage of total return attributed to each condition.

---

## Marginal-contribution exclusion test

```python
def asset_marginal_contribution(
    run_fn,          # callable(excluded_symbol) -> float  (returns compound return)
    baseline_return: float,
    universe: list[str],
) -> dict[str, float]:
    """
    Run the backtest N+1 times: once with all assets (baseline),
    then once per asset with that asset excluded.
    Returns dict: symbol -> (baseline_return - excluded_return).
    Positive = the asset contributed positively; negative = it dragged.
    """
    deltas = {}
    for sym in universe:
        excl_return = run_fn(excluded_symbol=sym)
        deltas[sym] = round(baseline_return - excl_return, 2)
    return dict(sorted(deltas.items(), key=lambda x: abs(x[1]), reverse=True))
```

This is the most expensive attribution step (N backtests). For large universes,
prioritize by running the exclusion test only on names that appear in the top 20%
of trade frequency or top 20% of total PnL contribution first.
