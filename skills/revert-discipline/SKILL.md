---
name: revert-discipline
description: Decide whether to keep or revert a strategy experiment after observing its backtest results. Use this whenever an experiment "helped one year but broke another", a change made things worse overall, you are wondering "is this regression real or noise?", "should I revert?", "the 2023 improvement isn't worth the 2020 collapse", "data changed and my baseline is stale", or "I'm not sure if this change is additive". Also use proactively before committing any parameter change to a multi-year baseline — reversion criteria should be defined before results are read, not after.
---

# Revert Discipline

Every experiment that looks like an improvement in isolation can still be net negative across
the full evaluation window. The job of this skill is to give you a clear, repeatable framework
for deciding *before* you look at results whether a change should be kept — and a clean process
for reverting when it should not.

Backtests reflect historical patterns. No reversion decision implies future profitability. Use
this framework to maintain the integrity of your experimental record, not as a substitute for
forward validation.

## Why a discipline matters

The most dangerous moment in strategy research is right after you see a good number: the temptation
is to keep the change because it helped *this* year, even when you can see it hurt others. Without a
pre-defined reversion standard, you accumulate a strategy shaped by whichever years happened to look
best during development — which is a form of in-sample selection bias that doesn't survive out-of-sample.

An equally dangerous moment is reverting too quickly based on a single-year regression that is inside
the noise band of your data source. The goal is a clear, written test that makes both errors obvious.

## Framework

### Step 1 — Write your hypothesis and success criteria before you run

Before touching code, record three things:

1. **The change and its theory** — what you are changing and the mechanism by which it should help
   (e.g. "reduce hold days in the neutral regime to recycle capital faster during choppy markets").
2. **The primary years under test** — which year(s) this change is specifically designed to improve.
3. **Acceptance criteria** — a written rule, for example:
   - "Primary year improves by at least X pp"
   - "No other year regresses more than Y pp"
   - "Net effect across all years is positive by at least Z pp/yr on average"

Write these down before running. Reading the results first and then defining acceptance criteria
defeats the purpose entirely.

A useful template:

```
Experiment: <ID>
Change: <one-line summary>
Mechanism: <why this should work>
Primary target: <year or metric>
Accept if: <primary year +>= X pp AND no other year regresses >= Y pp
Reject if: any single year regresses >= Y pp OR net avg < Z pp/yr
```

### Step 2 — Classify the result

When results come back, classify them immediately into one of four categories:

| Category | Pattern | Action |
|----------|---------|--------|
| **Clear win** | Primary year improves, no meaningful regression elsewhere | Keep |
| **Mixed / marginal** | Some years improve, some regress; net avg is near zero | Revert (see below) |
| **Partial win** | Strong primary improvement, isolated regression in one year | Diagnose before deciding |
| **Regression** | Primary year fails to improve OR net effect is negative | Revert immediately |

"Marginal" is not a keep. Marginal means the change added complexity and noise without a net benefit.
The baseline already paid the cost of that complexity; the experiment did not earn it back.

### Step 3 — Diagnose the partial-win case before reverting

When one year clearly benefits and one year clearly regresses, don't revert blindly. First ask:

- **Is the regression in a structurally different market regime?** A change that improves trending
  years and hurts volatile/crash-recovery years is telling you something about regime interaction, not
  about a bug. This is a feature, not a regression — but only if the regressing regime is correctly
  identified.
- **Is the regression within the data-source noise band?** If you have previously run the same
  baseline on two different data sources or two different download dates and seen differences of
  ±2–3 pp in the same year, a 1–2 pp regression may be noise rather than signal. Quantify your
  noise band explicitly and compare before reverting.
- **Does the regression have a mechanical root cause you can fix?** If you can identify *why* the
  year regressed (e.g. a parameter that is too aggressive in a specific condition), a targeted fix
  is worth exploring before a full revert. But if the fix requires adding more parameters to patch
  the new parameter, that is complexity compounding on complexity — revert and think differently.

If you cannot answer all three questions confidently, revert. It is always cheaper to revert and
return to a known-good baseline than to carry forward a hypothesis that needs defending.

### Step 4 — Revert cleanly

A clean revert means:

1. **Restore the exact baseline configuration** — not "approximately T29" but the actual parameter
   values, override table, and universe at the tagged baseline. If your baseline is not tagged or
   version-controlled, you cannot revert reliably. Tag every baseline before experimenting.
2. **Confirm the revert** — re-run the affected years against the restored baseline and confirm they
   match the baseline numbers within data-source noise. If they don't match, you have a configuration
   drift problem that must be resolved before continuing.
3. **Log the lesson** — record what you tried, what it actually did, and why it was reverted. The goal
   is to prevent the same hypothesis from being re-tested without the context of why it failed. Over
   multiple rounds of development, a well-maintained experiment log is worth more than any single
   improvement, because it accumulates the *boundaries* of what works in your strategy's design space.

For the log entry structure, see `references/experiment-log-format.md`.

## Special cases

### "Any cooldown > 0 is catastrophic"

