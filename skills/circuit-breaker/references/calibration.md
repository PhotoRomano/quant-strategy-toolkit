# Circuit Breaker Calibration Reference

This document covers structured threshold selection, sensitivity analysis, and out-of-sample
validation for the drawdown pause and EMA correlation gate described in the main SKILL.md.

## Why calibration is the hard part

Choosing parameters by eyeballing a single historical equity curve is almost always wrong.
The curve already happened — fitting to it produces a breaker that fires perfectly on past
events but incorrectly on future ones. The methods below reduce (they cannot eliminate) this
overfitting risk.

## Drawdown threshold selection

### Step 1 — Establish a "natural noise" baseline

Before choosing a pause threshold, measure how much drawdown your strategy produces by
random chance (i.e., drawdowns that recover quickly and are not signals of regime change).
Compute the distribution of all drawdown episodes in your in-sample history, including
episodes that recovered:

```python
def drawdown_episodes(equity_curve: pd.Series, min_depth_pct: float = 1.0) -> pd.DataFrame:
    """
    Returns a table of drawdown episodes with depth, duration, and recovery time.
    Only episodes deeper than min_depth_pct are reported.
    """
    peak    = equity_curve.cummax()
    dd      = (equity_curve - peak) / peak * 100          # negative = drawdown
    in_dd   = dd < -min_depth_pct
    episodes = []
    start = None
    for i, (ts, val) in enumerate(in_dd.items()):
        if val and start is None:
            start = ts
        elif not val and start is not None:
            depth = float(dd.loc[start:ts].min())
            duration = (ts - start).days if hasattr(ts - start, 'days') else i
            episodes.append({"start": start, "end": ts, "depth_pct": depth, "duration_days": duration})
            start = None
    return pd.DataFrame(episodes)
```

Look at the 75th and 90th percentile of episode depth in the episode table. A threshold near
the 75th percentile fires too often (catching noise). A threshold near the 90th percentile
fires rarely and lets the large drawdowns accumulate too long. A reasonable starting region
to explore is between the 75th and 90th percentile of your episode-depth distribution. Test
multiple thresholds in this band; do not pick one number and stop.

### Step 2 — Walk-forward test across at least two market regimes

Split your historical data into at least:
- A parameter-selection window (in-sample, IS)
- A held-out validation window (out-of-sample, OOS)

For each candidate threshold T, compute on IS:
- Number of pauses triggered
- Average pause duration
- Max drawdown with vs. without the breaker
- Return forgone (upside missed while paused)

Then run the *chosen* threshold on OOS only. If the OOS max drawdown reduction is in the
same ballpark as IS, the threshold is plausibly generalizing. If OOS shows no improvement,
the threshold was overfit to the IS regime.

A useful sanity check: if your best IS threshold corresponds to the exact peak-to-trough of
a specific historical crash, you almost certainly fitted to that crash. Prefer thresholds
that are round numbers (e.g., 8%, 10%) rather than suspiciously precise ones (e.g., 7.3%).

### Step 3 — Sensitivity table

Before finalizing, produce a sensitivity table across a grid of thresholds. The format:

| Threshold | IS max-DD | IS pauses | IS return miss | OOS max-DD | OOS pauses |
|-----------|-----------|-----------|----------------|------------|------------|
| 5%        | ...       | ...       | ...            | ...        | ...        |
| 7%        | ...       | ...       | ...            | ...        | ...        |
| 10%       | ...       | ...       | ...            | ...        | ...        |
| 15%       | ...       | ...       | ...            | ...        | ...        |

A well-calibrated threshold shows gradual improvement in max-DD as threshold decreases,
with an increasing cost in missed return. A threshold where max-DD drops sharply and
return miss is low is usually the result of fitting to a single crash.

## EMA span selection

### The fundamental tradeoff

A smaller fast span (e.g., 8) makes the gate more reactive: it fires sooner on trend breaks
but also fires on brief pullbacks in ongoing uptrends (whipsaws). A larger slow span (e.g.,
50 or 200) makes the gate less reactive but means correlated satellites remain open well
into a sustained downtrend before the gate fires.

There is no universally correct span. The right pair depends on:
- The typical trending period of your lead asset
- The frequency of your run loop (intraday vs. daily vs. weekly)
- How long correlated assets tend to remain correlated during drawdowns

### Span selection procedure

