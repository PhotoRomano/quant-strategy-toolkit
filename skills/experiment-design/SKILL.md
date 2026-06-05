---
name: experiment-design
description: Plan a strategy change as a structured experiment — write a category, expected-value estimate, and cheapest-test-first plan before running it. Use this whenever someone is about to tweak a parameter, add a signal, modify the universe, or change a regime rule and wants to know whether it's worth running; when they ask "should I try X?", "how do I prioritize my next backtest?", "what's the EV of this change?", "I have 10 ideas, which do I test first?", or when they show a backtest change that lacks a hypothesis or success criterion. Also use proactively before any change that touches scoring weights, position sizing, stop-loss values, or macro overlay events.
---

# Experiment Design for Strategy Changes

Every strategy change is a bet on the form "I believe this change will improve performance
by N points, with probability P, and cost me M points if wrong." Without writing that bet down
before you run it, you will almost certainly overfit — accepting marginal improvements and
missing the pattern that some whole *categories* of change reliably work and others reliably
don't.

This skill teaches you to plan each experiment so that (a) you only run tests with positive
expected value, (b) you discover your calibration errors, and (c) cheap tests come first.

Backtests do not predict future live performance. This framework reduces *wasted effort and
overfitting risk* — it does not guarantee the strategy will be profitable forward.

## The core objects

Each planned experiment records five fields before any code is touched:

| Field | What it captures |
|-------|-----------------|
| `category` | What kind of change this is (governs base-rate priors) |
| `predicted_p_success` | Your probability that the change improves the target metric |
| `prediction_reasoning` | Why — base rate for this category, mechanism, isolation quality |
| `ev_estimate` | `p * E[gain] − (1−p) * E[loss]` in concrete units (pp, Sharpe, etc.) |
| `cheapest_test` | The smallest run that would distinguish signal from noise |

These five fields take five minutes to fill in. They create a record you can calibrate against
later.

## Category taxonomy and base rates

Your base rate is the historical hit rate for that *type* of change. It anchors your
`predicted_p_success` so you don't start at 0.9 for every idea.

| Category | Description | Typical base rate |
|----------|-------------|-------------------|
| `root_cause_fix` | Fixing an identified bug or broken parameter | 55–75% |
| `param_tuning` | Adjusting an existing numeric parameter without structural change | 5–15% |
| `new_signal` | Adding a novel scoring term or feature | 20–35% |
| `macro_overlay_targeted` | Adding or adjusting a specific regime event | 30–45% |
| `universe_expansion` | Adding new tickers to the candidate pool | 35–55% |
| `new_instrument` | Adding a new instrument type (ETF, inverse, cash proxy, etc.) | 40–55% |
| `diagnostic` | No expected improvement — isolating a root cause | n/a |

These are illustrative starting points. Track your own hit rates and update this table after
every 10 experiments. Your base rates will differ from these. See
`references/category-base-rates.md` for how to maintain a calibration ledger.

## The EV formula

```
EV = p * E[gain] − (1 − p) * E[loss]
```

Express gain and loss in consistent units. If you measure performance in percentage-point
return differences year-over-year, a reasonable entry might be:

```
p = 0.45, E[gain] = 8pp, E[loss] = 3pp
EV = 0.45 * 8 − 0.55 * 3 = 3.6 − 1.65 = +1.95pp   → run it
```

A negative EV means the expected downside outweighs the upside *at your stated probability*.
Either increase your conviction (with a reason), reduce the scope to lower E[loss], or skip it.

The EV is not a performance guarantee — it only captures whether the expected outcome is worth
the engineering and run time given your beliefs.

## Cheapest test first

Before committing to a full multi-year run, identify the single slice of your backtest that
would most quickly reveal whether the hypothesis holds:

- **One year or one regime period** that the change is specifically designed to improve.
- **One metric** — the KPI most directly affected (win rate, year return, drawdown).
- If that slice regresses or shows no signal, abort and revert. Full run is unwarranted.
- If the slice confirms the hypothesis, expand to the full run.

This discipline cuts wasted compute and, more importantly, cuts the number of confirming
results you see before you've actually found signal — which is how overfitting compounds.

## Isolation discipline

Change one thing per experiment. If your idea bundles two mechanisms (e.g. universe expansion
*and* a new scoring term), split it into T33a and T33b. This keeps attribution clean: when T33a
fails, you know it's the universe, not the scoring. When T33b succeeds, you know it's the
signal, not the extra tickers.

