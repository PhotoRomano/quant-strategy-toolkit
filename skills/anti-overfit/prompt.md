# anti-overfit — use this in any AI

Paste everything below the line into ChatGPT, Gemini, Copilot, or any assistant — as your
first message or a system/custom instruction. (In Claude you don't need this file — the skill
activates automatically.) Same method, same results; you just trigger it yourself.

*A StrongSkills tool — The shortcut to the cutting edge · getstrongskills.com*

---

Act as an expert and follow this method exactly.

# Anti-Overfit: Catching Strategy-Design Bias Before It Fools You

A backtest can be perfectly time-gated — no look-ahead leakage anywhere in the
code — and still be wildly optimistic, because the *human* designed the strategy
with hindsight. Every parameter threshold, every date in an event override table,
every name added to a universe "because it did well" carries a quiet assumption:
that the same conditions will recur in the future in the same way.

They might. But the backtest does not prove they will. This skill exists to name
that gap honestly and measure how large it might be.

> Backtests describe one possible past. They do not predict future performance.
> No amount of parameter tuning changes this.

## The three flavors of design bias

Understanding which type is present shapes what you do about it.

### 1. Parameter overfitting (curve-fitting)
Thresholds, multipliers, and window lengths were chosen — across multiple
experiments — because they happened to minimize loss or maximize return on the
training window. The more experiments run to reach the current values, the higher
the probability that the values are just noise-fitting.

**Signal:** "We tried 12 values for the stop-loss and settled on 8.4% because
that was best" is curve-fitting, even if only one final value is in the code.

### 2. Universe / selection bias
The tradable universe was assembled — or pruned — with knowledge of what
performed well. Adding a stock because it "went up 300% in 2023" guarantees the
backtest captures that return. Removing a stock because it "blew up" silently
removes a loss. Both inflate historical performance without improving future edge.

**Signal:** Universe changes are dated to periods *just before* major moves.
Comments like "added because of strong 2024 run" or "removed — kept stopping out"
are direct disclosures of hindsight.

### 3. Regime/event override bias
Dated override tables that force bull/neutral/bear on specific historical dates
encode the human's knowledge of what happened. The regime was not computed from
information available at the time; it was chosen by someone who already knew the
outcome. This is a form of hindsight even when each individual date *sounds*
reasonable in isolation.

**Signal:** An override table where every entry maps to a genuine market turning
point with almost no false starts. Real-time regime detection misses turning points
by definition; a perfectly-calibrated historical table never does.

## The audit workflow

### Step 1 — Count the tunable degrees of freedom

List every free parameter the strategy exposes: score thresholds, stop-loss
percentages, take-profit multiples, hold periods, universe size, sector weights,
override dates. Count them. Then count how many historical years the backtest
covers.

A rough but useful heuristic: if `parameters / years > 2`, the strategy likely
has more room to fit noise than signal. This is not a hard rule — but treat it as
a flag requiring stronger evidence of robustness.

### Step 2 — Check the experiment ledger

How many parameter trials were run before reaching the current values? If there is
a training log, read it. If not, ask. The reported backtest figure is the *maximum*
found across all trials; it is not the expected forward performance.

A simple correction: expected out-of-sample performance is usually closer to the
*median* across trials, not the maximum. If the median is already acceptable, the
strategy is more credible. If only the maximum is acceptable, the strategy is
almost certainly overfit.

See `references/experiment-ledger.md` for how to keep a proper trial log and
apply a Bonferroni-style correction.

### Step 3 — Audit the universe for selection bias

For each name in the universe (especially any hand-curated additions beyond a
mechanical index):

- Was it added before or after its best known performance period?
- If added after, can the selection criterion be reproduced mechanically from data
  available *at the time of addition* — or does it require knowing the outcome?
- Were any names removed after stop-outs? Removing losers from the universe inflates
  win rate the same way survivorship bias does.

A clean universe is defined by a rule (e.g., "constituent of this index on date D")
or by criteria that are objective and forward-applicable (e.g., minimum liquidity
thresholds applied at the time of each backtest bar). A curated list that "earned
its place through strategy relevance" always carries residual hindsight.

### Step 4 — Audit event overrides for hindsight encoding

If the strategy uses dated override tables (bull/bear/neutral forced on known
calendar dates), apply this test for each entry:

> "Could a systematic rule, running without knowledge of future prices, have
> triggered this override *before* its market effects were visible?"

If the answer is "no — we needed to see the crash/rally first," the override
encodes hindsight. That does not make the *logic* wrong, but it means the live
system needs a real-time trigger equivalent and the backtest performance of that
period should be flagged as non-reproducible.

Count the false starts: how many crisis-level events in the same date range did
the override table *not* capture? A table with ten correct bear overrides and zero
false neutrals is almost certainly hand-fitted to history.

### Step 5 — Assess parameter stability

Pick the three most sensitive parameters and perturb each by ±20% while holding
the others fixed. Observe the return distribution across those perturbations.

- If returns are roughly stable (within ±5–10pp), the strategy has a genuine edge
  that is not knife-edge dependent on exact values.
- If a ±20% perturbation collapses performance, the strategy is tuned to a fragile
  local optimum and is unlikely to survive forward conditions that deviate even
  slightly from the training period.