1. Compute the cross-correlation between the lead asset and each satellite over your IS
   window at lags 0, 1, 3, and 5 periods. Confirm the correlation is high (> 0.6 at lag 0).
   If it isn't, the EMA gate on the lead asset will not meaningfully predict satellite
   behavior, and a different gate design is needed.

2. For each (fast, slow) pair in a candidate grid, compute:
   - Gate state at each point in time (open or closed)
   - Satellite entries suppressed
   - Would-have-been PnL of suppressed entries

3. Target: suppress entries with *below-average* forward returns without suppressing too
   many entries with *above-average* forward returns. A gate that suppresses entries whose
   forward return distribution is similar to the unconstrained distribution is doing nothing
   useful and only reducing capital deployment.

4. Use OOS to confirm the span pair's filtering quality holds on unseen data.

### Common span choices as starting points (not recommendations)

| Context                | Fast | Slow | Rationale |
|------------------------|------|------|-----------|
| Daily equities         | 50   | 200  | Classic "death cross" pattern for regime breaks |
| Daily equities         | 20   | 50   | More responsive for mean-reversion systems |
| Daily crypto           | 12   | 26   | Adapted from intraday MACD; crypto trends faster |
| Hourly crypto          | 8    | 21   | Common for hourly candle systems |

These are illustrative starting points. Run your own sensitivity analysis.

## Resume condition calibration

The resume condition deserves as much care as the pause condition. An overly eager resume
(fire as soon as EMA crossover occurs) re-enters right into dead-cat bounces. An overly
conservative resume (require full peak recovery) keeps capital sidelined through entire
bull legs.

### Dual-condition resume (recommended)

Require *both*:
1. A minimum recovery fraction (e.g., portfolio value is within X% of the high-water mark)
2. A minimum streak of consecutive periods where fast EMA > slow EMA

The streak requirement means the lead asset must sustain its uptrend, not merely touch the
fast-slow crossover once. A streak of 3-5 daily closes is a reasonable starting band; tune
with the same walk-forward procedure used for the pause threshold.

### Asymmetry principle

It is usually better to err on the side of resuming slightly late than slightly early.
A pause that ends one or two days after the actual bottom costs you small upside. A pause
that ends at a bounce before the second leg down costs you the full second leg. Design for
asymmetry: make the pause condition slightly easier to trigger, the resume condition slightly
harder.

## State persistence checklist

Before deploying:

- [ ] State file (or DB row) is written atomically (write to temp file, rename) to prevent
      corrupt state on crash during write
- [ ] State is read at the top of every run, not cached in memory across runs
- [ ] Peak value is initialized to the first observed portfolio value, not to zero or None
      (zero produces an immediate 100% "recovery" on the first real value)
- [ ] Timestamps are in UTC; convert to local only for display
- [ ] A `PAUSED` state that is older than N days triggers an alert — stale pauses suggest
      the resume condition is too strict or the system stopped running
- [ ] Manual override path exists (you need to be able to force-resume from the command line
      without code edits)

## Interaction effects

The drawdown pause and EMA gate can interact in unexpected ways:

- **Both fire simultaneously:** portfolio is paused AND EMA gate is closed. This is expected
  and correct. All new entries are suppressed. Exits still run.
- **EMA gate fires before drawdown threshold:** satellites are suppressed but the breaker is
  still ACTIVE. The lead asset itself may still enter. This is the intended early-warning
  behavior of the gate.
- **Drawdown recovers but EMA gate remains closed:** the maybe_resume condition requires
  both recovery *and* EMA streak. The resume function should explicitly check the streak,
  not just the portfolio value. Without this, the system resumes into a still-bearish lead
  asset.
- **Lead asset gaps up past slow EMA overnight:** gate re-opens instantly. If your system
  runs intraday, this is fine. If it runs daily, add a confirmation day to avoid acting on
  a single-candle fake breakout.

## Logging requirements

Every circuit breaker event must be logged with:
- Timestamp (UTC)
- Event type: PAUSE_TRIGGERED / RESUME_TRIGGERED / GATE_CLOSED / GATE_OPENED / ENTRY_SUPPRESSED
- Context values: current portfolio value, peak value, drawdown pct, fast EMA, slow EMA
- For ENTRY_SUPPRESSED: the symbol and its individual signal score

Without this log you cannot distinguish "the strategy found nothing today" from "the circuit
breaker suppressed ten valid entries." Operational debugging requires the audit trail.
