# Regime Classifier — Calibration and Override Reference

This reference covers the two areas where most regime classifiers break down in
practice: choosing thresholds that generalize, and managing the macro-override
table without turning it into a hindsight-labeling exercise.

---

## Threshold calibration

### The over-fitting trap

A score-to-label mapping has three free parameters: the bull threshold, the bear
threshold, and the dead-zone width between them. All three are easy to over-fit
because regime transitions are sparse — a typical ten-year backtest has fewer than
a dozen meaningful bull-to-bear transitions. Fitting thresholds on sparse events
with knowledge of outcomes produces fragile rules that work only on the dates they
were fitted to.

### Walk-forward split

Use the earliest available data as a calibration window and the most recent years
as a held-out test window. A reasonable starting split for a ten-year history is
to use the first seven years to examine threshold candidates and hold the final
three years untouched until evaluation.

Do not search thresholds on the held-out window at any point during development.
Running even a single comparison against held-out results corrupts the estimate.

### What to calibrate

Prefer calibrating for regime coherence (days-in-regime, transitions per year)
rather than optimizing for return directly. Directly optimizing thresholds on
return creates a hidden look-ahead: you are choosing the boundaries that happened
to work in the sample, which is selection bias. Coherence calibration targets
structural properties — a bull regime should not flip to bear and back within a
week; a bear regime should persist for at least a few weeks — that are independent
of forward return.

Sanity checks to run on your calibration window:

| Check | Target (illustrative, tune to your instrument) |
|-------|------------------------------------------------|
| Bull-regime transitions per year | 1–3 |
| Bear-regime transitions per year | 0–2 |
| Minimum regime duration (median) | >= 10 trading days |
| Neutral fraction of all dates | 15–40% |
| % of crash periods correctly labeled bear | Use known historical drawdowns |

If your classifier produces more than 5 bull/bear transitions per year on the index
you are testing, the thresholds are too tight and the classifier is reacting to
noise. Widen the dead-zone (raise the bull threshold, lower the bear threshold) or
add a minimum-duration gate (ignore a transition that reverses within N days).

### Minimum-duration gate

A simple debounce prevents the classifier from toggling on short-lived momentum
reversals. Track the date the regime last changed and require at least N trading
days before accepting a new label. A starting value of 5 trading days is a
reasonable floor; tune upward if you see excessive transitions. This is a
state-dependent filter, not a look-ahead: you are only using information up to the
current date.

```python
def regime_with_debounce(spy_full, decision_date, min_duration=5, state=None):
    """
    state is a dict carried across calls: {"regime": str, "since": str}
    Returns the (possibly held) regime label.
    """
    raw = compute_regime(spy_full, decision_date)
    if state is None or state["regime"] is None:
        state["regime"] = raw["regime"]
        state["since"]  = decision_date
        return raw["regime"]

    days_held = (pd.Timestamp(decision_date) - pd.Timestamp(state["since"])).days
    if raw["regime"] != state["regime"] and days_held < min_duration:
        return state["regime"]   # hold the current label

    state["regime"] = raw["regime"]
    state["since"]  = decision_date
    return raw["regime"]
```

---

## Macro-override management

### When to add an override

Add an override only for events that meet all three of these criteria:

1. **Systemic, not idiosyncratic.** A policy shock, central bank discontinuity, or
   pandemic is systemic. A single company earnings miss is not.
2. **Not already captured by MA + momentum.** Check the computed regime first. If
   the classifier already produces the correct label three or more days before you
   want to add the override, the override is redundant. Redundant overrides are
   not harmful but they inflate the apparent "precision" of the system.
3. **Justifiable in real-time terms.** The override date must correspond to a
   publicly observable event (a Fed announcement, an official declaration, a
   published news report) that a real trader could have acted on that day. If you
   are setting the override date to the exact bottom or the exact peak of a move,
   you have used hindsight in setting the date.

### Override table audit checklist

For each entry in your override table, answer:

- [ ] What specific public event justifies this date (not the return it produced)?
- [ ] Was the date chosen before or after you saw the backtest output at that date?
- [ ] Is there a corresponding clear entry (override=None) when the justification
      for the override expired?
- [ ] Did you test the strategy on a walk-forward window that contains no override
      dates, to verify the computed regime alone is viable?

### Disclosure requirement

In any strategy documentation, performance report, or SKILL output, you must state
explicitly: "The override table contains entries chosen with knowledge of historical
outcomes. These entries are not code leakage but they represent design-level
selection bias. Performance figures that incorporate override dates should not be
extrapolated to future periods without verification that the override logic applies
going forward."

---

## Handling the warm-up period

MA200 requires 200 trading days of history before it is meaningful. Before that
threshold:

- Do not label as bull or bear from MA signals alone.
- Default to neutral with a flag indicating insufficient history.
- Alternatively, use the shorter MA (MA50 alone) for the first 200 days with a
  lower confidence weight, but document this clearly.

```python
if len(spy) < 50:
    return {"regime": "neutral", "score": 50, "insufficient_history": True}
if len(spy) < 200:
    # MA200 not available — reduce weight of above_ma200 component
    # or explicitly cap score contribution
    ...
```

Do not silently fall back to `spy.mean()` as a proxy for MA200 during warm-up
without flagging it — a simple mean of 50 bars is not the same signal as a
200-day MA, and using it invisibly produces misleading early-period regime labels.

---

## Live vs. backtest regime

In a live system the regime is computed once per day (or per bar) against the
current data window, and the result is logged. The architecture is simpler than
the backtest walk-forward because you do not need the `.loc[:D]` slice — you are
always "at D" in real time.

However, keep the function signature identical between live and backtest mode.
Divergence between the live and backtest code paths is a common source of
live/backtest disagreement that has nothing to do with look-ahead bias. A single
implementation with a `decision_date` parameter covers both: in live mode pass
`datetime.today().strftime("%Y-%m-%d")` as the date and pass the full history as
the series.

---

## Sibling skills

- **regime-classifier** — the primary SKILL.md with the full method.
- **regime-position-sizing** — wire the label to concrete position parameters.
- **lookahead-audit** — full temporal-honesty audit of the broader strategy.
- **walk-forward-validation** — held-out evaluation framework.
