---
name: performance-attribution
description: Decompose backtest or live-trading returns by year, market regime, and individual asset to explain *why* performance looks the way it does — not just what the headline number is. Use this whenever someone shares a multi-year results table and asks "what's driving this?", "which years are real vs lucky?", "is one asset carrying everything?", "does this hold up across regimes?", "my 2022 was terrible — is that the strategy or the market?", or "I added one stock and the whole thing changed." Also use proactively before tuning parameters, presenting results to others, or deciding whether a backtest deserves live capital.
---

# Performance Attribution

A single multi-year return figure tells you almost nothing about whether a strategy
will survive forward. Attribution breaks that number apart so you can see whether the
wins are broad and repeatable, or whether they depend on a handful of lucky years,
one dominant position, or a regime that may not recur.

This skill does **not** tune parameters or pick assets. It diagnoses what is already
there. A clean attribution report is not a profit guarantee; it only clarifies which
conditions produced the results you're looking at.

## Why attribution matters before anything else

Two strategies can produce identical five-year compound returns and have completely
different risk profiles. One might earn consistently across regimes; the other might
owe everything to a single bull-market year while quietly bleeding in all others.
You cannot tell from the headline. Attribution surfaces the difference.

The three-layer decomposition below addresses the most common blind spots:

1. **Year-by-year** — isolates calendar-year volatility and regime sensitivity.
2. **Regime-sliced** — separates bull, neutral, and bear contributions so you know
   whether the strategy actually works in adverse conditions or just avoids them.
3. **Per-asset delta** — reveals whether a small number of names are carrying the
   portfolio, and how fragile that concentration is.

## Step 1 — Build the year-by-year table

For each calendar year in the backtest, compile the following columns. If the
strategy uses a benchmark, include it alongside so the comparison is immediate.

```
Year | Trades | Win Rate | Return | Max Drawdown | Avg Hold | Benchmark
```

Compute the **compounded** multi-year return separately from the average of annual
returns — the two differ whenever there are negative years, and the compound figure
is the one that actually matters.

Look for these patterns before doing anything else:

- **One year carrying everything.** If removing the single best year turns a winning
  compounded result into a flat or negative one, the strategy lacks breadth. That year
  should be studied closely: was the regime unusual? Did one asset dominate it?
- **Consistent drawdown creep.** Max drawdown growing faster than returns across years
  suggests increasing leverage, concentration, or regime mismatch.
- **Deteriorating win rate.** A win rate that starts reasonable and degrades year-over-year
  often signals that the scoring or universe is becoming stale, or that the market
  microstructure it was tuned on has changed.

## Step 2 — Slice returns by market regime

Assign each trade to the regime (bull / neutral / bear) that was active at entry.
Aggregate returns, win rates, and trade counts within each bucket.

A healthy regime breakdown looks roughly like this:

| Regime  | Expected role                                  | Warning sign                            |
|---------|------------------------------------------------|-----------------------------------------|
| Bull    | Highest return per trade; most trades          | Very few trades — strategy sits out rallies |
| Neutral | Modest positive return; conservative sizing    | Negative — neutral is a transition buffer; it should not consistently lose |
| Bear    | Small positive or near-zero; capital preservation | Deep losses — strategy is not adapting its posture |

The key question per regime: *does the strategy change its behavior in proportion to
what the market is doing, or does it behave identically regardless of conditions?*

A strategy that enters large positions in bear regimes with the same frequency as in
bull regimes is not regime-aware, even if its code claims to be. The trade count and
position-size distribution across regimes shows this directly.

## Step 3 — Per-asset delta analysis

For each asset in the universe, compute its **marginal contribution**: how much does
the total multi-year return change if that asset is removed?

The simplest version: run the backtest with the asset excluded, compare the full-period
return to the baseline. This answers the concentration question directly.

Flag any asset where:
- Its removal changes the total return by more than 5 percentage points in any single
  year (high dependence).
- It appears in fewer than 10% of decision periods but accounts for more than 20% of
  total profit (episodic windfall that may not repeat).
- Its contribution is large in exactly one regime or calendar year but negligible in
  others (theme-specific, not structural).

### Breadth divergence as a context signal

One useful informational signal for concentration analysis is the spread between an
equal-weight market index (such as RSP) and a cap-weight index (such as SPY) over
a trailing one-year window:

```
breadth_divergence = RSP_return_1yr - SPY_return_1yr
```

When this is strongly negative (e.g., -10 pp or more), a small number of large-cap
names are driving index-level gains while most stocks lag. In this environment, a
momentum strategy that happens to hold those large-cap names will look outstanding;
one that diversifies broadly will underperform both the index and its own history.