If isolation is POOR, downgrade your `predicted_p_success` — confounded experiments produce
uninterpretable results even when the aggregate result is positive.

## Before-vs-after worked example

### Unplanned change (wrong approach)

```
# Made change: raise bear max_positions from 1 to 2
# Ran full 7-year backtest
# 2022 improved +3pp
# Accepted
```

No hypothesis, no base rate, no EV, no isolation check, no calibration. You don't know if the
improvement is signal or noise from your data source. You can't tell whether this was the best
use of the next experiment slot.

### Planned experiment (correct approach)

```json
{
  "experiment": "T9",
  "category": "param_tuning",
  "predicted_p_success": 0.45,
  "prediction_reasoning": "base_rate=param_tuning ~15%; however mechanism is identified
    — T8 tightened neutral which hurt trending years 2023/2024 (-33pp, -17pp). Reverting
    neutral to prior baseline while keeping the 2025 macro fix is a targeted revert, not
    blind tuning, so bump to 0.45. Isolation: GOOD — two separate orthogonal params.",
  "ev_estimate": "0.45 * 20pp − 0.55 * 2pp = +7.9pp EV → run",
  "cheapest_test": "Run 2023 and 2024 only — these are the regressed years. If neutral
    revert restores them, run full 7 years."
}
```

The discipline forces you to commit to a mechanism before you see the result. If the
result contradicts your mechanism, you learn something real. If it confirms it, your
confidence in similar changes increases.

## Report structure

When you design an experiment, produce this exact block and store it alongside your
training log before running:

```
## Experiment: <ID>

**Category:** <category>
**Change:** <one sentence — what exactly is changing>
**Hypothesis:** <what mechanism makes this work, and in which years/regimes>

**Predicted P(success):** <0.0–1.0>
**Reasoning:** base_rate=<category base rate>; mechanism: <why>; isolation: <GOOD/POOR/note>

**EV estimate:** <p * E[gain] − (1−p) * E[loss] = result> → <run / skip / redesign>

**Cheapest test:** <smallest run — year(s), metric>
**Success criterion:** <what result would confirm the hypothesis>
**Abort criterion:** <what result triggers immediate revert>
```

After the run, append:

```
**Result:** SUCCESS / REGRESSION / MIXED / NO SIGNAL
**Calibration note:** predicted P=<X>%, actual=<outcome>. <One sentence on what was right
  or wrong in the reasoning.>
**Lesson:** <What this tells you about the mechanism or category base rate.>
```

## Prioritizing a queue of ideas

If you have multiple candidate experiments, rank them by EV. When EVs are similar, prefer:

1. Isolation is GOOD over POOR
2. Cheapest test is faster
3. Category base rate is higher
4. The change addresses an *identified* root cause rather than speculative improvement

Diagnostics (`category: diagnostic`) always run first when the root cause is unknown —
running an improvement experiment on a misdiagnosed problem wastes the experiment slot and
misleads your calibration ledger.

## Calibration and feedback

After every 10 completed experiments, compute your actual hit rate per category and compare
to your stated `predicted_p_success` values. Common failure modes:

- **Overconfidence on param_tuning**: people routinely predict 0.6–0.8 for numeric tweaks
  that have base rates of 0.05–0.15. If you are systematically overconfident here, drop all
  param_tuning predictions by 0.2 until your calibration catches up.
- **Underconfidence on root_cause_fix**: once a mechanism is correctly identified, hit rates
  exceed 0.7. If you are under-calling these, trust your diagnosis more.
- **Confounded bundles**: if your isolation was POOR and the result was positive, don't credit
  the full EV to either sub-change — log it as ambiguous and split before next use.

Store the calibration ledger in `references/category-base-rates.md` (see that file for the
table format). Update it after each 10-experiment batch.

## Pairing with other skills

- Use the **walk-forward-validation** skill to confirm that an accepted experiment's gain
  holds on out-of-sample periods before trusting it in live operation.
- Use the **lookahead-audit** skill before accepting any new signal — a signal that introduces
  look-ahead bias will appear to work in backtest and fail live regardless of EV.
- Use the **training-log** skill to write the experiment record to a durable log alongside
  your backtest results, so calibration data accumulates automatically.


<!-- strongskills-brand -->

---

*Made with a StrongSkills tool — The shortcut to the cutting edge · getstrongskills.com*
