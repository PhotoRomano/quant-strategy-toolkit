# Normalization and Ranking Reference

Deep catalog for the `momentum-scorer` skill: worked examples, edge cases, and diagnostics
for score normalization and ranking stability.

## Why normalization matters

A composite momentum score is only as useful as the spread of values it produces. Two
pathologies kill the score's signal before any ranking step:

1. **Clumping near the mean** — raw return differences between candidates are tiny in
   absolute terms, so all scores land within a few points of each other. Small numerical
   errors or data gaps flip the ranking arbitrarily.

2. **Outlier domination** — one component with an extreme value dwarfs all others,
   regardless of the weights. A stock up +80% in 60 days with a terrible vol profile gets
   selected over a stock with clean, consistent leadership across all windows.

Normalization solves both by re-expressing each component in a common unit before weighting.

## Method 1: Rank-based normalization

**Concept:** for each decision date, sort all candidates by component value and replace
each value with its fractional rank in the cross-section (0.0 to 1.0, or 0 to 100).

```python
import pandas as pd

def rank_normalize(series: pd.Series) -> pd.Series:
    """
    Convert a series of raw values (e.g., 20-day returns across all candidates)
    into fractional ranks in [0, 1] for the current cross-section.
    Ties are broken by averaging (method='average').
    NaN candidates receive NaN rank and are excluded downstream.
    """
    return series.rank(method="average", pct=True)
```

Applied per-component at each decision date:

```python
# At decision date D, for all candidates with sufficient history
raw_ret20  = {sym: compute_ret20(sym, D)  for sym in candidates}
raw_ret60  = {sym: compute_ret60(sym, D)  for sym in candidates}
raw_rs20   = {sym: compute_rs20(sym, D)   for sym in candidates}

# Normalize each component to [0, 1]
norm_ret20 = rank_normalize(pd.Series(raw_ret20))
norm_ret60 = rank_normalize(pd.Series(raw_ret60))
norm_rs20  = rank_normalize(pd.Series(raw_rs20))

# Weighted composite (scale to 0-100)
for sym in candidates:
    score[sym] = (
        norm_ret60[sym] * 35
        + norm_ret20[sym] * 25
        + norm_rs20[sym]  * 15
        # ... other components ...
    )
```

**Properties:**
- Outlier-resistant: an +80% outlier gets rank 1.0, same as a +20% leader in a weaker
  universe. Ranking does not amplify extreme values.
- Scores are comparable across different market periods: a score of 80 always means
  "in the top quintile of today's candidates."
- Loses absolute magnitude: a universe where everyone is up 2% looks the same as one
  where everyone is up 15%. This is usually *desirable* for relative momentum but means
  you cannot use the score to judge whether *any* name is worth entering — you still need
  an absolute quality gate.

**When to use:** cross-sectional (relative) momentum, fixed-universe strategies, when
stability across market regimes matters more than raw signal strength.

## Method 2: Z-score normalization

**Concept:** subtract the cross-sectional mean and divide by the cross-sectional standard
deviation. Clip at ±3 to limit outlier impact.

```python
def zscore_normalize(series: pd.Series, clip: float = 3.0) -> pd.Series:
    """
    Z-score normalize a series across the current cross-section.
    Returns NaN if std is zero (all candidates identical) — exclude gracefully.
    """
    mu  = series.mean()
    std = series.std()
    if std < 1e-9:
        return pd.Series(0.0, index=series.index)
    return ((series - mu) / std).clip(-clip, clip)
```

Scale z-scores to a 0-100 composite by centering at 50 and mapping ±3 to ±30:

```python
# z_score is in [-3, 3]; map to approx [20, 80] for each component
contribution = z_score * 10   # 1 std = 10 score points
score += contribution * weight
```

**Properties:**
- Preserves relative spacing: a name 2 std above average contributes proportionally more
  than a name 0.5 std above.
- More sensitive to outliers than rank-based (even after clipping at ±3).
- Easier to interpret when you care about the *magnitude* of outperformance, not just
  the rank (e.g., for position sizing within the top-N names).

**When to use:** when the distribution of returns within your universe is roughly normal,
when you want magnitude-sensitive signals, or when replicating academic factor research
(which typically uses z-scores).

## Comparing the two methods on the same data

| Candidate | 20d raw return | Rank-normalized (pct) | Z-score (clipped ±3) |
|-----------|---------------|----------------------|----------------------|
| A         | +18%          | 0.95                 | +2.1                 |
| B         | +12%          | 0.75                 | +0.9                 |
| C         | +8%           | 0.55                 | +0.1                 |
| D         | -1%           | 0.30                 | -1.2                 |
| E         | +75% (outlier)| 1.00                 | +3.0 (clipped)       |

