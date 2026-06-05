---
name: macro-overlay
description: Layer macro regime signals (yield curve, credit spreads, valuation ratios) onto a quantitative backtest with correct release-date gating, so the engine never reads a data point before it was publicly available. Use this when someone asks "how do I add macro filters to my backtest", "should I reduce position size when CAPE is high", "how do I gate FRED data in a walk-forward", "my macro overlay makes the backtest worse — why", "how do I use HY spread as a regime signal", or whenever a strategy uses any macro series (Fed funds rate, yield curve, GDP, CPI, credit spreads) as an input to entry/exit decisions or position sizing. Also use proactively before deploying any macro-aware strategy live, or when investigating why a macro-filtered backtest underperforms a pure-price strategy.
---

# Macro Overlay

Adding macro signals to a backtest is one of the most common ways to introduce **two distinct and compounding errors**: look-ahead bias on the data itself, and strategy-design bias from choosing thresholds with hindsight. This skill teaches you how to overlay macro regime signals correctly — with real release-date gating — and explains a hard-won lesson: **valuation ratios are not timing signals**.

This skill pairs naturally with the `lookahead-audit` skill (verify temporal gating) and the `regime-classifier` skill (price-based regime detection).

## Why macro overlays fail in practice

A macro overlay promises to reduce drawdowns by cutting exposure when the environment is hostile. In practice, most implementations fail for one of three reasons:

1. **Release-lag leak.** Macro series describe a reference period but are published weeks or months later. Using the June CPI reading on June 1 is impossible — it is released in mid-July. Gating on the reference period date rather than the publication date leaks the future.

2. **Valuation-as-timing trap.** Metrics like Shiller CAPE, price-to-book, or the Buffett indicator (market cap / GDP) measure *level* richness, not *directional* timing. A market can stay expensive for a decade. Reducing position size every time CAPE exceeds a fixed threshold causes systematic underinvestment during the most productive years of a bull market. **Use valuation signals for informational context, not for position reduction.**

3. **Cascade effects from regime overrides.** Changing the regime on one date ripples forward through all subsequent position-slot competition. A macro override that looks beneficial in isolation can displace better positions 3–5 months later. This means macro overlays should be sparse, high-conviction, and well-validated across the full backtest window — not frequent adjustments.

## The two-layer architecture

A correct macro overlay has two independent layers:

```
Layer 1 — Hard regime gate (credit stress)
  Triggered by credit market signals that historically precede drawdowns.
  High HY spread → force neutral or bear.
  This fires rarely (a few times per decade) and is directionally actionable.

Layer 2 — Informational context (logged, no action)
  Valuation ratios, yield curve shape, Buffett indicator.
  Logged for context and human review, never used to scale positions.
```

The key design decision is which signals belong in Layer 1 vs Layer 2. The guide in `references/signal-classification.md` covers the full catalog.

## Step 1 — Build the release-date table

Before writing a single line of overlay code, build a table mapping each macro series to its **publication lag**, not its reference period:

| Series | Reference period | Typical release lag | Gate field to use |
|--------|-----------------|--------------------|--------------------|
| CPI | Monthly | ~2 weeks after month end | `release_date` |
| GDP (advance) | Quarterly | ~4 weeks after quarter end | `release_date` |
| FRED BAMLH0A0HYM2 (HY spread) | Daily | Same day | `date` (daily, minimal lag) |
| FRED T10Y2Y (yield curve) | Daily | Same day | `date` (daily, minimal lag) |
| Shiller CAPE | Monthly | Published mid-following-month | `as_of_month + 15 days` |
| Fed Funds rate | Meeting dates | Announced same day | `announcement_date` |

Daily series from FRED (yield curve, credit spreads) have effectively no release lag and can be gated on the data date itself. Monthly series like CAPE should be treated as unavailable until roughly the 15th of the following month.

## Step 2 — Gate every series correctly in the walk-forward

