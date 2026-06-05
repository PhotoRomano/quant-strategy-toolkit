# Kelly Sizing — Math Reference

Companion to `SKILL.md`. Read this when you need confidence intervals on win rates,
multi-period Kelly extensions, or want to reason more rigorously about sample requirements.

---

## Confidence intervals on a win rate

A win rate is a proportion estimated from `n` binary outcomes. Its sampling uncertainty
is real and directly affects the Kelly fraction you should use. Use Wilson score intervals
rather than the naive normal approximation — Wilson is more accurate at both tails and
at small `n`.

**Wilson 95% confidence interval:**

```
center = (wins + z²/2) / (n + z²)
margin = z * sqrt(wins*(n-wins)/n + z²/4) / (n + z²)

lower_p = center - margin
upper_p = center + margin
```

Where `z = 1.96` for 95% confidence.

**Practical use:** compute the Kelly fraction at the *lower bound* of the confidence
interval rather than at the point estimate. This is "conservative Kelly" and is a
principled alternative to the flat half-Kelly rule. With small `n`, the lower bound
may be so low that Kelly recommends no bet — which is the honest answer.

Example: 17 wins out of 28 trades, `z = 1.96`:

```
p_hat  = 17/28 = 0.607
center = (17 + 1.92) / (28 + 3.84) = 18.92 / 31.84 = 0.594
margin = 1.96 * sqrt(17*11/28 + 0.96) / 31.84 = 0.166

p_lower = 0.594 - 0.166 = 0.428
p_upper = 0.594 + 0.166 = 0.760
```

Using `p_lower = 0.428` with the same payoff ratio `b = 1.647`:

```
f* = (0.428 * 1.647 - 0.572) / 1.647 = (0.705 - 0.572) / 1.647 = 0.081
f_half = 0.04   (4% of portfolio)
```

Vs. the point-estimate result of 18.5% unclamped. The confidence interval does the
work the clamp was doing, and more informatively.

---

## How many trades does Kelly actually need?

As a rough rule: to distinguish a 60% win rate from 50% at the 95% confidence level,
you need approximately 200 trades. At 20 trades, the 95% interval around a 60% observed
rate spans roughly 40pp (±20pp), which includes both "no edge" and "strong edge."

| Observed win rate | Trades for 95% CI to exclude 50% |
|-------------------|------------------------------------|
| 0.55              | ~900                               |
| 0.60              | ~220                               |
| 0.65              | ~100                               |
| 0.70              | ~57                                |
| 0.75              | ~35                                |

This is why `min_trades = 20` is a *minimum safety gate*, not an evidence threshold.
At 20 trades you are gating out the worst noise (3-for-3 flukes); you are not yet
confident in the estimate. The multiplier ceiling (max_mult) provides the second line
of defense until the sample matures.

---

## Geometric mean vs. arithmetic mean

The Kelly fraction optimizes the geometric mean growth rate of the portfolio, not the
arithmetic mean. This matters because of the "volatility drag" effect:

```
Geometric mean ≈ Arithmetic mean - (Variance / 2)
```

A strategy with 60% average arithmetic return but 40% standard deviation has roughly
`0.60 - 0.40²/2 = 0.52` geometric return. Over-sizing increases variance, which
reduces geometric return even as it increases arithmetic expected value. This is why
full Kelly can produce spectacular short-term runs followed by catastrophic drawdowns
that the arithmetic P&L never warned about.

Half-Kelly roughly halves both the expected geometric gain *above flat* and the variance
above flat. For most strategies and risk tolerances, that is the right trade.

---

## Multi-period Kelly (continuous compounding approximation)

When positions overlap (e.g. you hold 4 positions simultaneously), the Kelly fractions
are not simply additive. Each simultaneously-held position competes for the same capital.

A practical approximation for `k` simultaneous positions:

```
f_per_position ≈ f_half_single / sqrt(k)
```

This is not exact (the exact solution requires a joint probability model of all positions)
but it captures the key insight: as you concentrate multiple positions, each individual
Kelly fraction should shrink. Running 5 simultaneous positions with a 2x multiplier each
is not the same risk as running one.

Alternatively: apply the Kelly multiplier to your per-position budget cap (not the total
portfolio), where the budget cap already incorporates the regime max_positions limit. This
is the simplest safe approach.

---

## Kelly on non-binary outcomes (continuous return distribution)

The discrete formula `f* = (pb - q) / b` assumes every win is `+b` and every loss is
`-1`. Real trade returns have a distribution. The continuous-return Kelly fraction is:

```
f* = μ / σ²
```

Where `μ` is the mean return per trade and `σ²` is the variance. This is the log-normal
approximation and is more appropriate when win/loss magnitudes vary widely across trades.

**When to use this vs. the discrete formula:**
- If your average win is consistently ~1.5x your average loss (payoff ratio stable), the
  discrete formula is fine.
- If payoff ratios vary more than 3x across trades (e.g. some wins are 50% and some are
  2%), use the continuous approximation.

```python
import numpy as np

def kelly_continuous(returns: list[float]) -> float:
    """
    Kelly fraction from a list of per-trade return percentages.
    Returns the full-Kelly fraction; halve for production use.
    """
    r = np.array(returns) / 100.0   # convert pct to decimal
    mu = np.mean(r)
    sigma2 = np.var(r)
    if sigma2 == 0:
        return 0.0
    return mu / sigma2
```

---

## Decay and recency weighting

Historical win rates from 3 years ago may not reflect current edge. If market conditions
or strategy behavior have shifted, older trades should contribute less to the Kelly estimate.

Exponential recency weighting:

```python
def weighted_win_rate(trades: list[dict], half_life_trades: int = 50) -> float:
    """
    Win rate weighted by recency. Trades `half_life_trades` ago count half as much.
    `trades` must be in chronological order (oldest first).
    """
    import math
    decay = math.log(2) / half_life_trades
    total_weight = 0.0
    weighted_wins = 0.0
    for i, t in enumerate(trades):
        age = len(trades) - 1 - i   # 0 = most recent
        w = math.exp(-decay * age)
        total_weight += w
        if t["return_pct"] > 0:
            weighted_wins += w
    return weighted_wins / total_weight if total_weight > 0 else 0.5
```

Use `half_life_trades = 30–100` depending on how fast you expect the edge to evolve.
For most systematic strategies a half-life of 50–100 trades is reasonable. Shorter
half-lives make the estimate more adaptive but noisier.

---

## Red flags that make Kelly inputs untrustworthy

1. **Win rate > 75%** on more than 30 trades: rare in liquid markets. Likely look-ahead
   bias or survivorship. Audit the backtest before using the number.
2. **Zero recorded losses**: model has never been in a bear regime, or stop-losses were
   not triggered in the sample period. The `b` ratio is undefined. Treat as thin sample.
3. **Win rate computed on in-sample backtest**: the strategy was *trained* on the same data
   it is reporting win rates from. This always overstates edge. Kelly from in-sample win
   rates will oversize.
4. **Win rate computed per-sector or per-regime bucket with n < 15**: even within-regime
   Kelly requires meaningful sample size. Flag as "insufficient" and fall back to flat
   within that regime.
