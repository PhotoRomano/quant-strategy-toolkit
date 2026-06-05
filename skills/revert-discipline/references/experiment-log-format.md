# Experiment Log Format

A well-maintained experiment log has two jobs: (1) give you a fast lookup of what has already been
tried and why it was kept or reverted, and (2) accumulate the *boundaries* of your strategy's design
space so you do not re-test the same hypothesis with the same parameterization.

Every entry should be writable in under five minutes. If an entry takes longer, it is too detailed.
The goal is signal density, not documentation completeness.

---

## JSONL format (recommended)

Store one JSON object per line. This makes it machine-readable for future analysis (e.g. "what
fraction of experiments in category X were reverted?") while remaining human-readable.

```jsonl
{
  "experiment": "T42",
  "timestamp": "2026-01-15T10:30:00-05:00",
  "category": "parameter_tuning",
  "changes": [
    "Bear regime max_positions: 2 → 1"
  ],
  "hypothesis": "Fewer positions in bear reduces exposure and improves bear-year returns.",
  "predicted_p_success": 0.65,
  "primary_target": "2022",
  "acceptance_criteria": {
    "primary": "2022 improves >= 5pp",
    "secondary": "no other year regresses >= 8pp"
  },
  "result": "REGRESSION — reverted. 2022: -3.1pp (criterion failed). 2020: -12pp (catastrophic).",
  "lesson": "Fewer bear positions reduces available cash to capture the eventual bear recovery. Bear regime transitions to neutral, and neutral entries need the freed position slots. Do not test position reduction without also testing transition timing."
}
```

**Required fields:** `experiment`, `timestamp`, `changes`, `hypothesis`, `result`, `lesson`

**Optional but recommended:** `category`, `predicted_p_success`, `primary_target`,
`acceptance_criteria`, `result_vs_baseline` (a dict of year → delta_pp)

---

## Categories

Use consistent category labels so you can filter the log later:

| Category | Use when |
|----------|---------|
| `parameter_tuning` | Changing a numeric threshold (hold days, position count, score cutoff) |
| `universe_change` | Adding or removing symbols or screening criteria |
| `signal_addition` | Adding a new factor or data source to scoring |
| `regime_logic` | Changing how regime is determined or how it affects behavior |
| `macro_override` | Adding or modifying a dated event override |
| `sizing_change` | Changing position size formula or conviction weighting |
| `diagnostic` | No code change — investigating a discrepancy or data artifact |
| `infrastructure` | Runner, save, reporting changes — no strategy impact expected |

---

## Predicted probability of success

Before running each experiment, write down your estimated probability that the experiment will meet
its acceptance criteria. This is not required, but it builds calibration over time.

After N experiments, you can look back at your predictions vs outcomes:
- If your 0.8-confidence experiments succeed only 40% of the time, you are systematically
  overconfident — your theories sound good but don't survive the data.
- If your 0.3-confidence experiments succeed 60% of the time, your intuition about what "probably
  won't work" is wrong — these are your most underexplored directions.

A simple ledger at the top of your log file:

```
# Calibration ledger
High confidence (>0.7):  X predicted, Y succeeded  (Z%)
Medium confidence (0.4–0.7): X predicted, Y succeeded  (Z%)
Low confidence (<0.4):  X predicted, Y succeeded  (Z%)
```

---

## What to write in the lesson field

The lesson is the most valuable field. It should answer one question: **what would you tell your
future self before they re-tested a similar hypothesis?**

Good lessons are specific about the mechanism that failed, not about the outcome:

- Bad: "This didn't work."
- Bad: "The 2022 year was hurt."
- Good: "Position count reduction in bear is harmful because fewer slots means the regime-transition
  to neutral has no available positions. The constraint is not on the bear regime entries — it is on
  the first neutral entries after the bear ends."

If you cannot write a specific mechanism, write "root cause unknown" rather than a vague generality.
Unknown root causes are still useful because they flag that re-testing this category needs a diagnostic
step first.

---

## Baseline tagging

Before any experiment, tag the current baseline configuration in version control or with a named
snapshot. The experiment log entry is only as useful as your ability to restore the baseline it
references.

Minimum viable tagging:
- A named commit or config snapshot (e.g. `baseline-T40`, `config_T40.json`)
- The set of years that were confirmed to match the baseline numbers on this data source

If you cannot restore a named baseline exactly, you cannot trust revert confirmation runs — which means
you cannot trust that your current configuration is actually at baseline when the next experiment starts.

---

## Anti-patterns to avoid

**Adding a positive spin to a mixed result.** A result like "2019 +8pp, 2023 −19pp" is a regression,
not a "promising result with a known issue." Log it as a regression with the root cause noted, then
start a new experiment from the clean baseline.

**Overwriting the baseline with a marginal result.** Marginal means the change added complexity for
near-zero net benefit. The new baseline is now harder to improve from, because any future experiment
that undoes the marginal change looks like a regression. Keep the simplest effective baseline.

**Logging without a lesson.** A "REVERTED" with no lesson leaves the same hypothesis open for
re-testing without context. Every revert should close the hypothesis class it represents, or
narrow it to a specific sub-condition that has not yet been tested.

**Cross-run comparisons without controlling the data source.** If your underlying data source can
produce different numbers for the same year on different download dates (due to corporate actions,
adjustments, or data corrections), any experiment comparison that spans a data refresh is potentially
confounded. Run a diagnostic before attributing a difference to your change.