Position-entry cooldowns (gaps between when you can re-enter a stock after stopping out) feel
intuitively protective but can cause severe harm in strongly trending markets. The mechanism:

- In a bull trend, a stop-out is often triggered by brief volatility before a larger move continues.
- A cooldown fills the vacated slot with an alternative stock that holds the position for the full
  hold period.
- The alternative blocks the optimal re-entry that would have captured the continuation of the trend.

Before testing any cooldown parameter, test it in years that include both strong trends (where the cost
is highest) and volatile corrections (where the protective benefit is hypothesized to appear). If the
tested years do not include both regimes, your acceptance criteria are under-specified.

The general principle: constraints that feel like risk management often transfer risk from one year to
another rather than reducing total risk. Evaluate across the full window, not just the target year.

### When data revision invalidates a baseline

Sometimes the issue is not the change — it is that the same configuration produces different numbers
on different runs because underlying data has been revised, adjusted, or re-pulled from the source.

Signs of a data-revision artifact:
- A baseline re-run produces numbers different from the last recorded baseline by ±1–4 pp in one year,
  with all other years matching exactly.
- The regression appears only in the year most recently added to your evaluation window.
- Different machines or data sources produce systematically different numbers for the same year.

The correct response is a **diagnostic run**: run the same configuration with no changes on a
controlled data source, confirm which years are stable, and quantify the noise band. Treat any
regression within the noise band as non-actionable until you have a larger-signal change to test.

Lesson: never compare experiments run on different data-source downloads without first confirming the
noise band. A "regression" inside your noise band is not a regression.

### When a new feature is net negative despite good theory

Strong theoretical motivation is not a revert override. The pattern "theoretically sound but
empirically wrong" is one of the most common in quantitative research. Common causes:

- **Signal interaction**: the new feature changes which candidates get selected, and the displaced
  candidates were contributing more than the theoretical benefit of the new signal.
- **Regime-specific validity**: the theory is correct in one regime and actively harmful in another,
  and the harmful regime covers more of your evaluation window.
- **Threshold sensitivity**: the parameter value needed to make the feature beneficial is too narrow
  to be reliable, meaning any forward deviation will cause harm.

In all three cases, revert and log the specific failure mode. A future experiment with a different
parameterization or scoping may succeed — but it must be tested from a clean baseline with its own
pre-written acceptance criteria.

## Report structure

When this skill is invoked, produce the following:

```
# Revert Decision: <Experiment ID>

## Result classification
<Clear win / Mixed / Partial win / Regression — one sentence>

## Year-by-year delta vs baseline
| Year | Baseline | Result | Delta | Within noise? |
|------|---------|--------|-------|--------------|

## Acceptance criteria check
Criterion 1: <stated criterion> → <PASS / FAIL>
Criterion 2: <stated criterion> → <PASS / FAIL>

## Diagnostic (if partial win)
<Root cause of regressing year, if identified>

## Decision
KEEP / REVERT — one paragraph explaining why, referencing the acceptance criteria.

## If reverting: log entry
<The text to add to the experiment log, including what was tried and why it failed.>
```

## A worked micro-example

**Setup:** A regime-aware score modifier was added to give stocks above their 60-day moving average
a bonus at entry time, with the hypothesis that momentum continuations outperform mean-reversions
across all regimes.

**Pre-written acceptance criteria:** Primary year (2023, the intended beneficiary) must improve by
at least 5 pp. No other year may regress more than 10 pp.

**Results:**
- 2023: −1.2 pp (failed the primary criterion)
- 2020: −54 pp (catastrophically failed the secondary criterion)

**Root cause:** The 60-day MA filter excluded stocks during crash-recovery sequences because recovering
stocks are, by definition, below their 60-day MA at the moment of maximum opportunity. In 2020, this
prevented entries at the COVID bottom and throughout the subsequent recovery.

**Decision: REVERT.** The primary criterion failed and a secondary year showed a catastrophic
regression. The mechanism assumption (momentum continuations outperform) was correct in trending years
but inverted in crash-recovery years, which are exactly the highest-return environments in the
evaluation window.

**Log entry:**
```
Momentum MA filter (+12 score above 60d MA) — REVERTED
Primary target 2023: -1.2pp (criterion: +5pp). 2020: -54pp (criterion: max -10pp).
Root cause: MA filter is inverted in crash-recovery regimes — the biggest entries
are below the MA by definition. Any momentum screen that gates on current price
vs moving average will exclude recovery entries. Do not re-test this class of
signal without conditioning on regime first.
```

This is the right outcome even though the theory was reasonable. The experiment log now contains the
specific failure mode, so a future test can condition the momentum screen to bull-only or trend-
continuation-only regimes without repeating the same mistake.

## Pairing with other skills

- Use **experiment-design** to write well-structured hypotheses with pre-specified acceptance criteria
  before running.
- Use **walk-forward-validation** to confirm that a kept change is not purely in-sample before treating
  it as a durable improvement.
- Use **training-log** to maintain the structured experiment record that makes clean reverts possible.


<!-- strongskills-brand -->

---

*Made with a StrongSkills tool — The shortcut to the cutting edge · getstrongskills.com*