The correct pattern for any time-series macro input is `<= D` on the **publication date**, not the reference period date:

**Leaky version — gates on reference period:**
```python
# WRONG: CAPE for June is not available on June 1
cape = cape_df.loc[cape_df["reference_month"] <= decision_date, "value"].iloc[-1]
```

**Correct version — gates on publication date with lag offset:**
```python
# CAPE published around the 15th of the following month
# Apply a conservative 45-day lag to be safe
cape_available_date = decision_date - pd.DateOffset(days=45)
cape = cape_df.loc[cape_df["reference_month"] <= cape_available_date, "value"].iloc[-1]
```

For FRED daily series, the database query itself enforces the gate:
```python
def get_value_on_date(series: str, decision_date: str) -> float | None:
    """Return the most recent available value on or before decision_date."""
    row = db.execute("""
        SELECT value FROM fred_series
        WHERE series = ? AND date <= ? AND value IS NOT NULL
        ORDER BY date DESC LIMIT 1
    """, (series, decision_date)).fetchone()
    return float(row[0]) if row else None
```

The SQL `date <= ?` clause is the gating mechanism. Note that it returns the most recent value **on or before** the decision date — this is the correct point-in-time lookup pattern. An empty result means the series wasn't yet available; treat it as "no signal" rather than defaulting to a value that was only knowable later.

## Step 3 — Implement the credit spread gate

High-yield (HY) credit spreads are the best single macro signal for forced regime changes. When credit markets are stressed, equity risk premiums are elevated and drawdowns become more likely. The gate is directional, not valuation-based, and fires on absolute spread levels that historically coincide with systemic stress:

```python
def get_forced_regime(decision_date: str) -> str | None:
    """
    Returns 'bear', 'neutral', or None.
    Thresholds are illustrative starting points — tune to your own history.
    """
    hy_spread = get_value_on_date("HY_OAS_SERIES", decision_date)
    if hy_spread is None:
        return None  # no data available yet — do not default to stressed

    # Example thresholds (illustrative; tune with your own backtest)
    if hy_spread > 700:   # crisis-level stress
        return "bear"
    if hy_spread > 500:   # elevated stress, not yet crisis
        return "neutral"
    return None
```

The thresholds above are **illustrative starting points you must tune**. Historical crisis peaks vary — the 2008 crisis hit ~2000 bps; COVID spiked to ~1100 bps briefly; the 2022 rate cycle peaked near ~600 bps. A threshold tuned specifically to those events is hindsight-biased. Use the full available history, hold out recent years, and validate out-of-sample.

## Step 4 — Wire the overlay into the backtest loop

The overlay runs once per decision date, before entry scoring. The forced regime from Layer 1 overrides the computed price-based regime; Layer 2 signals are logged only:

```python
for decision_date in rebalance_dates:
    # 1. Compute price-based regime (MA crossover, momentum, VIX proxy)
    computed_regime = compute_regime(price_series, decision_date)

    # 2. Apply macro Layer 1 — credit spread gate
    forced_regime = get_forced_regime(decision_date)
    regime = forced_regime if forced_regime is not None else computed_regime

    # 3. Log Layer 2 signals — informational only, no position effect
    cape_value = get_cape_as_of(decision_date)
    log_macro_context(decision_date, cape_value, regime)

    # 4. Run entry/exit logic with final regime
    params = REGIME_PARAMS[regime]
    ...
```

This separation keeps the overlay auditable: you can inspect logs to see when Layer 1 fired and how often it changed the regime relative to the price-based signal alone.

## The CAPE lesson (and why it matters)

The Shiller CAPE ratio has been above 25 continuously since roughly 2016. Strategies that reduce position size when CAPE exceeds a fixed threshold (say, 30 or 35) have been in a permanent drawdown-reduction posture for nearly a decade — through the 2019 +31% SPY year, 2021 +27%, and 2024 +23%. The systematic underinvestment across those years typically dwarfs the drawdown savings in the one or two correction years the CAPE signal might have partially flagged.

