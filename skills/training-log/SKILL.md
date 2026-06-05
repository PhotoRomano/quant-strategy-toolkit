---
name: training-log
description: Structured JSONL experiment journaling for quantitative strategy development — the discipline layer that turns ad-hoc backtesting into a traceable research process. Use when someone says "I want to track my backtest experiments", "how do I know if my changes are improving things", "log this experiment", "write a pre-log entry", "update the training log", "what did I try last time", "add a diary entry after this run", or whenever someone is iterating on a backtest and needs to record a change, hypothesis, prediction, and outcome. Also use proactively when reviewing a series of experiments to spot calibration drift, identify what's already been tried, or surface lessons learned.
---

# Training-Log: Structured Experiment Journaling

Backtesting without a journal is just noise. Every time you change a parameter,
add a signal, or tune a regime rule, you are running an experiment. Without
a structured record, you will repeat dead-end experiments, lose your baseline,
and have no way to know whether your confidence in a change is calibrated to reality.

This skill gives you a lightweight, language-agnostic framework for journaling
every experiment as a structured JSONL entry — one JSON object per line —
so your entire research history is queryable, diffable, and honest.

This skill does **not** tell you what parameters to choose. It enforces the
discipline of writing down what you expected, why, and what actually happened
— before and after you run. That record is the difference between research
and guessing.

## Why JSONL?

One JSON object per line means:

- **Append-only** — each run adds exactly one line. No file locking, no
  merge conflicts, no accidental overwrites of prior results.
- **Queryable without a database** — `grep`, `jq`, Python `json.loads()`
  over lines; no schema migration needed as fields evolve.
- **Diffable** — a single new line in `git diff` is the complete record of
  an experiment. Pairs naturally with version control.
- **Incrementally extensible** — add a `category` field in experiment 30
  without touching experiments 1–29.

A companion spreadsheet (e.g. `training-log.xlsx`) is useful for pivot-table
views, but the JSONL file is the source of truth.

## The mandatory pre-experiment ritual

The highest-value discipline in this framework is writing the entry **before**
you run. This forces you to commit to a prediction that can be scored against
the outcome. It takes two minutes and eliminates hindsight rationalization.

Every entry must answer these questions before the run:

| Field | Purpose |
|---|---|
| `experiment` | A sortable label (e.g. `T32a`, `EXP-007`). Sequential, never reused. |
| `timestamp` | ISO 8601 with timezone. Auto-generate; do not backfill. |
| `category` | The type of change — drives your base-rate estimate. |
| `predicted_p_success` | Your probability the change improves the target metric (0.0–1.0). |
| `prediction_reasoning` | One line: base rate for this category, the causal mechanism, and isolation quality. |
| `ev_estimate` | `P * E[gain] - (1-P) * E[loss]` — only run if EV is positive. |
| `changes` | Exact list of what changed in the code or config. |
| `hypothesis` | What you expect, and the specific causal chain you believe is at work. |

After the run, add:

| Field | Purpose |
|---|---|
| `result` | One-sentence outcome verdict. Include `SUCCESS`, `REGRESSION`, `MIXED`, or `DIAGNOSTIC`. |
| `results` | Year-by-year (or fold-by-fold) output metrics. |
| `result_vs_baseline` | Delta versus the current champion, year-by-year. |
| `calibration` | Predicted P vs. actual outcome. Was the mechanism right or wrong? |
| `lesson_learned` | The one thing this run taught you, stated concretely. |

## Minimal viable schema

```json
{
  "experiment": "T32a",
  "timestamp": "2025-06-15T14:23:00-04:00",
  "category": "root_cause_fix",
  "predicted_p_success": 0.70,
  "prediction_reasoning": "base_rate=60-75% for isolated root cause fixes; mechanism is well-identified; single change",
  "ev_estimate": "0.70 * 4pp - 0.30 * 1pp = +2.5pp EV (positive, run)",
  "changes": ["scorer.py line 88: removed sector boost that had no expiry date"],
  "hypothesis": "Boost was persisting into periods it wasn't intended for, displacing other picks.",
  "result": "REGRESSION. -1.4pp on target year. Mechanism was wrong — root cause was elsewhere.",
  "results": {"2021": 17.7},
  "result_vs_baseline": {"2021": "-1.4pp"},
  "calibration": "predicted 70%, actual REGRESSION. Overconfident; should have isolated further first.",
  "lesson_learned": "Always verify root cause with a diagnostic run before a fix run."
}
```

