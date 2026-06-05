# walk-forward-validation — use this in any AI

Paste everything below the line into ChatGPT, Gemini, Copilot, or any assistant — as your
first message or a system/custom instruction. (In Claude you don't need this file — the skill
activates automatically.) Same method, same results; you just trigger it yourself.

*A StrongSkills tool — The shortcut to the cutting edge · getstrongskills.com*

---

Act as an expert and follow this method exactly.

# Walk-Forward Validation

A backtest that runs over the same data you tuned the strategy on tells you almost nothing
useful. The parameters were chosen — consciously or not — to work well on that exact history.
Walk-forward validation (WFV) is the discipline that separates what the strategy *learned* from
what it *knows how to do in the future*.

The central idea: at every optimization step, freeze an unseen forward window as a test set, run
the tuned strategy on it without touching the parameters again, and report *that* result. If the
strategy generalizes, test performance tracks train performance. If it does not, you have
curve-fitting — and you need to know that before committing capital.

This skill does **not** pick parameters, predict returns, or guarantee a strategy is profitable.
A passing walk-forward test means the strategy's edge is not entirely an artifact of historical
fitting. Whether that edge persists in live markets depends on factors the test cannot see.

---

## The core principle

Every point in time has exactly one role: it is either *known* when a parameter decision is made,
or it is *not yet known*. Walk-forward validation formalizes this by partitioning the timeline:

```
Timeline →

[-------- IS --------][--- OOS ---][-------- IS --------][--- OOS ---] ...
   Train window 1      Test 1        Train window 2       Test 2
```

**In-sample (IS)** — the window on which parameters are fit or selected.
**Out-of-sample (OOS)** — the window the strategy runs on using those frozen parameters, without
any further adjustment.

The OOS windows must never overlap with the IS window that produced the parameters run on them.
Violating this is temporal leakage — the same error as look-ahead bias, applied at the parameter
level rather than the data level.

---

## Two valid window schemes

### 1. Expanding window (anchored-origin)

The IS window grows at each step; the OOS window advances by a fixed stride.

```
Step 1:  IS = [2019–2021]         OOS = [2022]
Step 2:  IS = [2019–2022]         OOS = [2023]
Step 3:  IS = [2019–2023]         OOS = [2024]
```

**When to use:** when you believe the strategy learns from all history and older data is still
informative. This is the more conservative choice; early-period data never gets "forgotten."

### 2. Rolling window (fixed-length)

The IS window slides forward at each step, discarding old data.

```
Step 1:  IS = [2019–2021]         OOS = [2022]
Step 2:  IS = [2020–2022]         OOS = [2023]
Step 3:  IS = [2021–2023]         OOS = [2024]
```

**When to use:** when the strategy's regime or market structure changes over time, and old data
may be more misleading than helpful (e.g., a post-2020 volatility regime is structurally
different from 2010).

**Critical rule for both schemes:** set aside a *final holdout* period (typically the most recent
year or two) that is never touched during scheme selection, window-length choice, or any tuning.
That holdout is your last honest report card. Use it once, then deploy or abandon.

---

## Why not shuffle / cross-validate like in standard ML?

Standard k-fold cross-validation shuffles data randomly across folds. For time-series, that is
a form of look-ahead bias: the model trains on 2023 data and is "tested" on 2021, which it saw
implicitly during training. Information from the future leaks into the past fold.

The rule is simple: **test data must always be strictly later in time than training data.**
Never shuffle. Never stratify across time. The distribution of market returns is not IID.

---

## Step-by-step procedure

### 1. Define your fixed-parameter set

Before running the first WFV step, write down the complete list of every parameter the strategy
exposes: entry score threshold, hold period, stop-loss percentage, trailing stop, position sizing
fraction, regime thresholds, lookback windows, and any sector or asset filter weights.

These are the only things you are allowed to change between IS windows. Document each change and
the IS-period reason for it. Any change justified by "it looks better in 2023" when 2023 data
was already in the OOS pool is contamination.

### 2. Choose window lengths with intention, not hindsight

A common default: IS = 2–3 years, OOS = 1 year, stride = 1 year. The choice should be driven
by how often you expect the strategy's dominant regime to cycle, not by what produces the best
aggregate OOS number. Trying multiple window lengths and picking the best is itself overfitting
the walk-forward setup — choose once.

### 3. Run IS optimization or selection

For each IS window, run whatever parameter sweep or tuning process you use. Record the chosen
parameters and the IS performance. IS performance is informational only; it will always look
better than OOS and is not a reportable result.

### 4. Run OOS — frozen parameters only

Apply the IS-chosen parameters to the next forward window without any modification. The OOS run
must be a single, unedited execution. If the OOS result looks poor and you are tempted to "fix"
the parameters and re-run, that re-run is no longer OOS. You are allowed to investigate *why*
a period was bad (regime change? data quality?), but the OOS result stands as-is.

### 5. Collect OOS metrics across all windows

The final WFV report is built from the concatenated OOS windows only. Stitch them end-to-end as
if the strategy ran continuously, with each window using the parameters that were frozen for it.
Compute performance over that composite OOS series.

### 6. Run the final holdout

After all IS/OOS cycles are complete, run the strategy on the final holdout period — once — using
the parameters from the last IS window. This is the closest thing you have to a live-trading
simulation. Report it separately; never fold it back into parameter tuning.

---

## Degradation detection

A well-generalized strategy shows OOS performance that is lower than IS performance but in the
same direction. Degradation becomes a red flag when:

- **OOS is negative when IS is positive** — the strategy has not learned a real edge, it has
  memorized the training period.
- **IS/OOS correlation is near zero or negative across steps** — no consistent relationship
  between what was learned and what was realized. Likely curve-fitting.
