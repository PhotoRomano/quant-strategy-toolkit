# Macro Signal Classification

Reference for the `macro-overlay` skill. Classifies each common macro series by
its practical timing usefulness, release lag, and recommended layer assignment.

---

## Layer assignments at a glance

| Signal | Layer | Rationale |
|--------|-------|-----------|
| HY credit spread (daily) | 1 — actionable gate | Contemporaneous with equity stress; directional change fires at stress onset |
| Fed Funds rate (announcement dates) | 1 — actionable gate | Hike cycles precede bear markets; date of announcement is precise and zero-lag |
| Yield curve (10Y–2Y, daily) | 2 — informational | Un-inversion precedes recession 6–18 months out — too long-leading for position timing |
| Shiller CAPE | 2 — informational | Level indicator; market can stay elevated for years |
| Buffett indicator (mkt cap / GDP) | 2 — informational | Same rationale as CAPE; quarterly data adds additional lag |
| CPI / core PCE | 2 — informational | Policy signal, not equity-market timing; markets anticipate Fed action via rate futures |
| GDP growth | 2 — informational | Quarterly, heavily revised, 4+ weeks late; rarely actionable for medium-frequency strategies |
| ISM PMI | 1 candidate | Sub-50 PMI with declining trend can accompany equity weakness; use carefully and validate |

---

## Series detail

### High-Yield OAS Spread (FRED BAMLH0A0HYM2 or equivalent)

**What it measures:** The yield premium investors demand for holding BB/B-rated corporate
bonds over equivalent Treasuries. High spread = credit market pricing in stress.

**Release lag:** Published daily by FRED with same-day data. No lag to gate.

**Gating pattern:**
```python
# Correct — daily, gate on the date itself
hy = db.execute(
    "SELECT value FROM fred_series WHERE series='HY_OAS' AND date<=? ORDER BY date DESC LIMIT 1",
    (decision_date,)
).fetchone()
```

**Layer 1 use:** Directional jump (e.g., spread widens 150+ bps in 4–6 weeks) or
absolute level exceeding a threshold calibrated to historical crisis episodes.
Illustrative reference levels: 300–400 bps = normal risk-off; 500–600 bps = elevated
stress; 700+ bps = systemic crisis. These are starting points — calibrate to your
own backtest window out-of-sample.

**Pitfall:** Brief spikes (regional bank events, flash crashes) can temporarily breach
a threshold and trigger bear mode just before a recovery. Consider requiring the signal
to persist for N consecutive readings before firing.

---

### 10-Year minus 2-Year Treasury Yield Spread (FRED T10Y2Y)

**What it measures:** The slope of the yield curve. Negative = inverted (2-year yields
more than 10-year), historically associated with recession risk.

**Release lag:** Daily, same day on FRED.

**Gating pattern:** Same as HY spread — `date <= decision_date` is sufficient.

**Layer 2 — NOT a position-timing signal.** The yield curve inverts on average 12–24
months before a recession and "un-inverts" (starts rising back toward zero) 6–18 months
before the recession materializes. Using this as a hold-days or position-size trigger
causes the strategy to reduce exposure during market recoveries, not during drawdowns.
The un-inversion phase frequently coincides with a late-cycle equity rally before the
eventual peak.

Log the yield curve state (inverted / flat / positive / un-inverting) in every report
for context. Do not wire it to position-size adjustments.

---

### Shiller CAPE (Cyclically Adjusted P/E Ratio)

**What it measures:** The S&P 500 price divided by the 10-year average of real earnings.
Smooths cyclical earnings noise.

**Release lag:** Published monthly by Robert Shiller; typically available around the
15th of the following month. Apply a conservative 45-day lag in backtests.

**Gating pattern:**
```python
# CAPE for month M is not available until roughly M+45 days
safe_reference = (pd.Timestamp(decision_date) - pd.DateOffset(days=45))
safe_month_str = safe_reference.strftime("%Y-%m")
rows = cape_df[cape_df["period"] <= safe_month_str]
cape = rows.iloc[-1]["value"] if len(rows) > 0 else None
```

