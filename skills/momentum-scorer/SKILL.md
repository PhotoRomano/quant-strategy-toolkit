---
name: momentum-scorer
description: Design, normalize, and rank a multi-timeframe relative-strength momentum scoring framework for a quantitative strategy — including component selection, score assembly, regime-adaptive thresholds, and ranking-to-entry mechanics. Use this when someone asks "how do I score stocks for momentum", "build a momentum ranking", "relative strength scoring", "how should I weight momentum factors", "my momentum signal isn't ranking well", "what lookback periods matter", "score_threshold_delta", "how do I adjust entry selectivity by regime", or "why does my momentum scorer pick the wrong names". Also use when designing or auditing the scoring layer of a swing-trading or trend-following backtest.
---

# Momentum Scorer

A momentum scorer answers one question at each decision date: *of every candidate currently
eligible, which names have the strongest recent price leadership, adjusted for risk?*

Done well, a momentum scorer does not predict the future — it identifies assets that have
*already demonstrated* sustained relative strength across multiple timeframes, then ranks them
so a position-sizing layer can allocate capital to the top names. Done badly, it picks recent
laggards (buying on hope instead of trend) or blends timeframes inconsistently so a single
spike in one window dominates the ranking.

This skill covers the full design: components, normalization, weighting, relative-strength
computation, regime-adaptive thresholds, and the ranking-to-entry decision. You bring the
weights; this skill gives you the structure and the reasoning behind each choice.

Backtests using any scoring framework — including this one — do not guarantee future
performance. All examples are illustrative starting points, not recommendations.

## The four design decisions

Before writing a line of code, settle these four questions. Every subsequent detail flows
from them.

### 1. Which timeframes, and why?

Momentum is not a single phenomenon. Three distinct horizons capture different signal
sources:

- **Short-term (5-10 trading days):** reacts fastest to catalysts — earnings, sector
  rotation, macro news. High noise-to-signal; useful as a *tiebreaker* between names with
  similar medium-term scores, not as a primary driver.
- **Medium-term (20-30 trading days):** the core trend confirmation window for swing
  trading. Aligns with one monthly cycle of institutional flows. If a name can't show
  strength here, a 5-day spike is usually noise.
- **Longer-term (60-90 trading days):** filters out whipsaws. A stock that is strong at
  all three timeframes is in a sustained trend, not just recovering from an oversold extreme.

Using a single timeframe — say, 20-day return — invites a consistent failure mode: the
scorer picks names that just had one good month but are reversing. Blending three timeframes
adds robustness at the cost of slightly slower response to inflections.

### 2. How do you normalize raw returns into a score?

Raw percent returns are unbounded and skewed by outliers. If a +80% name sits alongside a
+8% name, a linear weight on raw returns lets the outlier dominate. Two approaches:

**Rank-based normalization** converts each timeframe's return into a percentile rank
across the current candidate universe (0.0–1.0 or 0–100). This is outlier-resistant and
well-suited to cross-sectional (relative) momentum. It removes the effect of absolute market
levels — a +3% return in a flat market and a +3% return in a ripping bull get the same raw
rank only if the cross-section is the same, so it naturally encodes relative information.

**Z-score normalization** (subtract mean, divide by std) preserves relative spacing, useful
when the *magnitude* of outperformance matters. More sensitive to outliers; clip at ±3 before
weighting.

Rank-based is easier to reason about in a daily debugging session. Z-score is more common
in academic factor research. Either works; pick one and stay consistent across all components.

See `references/normalization-and-ranking.md` for worked examples of both.

### 3. What is relative strength, and why does it deserve its own component?

Raw timeframe returns rank stocks against each other. Relative strength (RS) goes one step
further: it computes the stock's return *minus the benchmark return* over the same window.

```python
# RS over 20 trading days vs benchmark
rs_20 = stock_ret_20d - benchmark_ret_20d
```

This matters because in a strong bull market, *everything* goes up. A stock with a +12%
20-day return looks great, but if the benchmark is +15%, the stock is actually
underperforming. The RS component separates market beta from genuine stock leadership.

A name with positive RS across multiple timeframes is taking market share from the index
even as the market rises. That is the signal you want to be long.

### 4. How do you handle volatility?

A high-return, high-volatility name is not obviously better than a moderate-return,
low-volatility name. A volatility penalty in the score rewards names that achieve their
returns smoothly (institutional accumulation pattern) vs. choppily (retail speculation).

