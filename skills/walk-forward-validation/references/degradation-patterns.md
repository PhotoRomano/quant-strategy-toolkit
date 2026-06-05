# Walk-Forward Degradation Patterns — Reference Catalog

Detailed reference for interpreting IS/OOS divergence. Each entry: what the pattern looks like
in the per-step table, what it indicates, and how to respond. Read the entry that matches the
shape of your WFV results.

---

## Table of contents
1. Healthy degradation (expected)
2. Curve-fitting signature
3. Regime-shift degradation
4. Parameter-count overload
5. Low-sample noise
6. Monotonic OOS decay
7. IS/OOS ratio heuristic
8. Statistical significance caveats

---

## 1. Healthy degradation (expected)

**What it looks like:**

| Step | IS Return | OOS Return | IS/OOS ratio |
|------|-----------|------------|--------------|
| 1    | +28%      | +14%       | 0.50         |
| 2    | +31%      | +16%       | 0.52         |
| 3    | +26%      | +13%       | 0.50         |

OOS is consistently positive, roughly 40–60% of IS, and the ratio is stable across steps.

**What it means:** The strategy has learned something real. The IS/OOS gap is expected — IS
always looks better because parameters were chosen on it. The stable ratio means the edge is
consistent, not lucky.

**How to respond:** Report the composite OOS numbers as the honest estimate of live-trading
potential. Caveat that OOS ≠ live (transaction costs, slippage, regime drift).

---

## 2. Curve-fitting signature

**What it looks like:**

| Step | IS Return | OOS Return | IS/OOS ratio |
|------|-----------|------------|--------------|
| 1    | +42%      | -8%        | -0.19        |
| 2    | +38%      | +3%        | 0.08         |
| 3    | +45%      | -12%       | -0.27        |

OOS returns are near zero or negative while IS returns are large. IS/OOS ratio is unstable,
near zero, or negative.

**What it means:** The optimizer found parameters that fit the noise in each IS window. The
edge is not real — it is memorization. The strategy will likely lose money live.

**How to respond:**
- Reduce parameter count. More parameters than the IS window can support causes this.
- Increase IS window length relative to number of parameters.
- Simplify the strategy until the IS/OOS ratio stabilizes.
- Do NOT continue to the final holdout — it will not tell you anything different.

---

## 3. Regime-shift degradation

**What it looks like:**

| Step | IS Period    | IS Return | OOS Period | OOS Return |
|------|-------------|-----------|------------|------------|
| 1    | 2017–2019   | +24%      | 2020       | -18%       |
| 2    | 2017–2020   | +19%      | 2021       | +22%       |
| 3    | 2017–2021   | +21%      | 2022       | -31%       |
| 4    | 2017–2022   | +18%      | 2023       | +28%       |

OOS alternates dramatically between large gains and large losses, tracking the market regime
rather than the strategy's edge. IS performance is relatively stable.

**What it means:** The strategy's performance is regime-dependent and the IS window contained
the wrong regime for the OOS period. This is not pure curve-fitting — there may be real edge
within a regime — but the regime detector is either absent or failing.

**How to respond:**
- Add a market-regime gate (bull/bear/neutral classification) and evaluate performance
  conditional on regime.
- Ensure the IS window covers the same regime distribution as the OOS window, or use a rolling
  scheme that naturally includes recent regime shifts.
