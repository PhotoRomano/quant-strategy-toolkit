# Experiment Ledger: Tracking Trials and Correcting for Multiple Testing

## Why this matters

Every time you run a backtest with a different parameter set, choose the best
result, and discard the rest, you are implicitly conducting a multiple-comparison
test. The chance that at least one trial beats a threshold purely by chance grows
rapidly with the number of trials. With 20 independent trials and a 5% false
positive rate per trial, there is a ~64% chance that at least one trial looks
significant by luck.

The standard response in statistics is a multiple-testing correction. In
quantitative strategy development, the practical equivalent is the experiment
ledger — a log that records every trial so the correction can be applied, and so
a reader can see what was tried, not just what was kept.

## What to log for every trial

Keep a structured log (CSV or JSON) with at minimum:

| Field | Description |
|-------|-------------|
| trial_id | Sequential integer, never reused |
| date_run | When the trial was executed |
| parameter_set | Full dict of all tunable values |
| universe_version | Which universe was active |
| train_start / train_end | Date range used to compute results |
| return_on_capital | Final figure for this trial |
| sharpe | If computed |
| max_drawdown | If computed |
| win_rate | If computed |
| note | Why this trial was run, what hypothesis it tested |
| kept | Boolean — whether this became the live configuration |

The `note` field is the most important and most often omitted. It forces you to
state the hypothesis *before* observing the result, which is the only way to
distinguish genuine reasoning from retrospective rationalization.

## Applying a correction

### Bonferroni (conservative, simple)
If you ran K trials and want to claim significance at level α, require each
individual trial to meet α/K. If you want a 5% false discovery rate and ran
30 trials, each trial must hit p < 0.0017.

For backtests, translate this as: the minimum acceptable Sharpe ratio or return
should scale up with the number of trials. A rough guide from Harvey et al. (2016)
suggests requiring a minimum t-statistic of approximately 3.0 after 100+ trials
(versus 1.96 for a single uncorrected test).

### Deflated Sharpe Ratio (Bailey & Lopez de Prado)
The Deflated Sharpe Ratio (DSR) is a closed-form correction that accounts for:
- The number of trials
- Non-normality of returns
- The length of the backtest

The formula estimates the probability that the observed Sharpe exceeds the
expected maximum from random trials. A DSR below 0.5 means there is less than
50% chance the strategy has genuine edge after accounting for the trial count.

Approximate DSR calculation (simplified):

```python
import numpy as np
from scipy.stats import norm

def deflated_sharpe(sr_observed, sr_trials, n_trials, n_observations,
                    skew=0.0, kurt=3.0):
    """
    sr_observed:   Sharpe ratio of the best trial (annualized)
    sr_trials:     array of Sharpe ratios from all trials (or just the best and median)
    n_trials:      total number of trials run
    n_observations: number of return observations in the backtest
    skew, kurt:    return distribution shape (use 0.0, 3.0 for normal assumption)
    """
    # Expected maximum Sharpe from random trials (Extreme Value Theory)
    gamma = 0.5772  # Euler-Mascheroni constant
    sr_expected_max = (
        (1 - gamma) * norm.ppf(1 - 1/n_trials) +
        gamma * norm.ppf(1 - 1/(n_trials * np.e))
    )
    # Adjust sr_expected_max for non-normality (skew/kurt correction)
    sr_star = sr_expected_max * np.sqrt(
        (1 - skew * sr_expected_max + (kurt - 1)/4 * sr_expected_max**2)
        / n_observations
    )
    # DSR = probability that observed SR > sr_star (i.e., beats random expectation)
    z = (sr_observed - sr_star) * np.sqrt(n_observations - 1)
    return float(norm.cdf(z))
```

A DSR > 0.95 is strong evidence the strategy is not purely noise-fitted. A DSR
< 0.5 means the observed performance is consistent with random trial selection
and should not be trusted.

### The practical threshold test

If you cannot or will not compute DSR, apply this simpler check:

1. Sort all trials by return (or Sharpe). Find the median.
2. Ask: "Is the median trial acceptable as a live strategy?"
3. If yes: the strategy has genuine signal that shows up across most parameter
   settings. The best trial is a reasonable upper bound.
4. If no: the strategy only looks good at the optimized point. The median trial
   reveals the underlying signal quality.

## Universe versioning

Each universe change is a new degree of freedom. Log universe versions with:

| Field | Description |
|-------|-------------|
| version | Sequential identifier |
| date_locked | When this universe was finalized |
| change | What was added or removed |
| rationale | The rule or criterion used to make the change |
| test_period_overlap | Whether the change was made after observing results in the test period |

The last field is the honesty check. A universe change made *before* the relevant
backtest period is legitimate experimentation. A change made *after* observing
that a name dragged down returns, or that removing it improved the number, is
hindsight selection and must be disclosed.

## Event override versioning (regime/date tables)

The same principle applies to any dated override table. Log:

| Field | Description |
|-------|-------------|
| event_date | The date being overridden |
| override_value | The regime or parameter being set |
| added_in_trial | Trial ID when this override was introduced |
| trigger_rule | The systematic rule (if any) that could reproduce this in real time |
| real_time_trigger_available | Boolean — can this be replicated live without hindsight? |

An event override with `real_time_trigger_available = False` contributes to
design bias. It is not necessarily wrong, but it is not reproducible forward
and the backtest performance during that period is an upper bound, not an estimate.

## How to use this log in the anti-overfit audit

When running the anti-overfit audit, request the experiment ledger and:

1. Count the total trials. Apply the Bonferroni or DSR correction.
2. Compare the reported figure to the median trial. Report both.
3. Check each universe change for test-period overlap.
4. Check each event override for a real-time trigger rule.
5. If the ledger does not exist, state that: the number of trials is unknown,
   no correction can be applied, and the reported figure should be treated as
   a potentially heavily-selected maximum rather than a stable estimate.

## A note on the cascade effect

In regime-switching strategies, a parameter or override change in one period can
affect results many months later through slot competition — which positions are
open at a given date determines what can be entered next. This means:

- A "small" override in January can change which names are held in June.
- Testing a change against a single year may miss cascading effects in other years.
- The correct test for any parameter change is always the full multi-year period,
  not just the period the change was intended to affect.

This cascade property makes overfitting detection harder: a change that looks
locally beneficial may be globally coincidental, having improved one period by
accidentally displacing a loser from a later period. The only defense is full
multi-year evaluation of every change, logged in the experiment ledger.
