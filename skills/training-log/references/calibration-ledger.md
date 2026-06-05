# Calibration Ledger: Tracking Prediction Accuracy Over Time

This reference shows how to build and use a calibration ledger for your
experiment journal. The purpose is to measure whether your `predicted_p_success`
estimates are accurate — and if not, in which direction you are biased.

## Why calibration matters

If you consistently assign 0.70 probability to experiments that succeed only
30% of the time, you are wasting compute on low-quality ideas and miscalculating
EV on future proposals. A calibration ledger surfaces this bias concretely so
you can correct it.

## Ledger format

Maintain a running table in your spreadsheet companion (e.g., `training-log.xlsx`
on a "Calibration" sheet) with one row per completed experiment that had a
`predicted_p_success` value:

| Experiment | Category | Predicted P | Outcome | Outcome Binary |
|---|---|---|---|---|
| T08 | param_tuning | 0.55 | REGRESSION | 0 |
| T09 | root_cause_fix | 0.65 | SUCCESS | 1 |
| T14 | param_tuning | 0.50 | SUCCESS | 1 |
| T22 | new_instrument | 0.35 | MIXED | 0.5 |
| T27 | macro_overlay | 0.60 | REGRESSION | 0 |
| T28 | root_cause_fix | 0.70 | SUCCESS | 1 |
| T32a | root_cause_fix | 0.72 | REGRESSION | 0 |
| T33 | new_signal | 0.40 | MIXED | 0.5 |
| T34 | new_signal | 0.55 | REGRESSION | 0 |
| T35 | new_signal | 0.45 | REGRESSION | 0 |

`Outcome Binary`: 1 = SUCCESS, 0 = REGRESSION/REVERTED, 0.5 = MIXED/inconclusive.

## Computing calibration by bucket

Group predictions into buckets (e.g., 0.30–0.50, 0.50–0.70, 0.70–0.90) and
compare stated probability to observed success rate in each bucket:

| Predicted P range | N | Avg predicted P | Observed success rate | Bias |
|---|---|---|---|---|
| 0.30–0.50 | 5 | 0.40 | 0.30 | Slightly overconfident |
| 0.50–0.70 | 8 | 0.58 | 0.38 | Overconfident |
| 0.70–0.90 | 4 | 0.73 | 0.25 | Significantly overconfident |

In this example, the researcher should recalibrate: stated 0.70 confidence
in a category should probably be stated as 0.40 given observed outcomes.

## Category-level base rates

Track base rates separately per category, because confidence should vary by
experiment type:

| Category | N | Success rate | Suggested prior for next |
|---|---|---|---|
| root_cause_fix | 6 | 0.50 | 0.45–0.55 (unless mechanism is confirmed diagnostic) |
| param_tuning | 5 | 0.40 | 0.35–0.45 |
| new_signal | 7 | 0.28 | 0.25–0.35 |
| macro_overlay | 4 | 0.38 | 0.30–0.45 (hindsight risk keeps this lower) |
| diagnostic | N/A | Always run | N/A — not a success/fail category |

Use these observed rates as your prior when filling in `predicted_p_success`
for the next experiment in a given category. Your personal estimates can nudge
from the category base rate based on isolation quality and mechanism confidence,
but should not deviate dramatically without strong justification.

## The calibration review ritual

Every 10–15 completed experiments, run this checklist:

1. Pull all entries with `predicted_p_success` from TRAINING_LOG.jsonl.
2. Assign `Outcome Binary` for each (1 / 0.5 / 0).
3. Update the bucket table and category table above.
4. If any category shows observed rate more than 20pp below stated rate,
   adjust your default prior downward for that category.
5. If isolation quality (`isolation: GOOD` vs `isolation: POOR` in prediction
   reasoning) correlates with better calibration, apply an isolation discount
   to poorly-isolated experiments automatically.

## Mechanism tracking: why predictions fail

Calibration alone tells you how wrong you are. Mechanism tracking tells you
why. When an experiment fails, annotate the `calibration` field with which
part of the reasoning chain broke down:

- **Mechanism wrong** — the causal story was incorrect. The change had the
  opposite effect, or no effect at all.
- **Mechanism right, context wrong** — the change works in the predicted
  direction in some market regimes but not others (e.g. a momentum signal
  that works in stable bull markets but hurts in crash-recovery years).
- **Isolation failed** — a second, uncontrolled change was responsible for
  the outcome (positive or negative).
- **Data artifact** — the result was driven by a data source inconsistency,
  not by the hypothesis being tested.

Over time, the frequency of each failure mode tells you where to improve your
experimental design. Isolation failures suggest you are bundling too many
changes. Context-wrong failures suggest you need regime-conditional testing.
Data artifact failures suggest a data quality audit.

## Worked calibration narrative

After 20 experiments, a researcher notices:

- Their `new_signal` category has a 27% observed success rate against a
  stated average of 0.48.
- All three `root_cause_fix` successes had `isolation: GOOD` in the
  prediction reasoning; all four failures had `isolation: POOR`.
- Two experiments were reverted because of "mechanism right, context wrong"
  — both were momentum signals that worked in trending years and failed
  in rotation years.

Conclusions they apply going forward:

1. Lower the `new_signal` prior to 0.30 by default.
2. Never assign P > 0.50 to a `root_cause_fix` unless isolation is confirmed
   GOOD (diagnostic run completed first).
3. Test momentum signals on a rotation year (e.g., value-dominant or
   crash-recovery period) as the cheapest first check, not a trending year.

This is how the calibration ledger compounds research quality over time.