- Consider separate parameter sets per regime (tuned only on that regime's IS history).

---

## 4. Parameter-count overload

**What it looks like:**

| IS window | Parameters tuned | IS Sharpe | OOS Sharpe |
|-----------|-----------------|-----------|------------|
| 1 year    | 12              | 2.8       | 0.1        |
| 2 years   | 12              | 2.1       | 0.4        |
| 3 years   | 12              | 1.8       | 0.9        |
| 3 years   | 4               | 1.4       | 1.1        |

IS Sharpe falls as the window lengthens (the optimizer has less room to overfit), and OOS
Sharpe rises. Reducing parameter count raises OOS Sharpe even when IS Sharpe drops.

**The rule of thumb:** You need roughly 50–100 independent trade events in the IS window per
free parameter to have a reasonable chance of non-spurious fits. A strategy with 10 parameters
needs 500–1000 trades in the IS window. At typical hold periods of 20–45 days and 5–12 positions,
that is several years of history minimum.

**How to respond:**
- Count independent trade events in the IS window (not days — trades are the unit).
- If events / parameters < 50, simplify the parameter set.
- Prefer higher-level parameters (regime threshold, position size fraction) over lower-level
  ones (per-sector score adjustments) unless the lower-level parameters have a clear theoretical
  justification.

---

## 5. Low-sample noise

**What it looks like:**

| Step | OOS Trades | OOS Return | OOS Sharpe |
|------|-----------|------------|------------|
| 1    | 8         | +18%       | 1.4        |
| 2    | 7         | -12%       | -0.8       |
| 3    | 11        | +22%       | 1.7        |

OOS results swing wildly and are driven by very few trades. The positive steps and negative
steps are equally plausible.

**What it means:** The OOS window is too short or the strategy trades too infrequently to
produce a statistically meaningful result. A single trade in a 1-year OOS window can swing the
annual return by 10–20 percentage points.

**How to respond:**
- Lengthen the OOS window, or run multiple shorter OOS windows and evaluate the distribution.
- Require a minimum trade count per OOS window before treating the result as evidence (a
  common floor: 20+ independent closed trades per OOS window).
- Widen the confidence interval on any reported OOS return. With 8 trades, the 95% confidence
  interval on a 60% win rate is ±34 percentage points — the result is noise.

---

## 6. Monotonic OOS decay

**What it looks like:**

| Step | OOS Period | OOS Return |
|------|-----------|------------|
| 1    | 2020       | +22%       |
| 2    | 2021       | +14%       |
| 3    | 2022       | +4%        |
| 4    | 2023       | -6%        |
| 5    | 2024       | -18%       |

Each successive OOS window is worse than the last, while IS performance remains positive.

**What it means:** The strategy's edge is decaying over time. Possible causes: the market has
adapted to the same signal (crowding), the macro regime has permanently shifted, or the original
IS data contained a one-time event (e.g. 2008–2009 recovery) that boosted apparent IS edge.

**How to respond:**
- Investigate whether the decay is regime-driven (is the most recent OOS window a bear
  market?) or structural.
- If structural, the strategy may need a fundamental redesign, not parameter retuning.
- Do not extend the IS window to include the bad OOS years hoping to "recalibrate" — that
  just moves the problem forward one step.

---

## 7. IS/OOS ratio heuristic

The IS/OOS return ratio is a quick diagnostic. Compute it as OOS return / IS return for each
step (using annualized returns, same sign convention).

| Ratio range       | Interpretation                               |
|-------------------|----------------------------------------------|
| 0.40 – 0.70       | Healthy generalization                       |
| 0.70 – 1.00       | Possibly lucky OOS or IS was conservative    |
| > 1.00            | OOS beat IS — suspicious, check regime       |
| 0.00 – 0.40       | Weak but potentially real; needs more steps  |
| Negative          | Curve-fitting, likely not deployable         |
| Highly variable   | Low-sample noise or regime-shift; diagnose   |

Note: apply this to **Sharpe ratio** rather than raw return when possible, because it adjusts
for the volatility of the OOS period (which may differ from the IS period for structural reasons).

---

## 8. Statistical significance caveats

Walk-forward results are not statistically powerful tests by normal standards. A WFV with 3–5
steps over a 5-year history produces, at most, 5 semi-independent OOS observations. That is
not enough to reject the null hypothesis of "lucky" at conventional significance levels.

This does not make WFV useless — it makes it honest. The correct framing:

- A consistently positive IS/OOS ratio across 4+ steps provides *practical evidence* that the
  strategy is not purely curve-fit.
- It does not constitute *proof* of positive expected value in live trading.
- Every WFV report should include an explicit statement: "These results are consistent with
  [generalizes / curve-fits], but the sample of OOS windows is small. More out-of-sample history
  is the only way to increase confidence."

Live trading, with careful position sizing and real P&L tracking, is ultimately the only true
OOS test. Treat walk-forward validation as a necessary gate before live testing, not a
substitute for it.