With rank normalization, E gets 1.00 (top rank), but A gets 0.95 — E's enormous return
does not compress A's relative standing much. With z-score, E clips to +3.0 but the
scale of the outlier still affects every other name's relative contribution because the
z-score is computed relative to the full distribution including E.

**Practical recommendation:** unless your universe naturally has log-normal return
distributions (commodities, crypto), rank normalization is more robust for equity
cross-sections because it is completely insensitive to outlier magnitudes.

## Mixing normalized and raw components

A common mistake is to mix rank-normalized components with raw (un-normalized) additions
in the same weighted sum:

```python
# BUG: mixing scales
score = ret_60d_rank_pct * 35     # 0-35 points from normalized component
      + raw_vol_score             # -15 to +15 points raw
      + sector_boost              # +20 raw if in boosted list
```

The sector_boost and vol_score are both raw, but they are in the same scale as the
normalized components because they are bounded small numbers. This is acceptable *only*
if you have intentionally calibrated the raw terms to be on the same order of magnitude
as the normalized terms. Document this explicitly if you do it — it is a legitimate
design choice, not a bug, but it looks wrong to a reader who expects pure normalization.

The general principle: every additive term in your score formula should be documented
with its expected range and unit. If you cannot state them, the formula has an implicit
scaling assumption that can break when the universe changes.

## Ranking stability diagnostics

After computing scores on a backtest run, check these to validate the ranking quality:

**Score distribution by regime:**

```python
import matplotlib.pyplot as plt

for regime in ["bull", "neutral", "bear"]:
    regime_scores = [s for date, sym, s, r in all_scores if r == regime]
    plt.hist(regime_scores, bins=30, alpha=0.5, label=regime)
plt.legend(); plt.title("Score distribution by regime"); plt.show()
```

A healthy distribution is spread across ~40 points of range within each regime. If all
scores cluster within 5 points, the ranking is essentially random — add stronger
normalization or review whether components are correlated.

**Top-rank churn:**

```python
# Track how often the top-N changes between consecutive decision dates
prev_top = set()
churn_rates = []
for date in decision_dates:
    curr_top = set(top_n_names(date))
    if prev_top:
        churn = 1 - len(curr_top & prev_top) / len(curr_top)
        churn_rates.append(churn)
    prev_top = curr_top
print(f"Mean top-N churn: {sum(churn_rates)/len(churn_rates):.1%}")
```

For a 20-day hold strategy, top-4 churn of 20-30% per rebalance is typical. Churn above
60% suggests the scorer is too noisy (short-window dominated). Churn below 10% suggests
you're not refreshing on new information.

**RS vs raw-return rank correlation:**

If your relative-strength rank and your raw-return rank are highly correlated (Spearman r
above 0.90), the RS component is adding very little independent information — the benchmark
is essentially flat. This is fine in trending markets but means your score isn't adjusting
for regime. Consider whether your RS computation is actually working (check for the date
gating bug shown in SKILL.md).

## Common normalization bugs

**1. Normalizing across the full universe, including candidates without sufficient history.**

A candidate with only 10 days of data receives a 0.0 return for the 60-day component. This
artificially anchors the low end of the rank distribution, inflating every other candidate's
normalized rank. Exclude candidates below the minimum lookback before normalizing.

```python
eligible = {sym for sym in candidates if has_history(sym, date, min_days=62)}
# Normalize only within eligible set; re-join with full list after
```

**2. Re-using yesterday's normalized rank instead of re-computing.**

Normalization is cross-sectional: it depends on *who else is in the universe today*. If the
universe changes (a name is added, or one is excluded due to a fundamental gate), yesterday's
ranks are stale. Always re-compute the full normalization step at every decision date.

**3. Normalizing over the full time-series instead of the current cross-section.**

A time-series percentile ("this name's return is in the 80th percentile of its own
historical returns") is a different signal from a cross-sectional percentile ("this name's
return is in the 80th percentile of today's universe"). Both are valid but they answer
different questions. For relative momentum (which name to prefer over others today),
cross-sectional normalization is correct. For time-series momentum (is this name in an
up-trend vs its own history), time-series percentile is correct. Do not mix them.

## Connecting normalization to regime thresholds

After normalization, your composite score has a known range (e.g., 0–100 with a neutral
baseline of 50). This makes the `score_threshold_delta` interpretable:

- A delta of -10 in bull regime says: "I will accept names down to the 40th-percentile of
  today's distribution rather than the 50th." This is a deliberate loosening.
- A delta of +15 in bear regime says: "I only want names above the 65th percentile
  of today's distribution." High selectivity.

Because rank-normalized scores are consistent across time (a score of 65 always means
roughly "top 35% of today's candidates"), the threshold deltas remain calibrated even when
absolute market returns shift dramatically. This is one reason to prefer rank normalization:
your thresholds do not need to be re-tuned every time volatility spikes.