## Experiment categories and their base rates

Categorizing each experiment lets you apply a realistic prior probability
before you run. Use these as starting points and calibrate them against
your own log over time.

| Category | Description | Illustrative base rate |
|---|---|---|
| `root_cause_fix` | You have identified the specific mechanism causing a regression and are fixing exactly that. | ~50–70% (high when mechanism is confirmed) |
| `param_tuning` | Adjusting a numeric threshold (hold days, position size, score cutoff). | ~30–45% |
| `macro_overlay` | Adding or modifying a dated regime-override event. | ~35–55% (high risk of hindsight; see note below) |
| `new_signal` | Adding a new scoring factor (momentum, quality screen, sentiment). | ~25–40% |
| `new_instrument` | Adding an asset to the tradable universe. | ~30–50% |
| `quality_gate` | Adding a fundamental filter that hard-blocks low-quality entries. | ~25–40% (high false-positive risk) |
| `diagnostic` | No hypothesis about improvement; pure measurement and root-cause investigation. | Always run; success is information, not improvement. |

These base rates exist to stop you from assuming any idea has a >70% chance
of working. Most ideas in quantitative research fail on the first attempt.

> **Hindsight caution for macro overlays:** Adding a dated override because
> you know what happened on that date is design bias, not a code fix. It may
> improve backtests and hurt live performance. Log the motivation honestly.
> See the lookahead-audit skill for the distinction between code leakage
> and design bias.

## Expected Value filter: only run positive-EV experiments

Before running, compute:

```
EV = P(success) × E[gain in pp] - P(failure) × E[loss in pp]
```

where "gain" and "loss" are your estimated impact on the target metric if
the experiment succeeds or fails respectively.

If EV is negative or near zero, either improve the isolation (reduce expected
loss) or deprioritize the experiment. This prevents burning compute and time
on low-quality ideas.

Example EV calculation from a real entry:

```
predicted_p_success: 0.55
mechanism: 3-month relative strength differentiates recent leaders from laggards
isolation: GOOD — single scoring term, capped at ±8 points
EV = 0.55 * 10pp - 0.45 * 8pp = +5.5pp - 3.6pp = +1.9pp (positive, run cheapest year first)
```

## Isolation discipline

The most common reason experiments produce ambiguous results is that too
many things changed at once. Every entry should represent **one** change,
or at minimum a logically inseparable pair of changes. When you bundle three
changes, a regression tells you nothing about which one caused the problem.

Prefer this workflow:

1. Write a `--pre-log` skeleton with the proposed change.
2. If you are tempted to add a second change, write a second skeleton (next
   experiment number) with it as a separate hypothesis.
3. Run the smallest possible test first (one year, one market period) to
   validate the mechanism before spending time on a full run.
4. Only promote to a full multi-year run if the cheapest test is consistent
   with the hypothesis.

## Calibration tracking: scoring your own predictions

The prediction fields (`predicted_p_success`, `prediction_reasoning`) only
have value if you review them against outcomes. A calibration review asks:

- When you said P=0.70, did roughly 70% of those experiments succeed?
- Are you systematically overconfident in a particular category?
- Are you correctly penalizing poor isolation in your P estimate?

Run a calibration review every 10–15 experiments. Pull all entries with a
`predicted_p_success` field and score the prediction against the outcome word
in `result`. If your stated 0.70-probability experiments succeed only 30%
of the time, you are overconfident and should lower your prior for that category.

See `references/calibration-ledger.md` for a worked calibration table format
and how to use the ledger to improve future estimates.

## Worked micro-example: before and after