A simple penalty:

```python
# 10-day realized daily return std
vol = daily_returns[-10:].std()
# Reward lower vol, penalize extreme vol; bound the adjustment
vol_score = max(-15.0, min(15.0, (target_vol - vol) * scale_factor))
```

Set `target_vol` at the typical "well-behaved trend" volatility for your asset class — for
large-cap equities, roughly 1.0–1.5% daily (about 16–24% annualized) is a reasonable
starting point. The exact boundary is something you calibrate through observation, not a
fixed right answer.

## Score assembly

Once you have components, combine them as a weighted sum starting from a neutral baseline:

```python
score = 50.0  # neutral baseline — center of a 0-100 scale
score += ret_60d_normalized * w1   # sustained trend — highest weight
score += ret_20d_normalized * w2   # core swing-trade window
score += ret_5d_normalized  * w3   # short-term catalyst — lowest weight
score += rs_20d             * w4   # relative strength vs benchmark
score += vol_score          * w5   # volatility adjustment
```

The weights express your *theory of the trade*. For swing trading with 30-60 day holds,
a reasonable starting structure weights the 60d window most and the 5d window least —
because a 5-day spike without a prior trend is mean-reversion bait. Typical starting
ratios (not a recommendation — calibrate to your universe):

- 60d: ~35% of total weight
- 20d: ~25%
- RS:  ~15%
- 5d:  ~15%
- Vol: ~10%

You will re-weight based on your actual universe and hold period. Document the theoretical
rationale for each weight you choose, so you can explain it independent of backtest results.
Weights chosen purely to fit historical data are a form of overfit.

## Regime-adaptive thresholds (score_threshold_delta)

A fixed entry score threshold treats bull markets and bear markets identically. That
misses a key piece of signal: the market regime *is itself a momentum signal*. When the
broad market is in a sustained uptrend, lower-scoring names can still ride the trend; when
the market is deteriorating, only the highest-conviction names are worth holding.

The mechanism is a `score_threshold_delta`: an additive offset applied to the base entry
threshold depending on the current regime.

```python
BASE_THRESHOLD = 60          # your neutral-regime minimum score

SCORE_THRESHOLD_DELTA = {
    "bull":    -10,   # more permissive — lower bar; trend lifts weaker names
    "neutral":   0,   # baseline
    "bear":    +15,   # very selective — only the strongest names survive
}

effective_threshold = BASE_THRESHOLD + SCORE_THRESHOLD_DELTA[regime]
# bull  → 50   neutral → 60   bear → 75
```

The numbers above are illustrative. The right values depend on your universe, score
distribution, and position limit. What matters is the *direction and intent*:
- In bull regimes, loosening the threshold lets in more candidates without hurting win rate,
  because the macro tailwind does some of the work.
- In bear regimes, tightening aggressively filters out the names that look like momentum
  leaders but are in fact lagging a falling market — they will eventually roll over.

How to set the delta: run your backtest with different delta values and observe how
entry selectivity changes across regime periods — not just aggregate performance. A delta
that improves aggregate return but does so by fitting one specific crisis is likely to be
an overfit. A robust delta is one that makes intuitive sense (tighter in bear, looser in
bull) and produces better trade quality metrics (win rate, average hold P&L) across
*multiple* regime periods, not just one.

## Worked micro-example: leaky ranking vs correct ranking

**Setup:** three candidates on a single decision date in a neutral regime.

| Symbol | 20d ret | 60d ret | RS 20d | Vol | Raw composite |
|--------|---------|---------|--------|-----|---------------|
| A      | +12%    | +8%     | +5%    | low | 74            |
| B      | +18%    | +3%     | -2%    | med | 68            |
| C      | +6%     | +14%    | +8%    | low | 71            |

B scores second despite having the highest 20-day return, because its 60-day trend is
shallow and its relative strength is negative (the market ran harder). A scores first.
C scores third on the surface but has the strongest relative strength and sustained trend —
worth flagging as a secondary candidate if slot capacity allows.

**The leaky version** (a common mistake):

```python
# Compute returns over entire history, THEN slice to today's ranking
ret_20 = prices_df.pct_change(20).iloc[-1]        # .iloc[-1] = today's whole-frame row
ret_60 = prices_df.pct_change(60).iloc[-1]
score  = 0.5 * ret_20 + 0.5 * ret_60              # no relative strength, no vol
top_names = score.nlargest(4).index.tolist()
```