This signal does **not** tell you what to do. It explains context: a strategy's
strong year during narrow mega-cap leadership looks different from the same return
delivered when breadth was healthy. Use it to annotate the year-by-year table rather
than to gate entries.

## Step 4 — Identify the honest story

After Steps 1–3, answer these questions in plain language before writing the report:

1. Which years, regimes, and assets are **structural** contributors (appear across many
   conditions) vs **episodic** (appear once, in specific circumstances)?
2. Is the win rate above 50% across most year/regime combinations, or does a high total
   return mask a low win rate compensated by large winners?
3. How would the multi-year compound return look if the single best asset were excluded?
   If the single best year were excluded?
4. Is there evidence of **concentration risk** — the strategy implicitly depending on
   a specific name, sector, or macro event continuing to repeat?

These answers form the body of the attribution report. They are more useful than any
single metric.

## Report structure

ALWAYS produce the attribution as this exact structure:

```
# Performance Attribution: <strategy name>

## Year-by-Year Summary
| Year | Trades | Win Rate | Return | Max DD | Avg Hold | Benchmark | Notes |
|------|--------|----------|--------|--------|----------|-----------|-------|
<one row per year>

Compounded multi-year return: XX%   (arithmetic average: XX%/yr)

## Regime Breakdown
| Regime  | Trades | Win Rate | Avg Return/Trade | Total Contribution |
|---------|--------|----------|------------------|--------------------|
<bull / neutral / bear rows>

Regime observation: <1–2 sentences on whether the strategy is genuinely regime-adaptive.>

## Per-Asset Delta
| Asset | Years Active | Contribution | Marginal Impact (excl.) | Dependence Flag |
|-------|-------------|--------------|-------------------------|-----------------|
<top contributors and any flagged names>

Breadth context: <RSP-SPY divergence note for the most impactful year(s), if applicable.>

## Concentration Assessment
<Paragraph: how fragile is the return stream? One-asset or one-year removal test.>

## What Looks Structural vs Episodic
<Bullet list: which wins repeat across conditions, which were one-time circumstances.>

## Honest Summary
<2–4 sentences: what the numbers actually say about the robustness of this strategy,
without overstating forward expectations. Backtests don't predict the future.>
```

## A worked micro-example

**Setup:** A strategy reports +68% over three years. The year-by-year table shows:

```
Year | Return | Trades | Win Rate | Regime at most entries
2021 | +47%   |  35    |  63%     | bull
2022 |  -8%   |  39    |  41%     | bear/neutral
2023 | +29%   |  32    |  66%     | bull
```

**What the table shows:** The strategy earned in bull years and gave back in bear.
That is expected and not by itself disqualifying.

**What per-asset delta reveals:** Running the exclusion test shows that one tech name
accounted for approximately 18 percentage points of the 2023 return. Without it,
2023 is roughly +11%. That single name was also the top contributor in 2021.

**What breadth divergence adds:** In 2023, RSP underperformed SPY by approximately
12 pp over the trailing year — narrow mega-cap leadership. The strategy's outperformance
that year coincides almost exactly with the window of narrow breadth, suggesting it was
holding the names that *were* the market concentration, not demonstrating broad alpha.

**The honest story:** The strategy is long-oriented, regime-sensitive in the right
direction, and has a structurally positive win rate. But a single position family is
responsible for a disproportionate share of the compound return, and the best
performance years coincide with narrow market leadership conditions. A forward
scenario where breadth is healthier and large-cap tech underperforms would look
materially different. This is not a flaw to fix immediately — it is a risk to disclose
and monitor.

**Before-vs-after framing:** The difference between a naive read ("strategy returned
+68% in three years") and an attributed read ("two bull years carried the result; one
name drove roughly a third of total profit; bear-regime performance was negative and
needs work") is the difference between deploying capital confidently and deploying it
with appropriate position sizing and regime filters.

## When the user wants more depth

If the attribution reveals heavy concentration or regime dependence, the natural next
steps are:

- **Regime-position-sizing skill** — examine whether position sizes in bear and neutral
  regimes are proportionate to the evidence for each trade.
- **Walk-forward-validation skill** — confirm that the structural contributors hold up
  on out-of-sample data, not just the training period.
- **Anti-overfit skill** — if many parameters were tuned to the years that happen to
  be the best contributors, the attribution may be measuring curve-fit rather than edge.

Do not re-run the backtest with modified parameters as part of attribution. Attribution
describes what exists; optimization is a separate step that should follow a clean
understanding of the current result.


<!-- strongskills-brand -->

---

*Made with a StrongSkills tool — The shortcut to the cutting edge · getstrongskills.com*