**Pre-experiment entry (written before running):**

```json
{
  "experiment": "T15",
  "timestamp": "2025-09-01T09:45:00-04:00",
  "category": "new_signal",
  "predicted_p_success": 0.40,
  "prediction_reasoning": "base_rate=25-40% for new signals; mechanism: quality stocks 15-25% off 52w high in bull regime represent dip-buying opportunities; isolation: GOOD — single additive score term",
  "ev_estimate": "0.40 * 5pp - 0.60 * 2pp = +0.8pp EV (marginal positive, run cheapest year first)",
  "changes": ["scorer.py: add +8 bonus when price is 15-25% below 52-week high in bull regime"],
  "hypothesis": "Stocks pulling back modestly from highs in a confirmed bull regime often recover. A small bonus should improve 2019 and 2023 bull-year performance without hurting bear years."
}
```

**After running:**

```json
{
  "result": "MIXED. 2019 improved +3.2pp. 2021 regressed -5.1pp — bonus fired during early 2021 value rotation, picking stocks declining from inflated 2020 peaks rather than healthy dips.",
  "results": {"2019": 28.7, "2021": 14.3},
  "result_vs_baseline": {"2019": "+3.2pp", "2021": "-5.1pp"},
  "calibration": "predicted 40%, actual MIXED. Mechanism partially correct but context-dependent — works in stable bull, fails in rotation years.",
  "lesson_learned": "Dip bonus needs a regime-freshness check: apply only when the bull regime has been continuous for > 60 days, not immediately after a crash-recovery inflection."
}
```

The lesson in the post-run entry becomes the hypothesis for the next experiment.
That is the compounding effect of a maintained journal.

## Diary integration

After each run, write a brief narrative diary entry that captures the session
in plain language — what you tried, what surprised you, and what you plan next.
The diary is the qualitative complement to the structured JSONL. Together they
give you two recovery paths after a long gap:

1. Read the JSONL to reconstruct exact parameter states.
2. Read the diary to re-enter the reasoning context quickly.

A diary entry template:

```
## <date> | <strategy name> | Training <experiment>

**Category:** <category>
**Predicted P(success):** <p> — <one-line reasoning>
**EV estimate:** <EV line>

**Changes:** <semicolon list>
**Hypothesis:** <one paragraph>
**Result:** <outcome word + one paragraph>

| Year | Return (vs baseline) | Win% | MaxDD |
|------|-----------------------|------|-------|
| 2023 | +15.2% (+3.1pp)       | 62%  | 8.4%  |

**Calibration:** predicted P=60% → actual SUCCESS (✓ win)
**Lesson:** <one sentence>
**Next:** <experiment number and direction>
```

## Output format when reviewing the log

When asked to summarize or audit a training log, produce this structure:

```
# Training Log Review: <strategy name>

## Summary
- Total experiments: N
- Improvements (SUCCESS): N (N%)
- Regressions: N
- Diagnostics/inconclusive: N

## Calibration Assessment
| Predicted P range | N experiments | Actual success rate | Bias |
|---|---|---|---|
| 0.60–0.80         | 8             | 37%                 | Overconfident |
| 0.30–0.60         | 10            | 45%                 | Well-calibrated |

## What Has Already Been Tried
<Category-grouped list with outcome labels — prevents re-running dead ends>

## Lessons Ledger
<Chronological list of lesson_learned fields — the compounding knowledge base>

## Recommended Next Experiments
<Based on open threads, unsuccessful but partially-confirmed mechanisms, and untested hypotheses>
```

## When the user wants more

For calibration table templates and a worked ledger showing how to compute
and track prediction accuracy across categories, see
`references/calibration-ledger.md`.

Pair this skill with the **experiment-design** skill (pre-experiment hypothesis
structuring), the **backtest-harness** skill (running the experiments themselves),
and the **lookahead-audit** skill (verifying that the code changes being logged
are temporally honest).


<!-- strongskills-brand -->

---

*Made with a StrongSkills tool — The shortcut to the cutting edge · getstrongskills.com*