This has two issues: no relative strength component (will persistently select high-beta
names over leaders), and no volatility penalty (will over-select volatile micro-caps).

**The gated version:**

```python
def score_candidates(prices_df, spy_series, date_str, n_top=4):
    hist = prices_df.loc[:date_str]               # gate ALL data to decision date
    spy  = spy_series.loc[:date_str]

    scores = {}
    for sym in hist.columns:
        col = hist[sym].dropna()
        if len(col) < 62:
            continue

        p   = col.iloc[-1]
        r5  = (p / col.iloc[-6]  - 1) * 100
        r20 = (p / col.iloc[-21] - 1) * 100
        r60 = (p / col.iloc[-61] - 1) * 100

        spy_r20   = (spy.iloc[-1] / spy.iloc[-21] - 1) * 100 if len(spy) >= 21 else 0
        rs_20     = r20 - spy_r20

        vol       = col.pct_change().iloc[-10:].std() * 100   # daily %, last 10d
        vol_score = max(-15.0, min(15.0, (1.2 - vol) * 10))  # illustrative target: 1.2%/day

        score = (50
                 + r60  * 0.35
                 + r20  * 0.25
                 + r5   * 0.15
                 + rs_20 * 0.15
                 + vol_score * 0.10)
        scores[sym] = max(0.0, min(120.0, score))

    return sorted(scores, key=scores.get, reverse=True)[:n_top]
```

The key differences: every slice is gated with `loc[:date_str]`, relative strength is an
explicit component, and volatility is penalized. All three changes together shift the
ranking toward names that are *actually leading the market* on the decision date.

## Ranking to entry

A sorted score list is not the same as an entry decision. The scorer's output feeds a
downstream allocation layer that applies:

1. **Regime-adaptive slot limit** — the max number of simultaneous positions varies by
   regime (fewer in bear, allowing more in neutral/bull to diversify within the trend).
2. **Score threshold gate** — apply `effective_threshold = base + score_threshold_delta[regime]`.
   Only names above the threshold are candidates. This prevents filling slots with weak
   names when the universe is thin.
3. **Conviction-based sizing** — within a slot, position size scales with how far above
   the threshold the score sits. A name at 95/100 gets a larger allocation than a name
   at 62/100.
4. **Cooldown enforcement** — a name that just triggered a stop-loss should not be
   immediately re-entered in bear or neutral regimes, where stop-outs often precede further
   deterioration. Bull regimes may skip the cooldown, since dip-and-recover is a common
   pattern in uptrends.

These mechanics are detailed in the `regime-position-sizing` and `stop-loss-designer`
sibling skills.

## Report structure

When using this skill to review or design a scoring system, produce:

```
# Momentum Scorer Review: <strategy name>

## Score Components
| Component | Window | Normalization | Weight | Rationale |
|-----------|--------|---------------|--------|-----------|
<one row per component>

## Relative Strength Benchmark
<What the benchmark is, why it was chosen, whether it is gated correctly>

## Regime Adaptation
| Regime | score_threshold_delta | Effective threshold | Expected selectivity |
|--------|-----------------------|--------------------|--------------------|

## Identified Issues
<Any component missing, weight unjustified, normalization inconsistency, look-ahead risk>

## Recommendations
<Concrete changes to component list, weights, or threshold mechanics>
```

## When the user wants more

If the scorer is producing unexpected rankings, common diagnoses:

- **Always picks high-beta names:** RS component is absent or underweighted.
- **Misses sustained trends in favor of recent spikes:** 60d weight is too low vs 5d.
- **Over-penalizes volatile names even in bull markets:** vol weight too high relative to
  return weights, or vol scaling factor poorly calibrated.
- **Entry selectivity doesn't change across regimes:** `score_threshold_delta` is set to
  zero or the effective threshold is the same for all regimes.
- **Score distribution is clumped near 50:** normalization is missing (raw returns with no
  centering) — normalize each component before weighting.

For deep detail on normalization choices, cross-sectional vs. time-series momentum, and
ranking stability diagnostics, see `references/normalization-and-ranking.md`.

Pair with the `regime-classifier` skill for regime detection, `regime-position-sizing` for
how scores feed into allocation, and `lookahead-audit` to verify your price and RS data
is correctly gated before each decision date.


<!-- strongskills-brand -->

---

*Made with a StrongSkills tool — The shortcut to the cutting edge · getstrongskills.com*