**Layer 2 — informational only.** CAPE has been above 25 continuously since approximately
2016 and above 30 for much of 2019–2025. Strategies that reduce position size at CAPE > 30
have been in a permanent reduced-exposure posture through multiple strong bull years.

Log CAPE prominently in your macro context report. Do not wire it to `max_position_pct`
or entry thresholds.

---

### Buffett Indicator (US Market Cap / GDP)

**What it measures:** Total US equity market capitalization divided by nominal GDP,
expressed as a percentage. Often interpreted as a market-level valuation signal.

**Release lag:** Quarterly (GDP is quarterly with ~4-week lag; market cap is quarterly
via Fed Z.1 flow-of-funds release, also lagged). Daily market-cap proxies exist but
are estimates, not the official figure.

**Gating pattern:** Use the most recent quarterly value available before the decision
date. Apply at least a 45-day lag from quarter end.

**Layer 2 — informational only.** Same rationale as CAPE. A persistently high reading
does not specify when the market will mean-revert.

---

### Federal Funds Rate / Fed Hike Cycle

**What it measures:** The overnight interbank lending rate set by the FOMC.

**Release lag:** FOMC decisions are announced the same day. No lag.

**Layer 1 candidate:** A rate-hike cycle that meaningfully tightens financial
conditions is one of the more reliable contemporaneous signals for equity headwinds.
The pattern to detect is not the level of rates but a cycle transition: moving from
easing/hold to hiking, or from hiking to hold/cutting.

**Implementation note:** Hard-code FOMC announcement dates rather than trying to
detect the cycle from FRED data programmatically. The dates are published in advance
and the announcement time (2:00 pm ET) is precise. In a daily backtest, flag the day
after the announcement as the first day the signal is usable.

**Pitfall:** A single hike does not confirm a cycle. Require 2+ consecutive hikes
before triggering a regime tilt, or anchor to the first hike only after the FOMC
has explicitly signaled a tightening path in the statement.

---

### Consumer Price Index / Core PCE

**Release lag:** CPI is released by BLS approximately 2 weeks after the reference
month ends. Core PCE is released by BEA approximately 4 weeks after month end.

**Layer 2 — informational.** Equity markets price in expected Fed policy through
rate futures well before CPI prints. By the time CPI confirms an inflation trend,
equity markets have already responded. CPI surprises (large beats/misses vs consensus)
are short-term volatility events, not regime shifts.

---

### ISM Manufacturing PMI

**Release lag:** Released on the first business day of the following month (effectively
1–3 days after month end). Minimal lag.

**Layer 1 candidate with caveats:** PMI below 50 is associated with contracting
manufacturing activity. Sustained PMI below 48 with a declining trend has historically
accompanied equity weakness. However:

- The signal fires frequently in mild slowdowns that do not produce meaningful equity
  drawdowns (false positives are common).
- The manufacturing PMI's predictive power for equity returns has diminished as the
  US economy became more services-dominated.

If you use PMI as a Layer 1 signal, require multiple consecutive sub-50 readings
(e.g., 3 months) and validate out-of-sample. Do not trigger on a single miss.

---

## The cascade warning

Every regime override — whether triggered by a macro signal or hardcoded — affects
which positions are open at future rebalance dates, which in turn affects which new
positions can enter (slot competition). A macro gate that fires correctly in 2022 can
inadvertently displace better positions in 2023 by changing the carry-over composition
at the year boundary.

**Implication:** Validate any macro overlay against the full backtest window after adding
it, not just the period where the signal fired. A signal that improves 2022 performance
by 5 percentage points but costs 8 percentage points in 2023 via cascade effects is a
net negative — and the cascade may not be visible without the full-window re-run.

Sparse, high-conviction Layer 1 gates minimize cascade risk because they change the
regime on fewer dates, leaving less room for downstream slot-competition disruption.