- **OOS Sharpe degrades monotonically** across successive steps while IS Sharpe stays stable —
  the market has structurally changed and the strategy is not adapting.

A reasonable target: OOS performance at 40–70% of IS performance on a return-per-unit-risk basis.
Numbers below that suggest the parameter count is too high relative to the signal.

See `references/degradation-patterns.md` for a full catalog of failure modes, statistical tests,
and the IS/OOS ratio heuristic.

---

## Report structure

Produce walk-forward results in this exact structure. Never report IS performance as the strategy's
performance; always lead with OOS.

```
# Walk-Forward Validation: <strategy name>

## Configuration
- IS window:       <length, e.g. "2 years">
- OOS window:      <length, e.g. "1 year">
- Stride:          <e.g. "1 year">
- Scheme:          <expanding | rolling>
- Parameter set:   <list the parameters that were optimized>
- Final holdout:   <period reserved and not touched>

## Per-Step Results
| Step | IS Period    | OOS Period   | IS Return | OOS Return | IS Sharpe | OOS Sharpe | IS/OOS ratio |
|------|-------------|-------------|-----------|------------|-----------|------------|--------------|
| 1    | 2019–2021   | 2022        | ...       | ...        | ...       | ...        | ...          |
| 2    | 2019–2022   | 2023        | ...       | ...        | ...       | ...        | ...          |
...

## Composite OOS Performance (concatenated OOS windows only)
- Total return:      <annualized, OOS only>
- Sharpe ratio:      <OOS only>
- Max drawdown:      <OOS only>
- Win rate:          <OOS only>
- Number of trades:  <OOS only>

## Final Holdout
- Period:            <reserved period>
- Parameters used:   <from last IS window>
- Return:            ...
- Sharpe:            ...
- Max drawdown:      ...

## IS/OOS Degradation Assessment
<Is OOS tracking IS? Is there a trend? State the verdict plainly.>

## Verdict
<GENERALIZES / CURVE-FIT / INCONCLUSIVE — one sentence reason.>

## Caveats
<Honesty section: parameter count, regime coverage, data recency, transaction cost assumptions.>
```

---

## A worked micro-example

A strategy is tuned on 2019–2022 and reports an annualized return of +38%. Someone asks whether
it will work in 2023.

**Wrong approach — in-sample-only evaluation:**
```python
# Optimized parameters on 2019–2022 full history
params = optimize(strategy, data["2019":"2022"])   # picks best params over 4 years
result = backtest(strategy, params, data["2019":"2022"])
print(result["return"])   # +38% — this is IS; it says nothing about 2023
```

The 38% is the number that *motivated* the chosen parameters. It is not evidence the strategy
works. It is evidence the optimizer found parameters that fit 2019–2022.

**Correct approach — expanding-window WFV:**
```python
steps = [
    {"is": ("2019", "2021"), "oos": ("2022", "2022")},
    {"is": ("2019", "2022"), "oos": ("2023", "2023")},
]

oos_equity_curves = []

for step in steps:
    # 1. Optimize on IS window only
    params = optimize(strategy, data[step["is"][0] : step["is"][1]])

    # 2. Run OOS with frozen params — no re-touching
    oos_result = backtest(strategy, params, data[step["oos"][0] : step["oos"][1]])
    oos_equity_curves.append(oos_result["equity_curve"])

# 3. Report composite OOS, not IS
composite = stitch_curves(oos_equity_curves)
report(composite)   # this is the honest number
```

If `composite` shows +12%/yr annualized, the honest answer to "will it work in 2023" is: "the
strategy generalizes at roughly one-third of its IS performance. That could be real edge, or it
could be luck across two OOS windows — more windows would increase confidence."

---

## Common mistakes and their fixes

| Mistake | Why it invalidates the test | Fix |
|---|---|---|
| Re-running OOS after seeing a poor result | Turns OOS into IS — you are now fitting to it | OOS runs once; document and move on |
| Choosing window lengths after seeing the aggregate OOS return | Same as overfitting the split itself | Commit to window scheme before any run |
| Including final holdout in parameter tuning | Destroys the only truly unseen period | Reserve holdout before any tuning begins |
| Reporting IS performance as the strategy's performance | Misleads anyone making a deployment decision | Always lead with OOS in every report |
| Using the full data range for initial parameter search before defining splits | Pre-contaminates every OOS window | Define splits first, then restrict access |
| Using the same random seed / data range for every IS window in a rolling scheme | Systematic correlation between windows — not truly independent tests | Each window should use only the data in its date range |

---

## Regime coverage: a structural concern

A strategy's OOS windows may not cover all meaningful market regimes. If every OOS window falls
in a bull market, the test says nothing about bear performance. Before trusting the composite OOS
result, audit the regime coverage of the OOS windows:

- Which OOS windows included a significant drawdown period?
- Which included a rate-rising environment?
- Which included elevated volatility (VIX > 30)?

If all the stress scenarios fall inside IS windows, the OOS result is optimistic by construction.
This is not a code bug — it is a structural limitation of the available data history. Disclose it
explicitly. A strategy tested entirely in a bull market is untested, not validated.

---

## Relationship to other skills

- Pair with **lookahead-audit** first: a walk-forward test run on leaky data is still a leaky
  test. Confirm temporal honesty in the code before structuring the WFV.
- Pair with **anti-overfit** to quantify how many parameters are too many for a given IS window
  length (the degrees-of-freedom / sample-size relationship).
- Pair with **experiment-design** when logging WFV runs: each IS/OOS step is an experiment; it
  should be recorded with a hypothesis, parameters, and result before the run, not after.
- Pair with **metrics-report** to produce the composite OOS performance table in a standardized,
  shareable format.


<!-- strongskills-brand -->

---

*Made with a StrongSkills tool — The shortcut to the cutting edge · getstrongskills.com*