**The test to apply:** Is your signal a *level* indicator or a *directional change* indicator?

- CAPE at 35 vs 28 tells you about relative richness — but the market can sustain elevated CAPE for years. Level is not timing.
- HY spread jumping from 300 bps to 600 bps in 6 weeks tells you credit markets are pricing in stress *now*. Directional change is timing.

Log valuation ratios prominently in your output report for context. Reserve regime overrides for directional credit-market signals that have historically been contemporaneous with equity drawdowns, not predictive in a multi-year leading sense.

## Step 5 — Validate sparsity

A macro overlay that fires frequently is a strategy unto itself, and a poorly backtested one. Count how many decision dates the Layer 1 gate actually changed the regime relative to the price-based signal alone. If that number is large, the overlay is doing most of the work — and it is probably overfit to specific historical episodes.

A rule of thumb: forced regime changes should represent no more than 5–10% of total decision dates over a multi-year backtest. If the overlay is firing more than that, the thresholds are too sensitive and will likely over-trigger in live trading.

## Output format

When implementing or auditing a macro overlay, produce this report for every backtest run:

```
# Macro Overlay Report: <strategy name> <backtest period>

## Layer 1 — Forced regime changes
| Date | Signal | Value | Forced regime | Computed regime (would have been) |
|------|--------|-------|--------------|-----------------------------------|
<one row per date where Layer 1 fired>

## Layer 2 — Informational signals (no position effect)
<Summary of CAPE / Buffett / yield-curve state at backtest start and end>

## Sparsity check
<Number of decision dates where Layer 1 changed the regime / total decision dates>

## Release-lag audit
<For each macro series used: lag applied, earliest date used, verification that no value
was used before its publication date>

## Impact analysis
<Strategy return with overlay vs without; max drawdown comparison>
```

## A worked micro-example

**Setup:** A backtest runs weekly from 2019 to present. The strategy uses HY spread as a regime gate and CAPE for context.

**Leaky version — uses wrong date field:**
```python
# WRONG — gates on the period the spread *describes*, not when FRED published it
# FRED updates BAMLH0A0HYM2 daily with same-day data, so this specific example
# works — but the pattern is dangerous when applied to monthly series like CAPE
cape_row = cape_df[cape_df["period"] == decision_date[:7]].iloc[0]
cape = cape_row["value"]  # period is "2021-06" but CAPE for Jun isn't out until mid-July
```

**Correct version — explicit lag on monthly series:**
```python
# Apply 45-day lag to be conservative (CAPE published ~mid following month)
safe_date = (pd.Timestamp(decision_date) - pd.DateOffset(days=45)).strftime("%Y-%m")
cape_rows = cape_df[cape_df["period"] <= safe_date]
cape = cape_rows.iloc[-1]["value"] if len(cape_rows) > 0 else None
```

This 45-day lag ensures you never use a CAPE reading before it was publicly available. For FRED daily series (yield curve, HY spread), the `date <= decision_date` SQL gate is sufficient because FRED publishes them same-day.

## Honesty caveat

Macro overlays that look compelling in backtest frequently disappoint live because the specific stress episodes that triggered Layer 1 are now part of the training history. A backtest that correctly gates COVID (Feb 2020) and the 2022 rate cycle is not evidence the same thresholds will catch the next drawdown trigger — which will look different. Validate out-of-sample, keep thresholds sparse, and never use macro signals to claim a strategy is "protected" from drawdowns.

## When to go deeper

If you need a full catalog of macro series, their lag characteristics, and code patterns for each, see `references/signal-classification.md`. That reference also covers the yield curve un-inversion pattern and why it is too long-leading to use as a position-timing signal (historically 6–18 months before recession onset — far too long to act on for a medium-frequency equity strategy).


<!-- strongskills-brand -->

---

*Made with a StrongSkills tool — The shortcut to the cutting edge · getstrongskills.com*
