# Category Base Rates — Calibration Ledger

This file records your actual hit rates per experiment category. Update it after every
10 completed experiments. The initial values in the table below are illustrative starting
points drawn from general quant research practice — replace them with your own data.

Backtests and calibration data do not predict future live performance.

## What "success" means

Define success *once* and keep it consistent across your ledger. Reasonable choices:

- Average annual return improves by at least X percentage points across all backtest years
- Sharpe ratio improves by at least Y
- No year regresses more than Z percentage points

Document your definition here before you start logging experiments:

```
Success definition: ___________________________________________________
Abort threshold:    ___________________________________________________
```

## Calibration table

| Category | Runs | Successes | Actual hit rate | Avg predicted P | Calibration status |
|----------|------|-----------|----------------|-----------------|-------------------|
| root_cause_fix | 0 | 0 | — | — | no data |
| param_tuning | 0 | 0 | — | — | no data |
| new_signal | 0 | 0 | — | — | no data |
| macro_overlay_targeted | 0 | 0 | — | — | no data |
| universe_expansion | 0 | 0 | — | — | no data |
| new_instrument | 0 | 0 | — | — | no data |
| diagnostic | n/a | n/a | n/a | n/a | n/a |

**Calibration status key:**
- `no data` — fewer than 5 completed experiments in category
- `well-calibrated` — actual hit rate within ±10pp of avg predicted P
- `overconfident` — actual hit rate more than 10pp below avg predicted P
- `underconfident` — actual hit rate more than 10pp above avg predicted P

## How to update this table

After each completed experiment, add one row to the experiment log below. After every
10 experiments, recompute the category totals above.

### Experiment log

| ID | Category | Predicted P | Result | Notes |
|----|----------|-------------|--------|-------|
| — | — | — | — | — |

## Reading the calibration status

**Overconfident on param_tuning** is the most common pattern. If your actual hit rate on
parameter tweaks is below 0.15 but you keep predicting 0.5–0.7, reduce every new
`param_tuning` prediction by 0.2 until the ledger re-converges.

**Root cause fixes deserve higher priors once the mechanism is confirmed.** A fix where
you have identified the specific bug, confirmed it with a diagnostic experiment, and can
point to exact code lines typically succeeds at rates above 0.65. If you are
underconfident here, trust your diagnosis.

**Macro overlay events are highly path-dependent.** A targeted event that addresses a
specific known regime failure (inverse ETF re-entry during a false rally, neutral bleed
into the next year) behaves more like a root cause fix (higher P) than a speculative overlay
addition (lower P). Distinguish between the two in your reasoning field.

## Isolation quality and its effect on predicted P

| Isolation level | Adjustment to predicted P |
|----------------|--------------------------|
| EXCELLENT — one variable, pre/post baseline locked | +0.05 to base rate |
| GOOD — single mechanism, clean baseline | no adjustment |
| FAIR — two related changes, interacting but tracked | −0.10 |
| POOR — multiple mechanisms bundled | −0.20 or split before running |

## EV floor guidance

Suggested minimum EV to run a full backtest (tune these to your own compute budget):

| Run cost | EV floor |
|----------|----------|
| Single-year diagnostic | positive EV not required — diagnostic |
| 3-year partial run | EV > 0 in target metric |
| Full multi-year run | EV > 1pp average annual return equivalent |

Below the floor, redesign the experiment to have a cheaper cheapest-test, improve
isolation, or table the idea until you have a better mechanism hypothesis.