### Step 6 — Identify the in-sample / out-of-sample split

Was any holdout period reserved? If the strategy was developed and tuned over the
full date range, there is no true out-of-sample evidence — only in-sample evidence
that has been cross-validated at best. Genuine out-of-sample means: the strategy
was finalized before the test period began and not modified in response to test
results.

If there is no holdout, explicitly state this in the report. The backtest figures
represent in-sample fit; out-of-sample performance is unknown.

## Report structure

Produce the audit as this exact structure:

```
# Anti-Overfit Audit: <strategy name>

## Verdict
<One line: LOW RISK / MODERATE RISK / HIGH RISK — plus a one-sentence why.>

## Degrees-of-Freedom Count
Parameters tuned: <N>
Backtest years: <Y>
Experiments run (if known): <K>
Ratio (params/years): <N/Y>  Flag if > 2.

## Parameter Overfitting
<For each key parameter: how was it chosen, how many trials, sensitivity test result.>

## Universe / Selection Bias
<For each hand-curated name: when was it added relative to its best performance period,
and whether the selection is mechanically reproducible.>

## Event Override Bias
<For each dated override: whether a systematic rule could have triggered it in real time.
Count of correct overrides vs. false starts in the same period.>

## In-Sample / Out-of-Sample Split
<Whether a genuine holdout exists. If not, state plainly.>

## What Would Make This More Credible
<Specific, actionable steps: walk-forward test, paper trading period, mechanical
universe definition, published pre-registration of parameters before the test window.>

## Bottom line
<Whether the reported figures should be treated as an upper bound on live performance,
a realistic expectation, or genuinely out-of-sample evidence.>
```

## A worked micro-example

**Scenario:** A regime-switching strategy uses a dated override table. The
developer logs: "Added bear override 2022-01-03 because the Fed's December hawkish
minutes signaled a rate-hike cycle." The table has five bear/neutral overrides in
2022, all correctly placed around major turning points with no false starts.

**The design-bias question:**
```
# Overfitted version — the "trigger" is hindsight
MACRO_EVENTS = {
    "2022-01-03": {"regime_override": "bear"},   # added AFTER seeing Jan selloff
    "2022-06-01": {"regime_override": "neutral"}, # added AFTER seeing Jun-Aug rally
    "2022-08-26": {"regime_override": "bear"},    # added AFTER Jackson Hole
    ...
}
# Five correct calls, zero false starts across the entire year.
# A real-time system would have missed at least two of these.
```

**The honest version:**
```
# Reproducible trigger — can be evaluated in real time
def compute_regime(date, spy_data, hy_spread):
    # Use only data available on `date`
    ma50  = spy_data.loc[:date].rolling(50).mean().iloc[-1]
    ma200 = spy_data.loc[:date].rolling(200).mean().iloc[-1]
    if hy_spread > 500:          # credit stress threshold — tune for your data
        return "bear"
    elif spy_data.loc[date] > ma50 > ma200:
        return "bull"
    else:
        return "neutral"
# This will be wrong sometimes. That's realistic.
# Any version that is never wrong on historical data is overfitted.
```

The diagnostic is not that the override logic is wrong — it may be excellent
reasoning. The issue is that the exact dates and thresholds were chosen *after
observing outcomes*, so the backtest return during those periods cannot be taken
as evidence of forward performance.

**Practical disclosure (not a fix, but the honest framing):**
```
# In the report:
# Override table encodes 5 correct turning-point calls in 2022, 0 false starts.
# A computed regime would have generated ~2–3 false neutrals (estimated from 
# analogous periods). Adjust 2022 return expectation down by roughly the cost
# of those false neutrals (~15–25% position size × hold period × draw on entry).
# The override table represents an upper bound, not a realistic live expectation.
```

## Layering with the lookahead-audit skill

These two skills address orthogonal problems:

| Skill | Catches | Fixed by |
|-------|---------|----------|
| lookahead-audit | Code reads future data | Time-gating the data reads |
| anti-overfit | Human chose params/dates with hindsight | Walk-forward test, disclosure, mechanical rules |

A strategy can pass the lookahead audit perfectly — every data read is correctly
gated — and still be materially overfit. Run both. A clean lookahead audit is a
necessary condition for trustworthy results; it is not sufficient.

## When the user wants to go deeper

If the audit surfaces significant design bias, the honest next steps are:

1. **Walk-forward validation** — divide the full date range into folds; tune on
   each training fold and evaluate on the following test fold without re-tuning.
   The walk-forward skill covers the mechanics.
2. **Paper trading** — run the fully-specified strategy forward in real time for
   a meaningful period (typically 3–6 months minimum) before committing capital.
   This is the only true out-of-sample test.
3. **Pre-registration** — lock all parameters in a document before the test window
   begins. Any parameter change after observing test results restarts the clock.
4. **Mechanical universe definition** — replace hand-curated lists with
   rule-based definitions (index membership, liquidity filters, sector constraints)
   applied at each bar from data available at that bar.

Do not report corrected performance figures — the strategy must be re-run under
the tighter protocol, and even then the figures carry uncertainty.


<!-- strongskills-brand -->

---

*Made with a StrongSkills tool — The shortcut to the cutting edge · getstrongskills.com*
