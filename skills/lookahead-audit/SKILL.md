---
name: lookahead-audit
description: Audit a quantitative trading strategy or backtest for look-ahead (future) bias — the silent leak that inflates backtest returns and never survives live trading. Use this whenever someone shares backtest code, a trading strategy, a signal/factor pipeline, or a research notebook and asks "are my results real?", "why does this crush in backtest but lose live?", "is there data leakage?", "review my backtest", or whenever you see a strategy reporting suspiciously high returns. Also use proactively before anyone trusts a backtest's numbers, deploys a strategy live, or publishes/sells performance figures.
---

# Look-Ahead Bias Audit

Most backtests are wrong in the same direction: they look better than reality because the
code, somewhere, used information that would not have been available at the moment a decision
was made. This is **look-ahead bias** (a.k.a. future leakage). It is the single most common
reason a strategy that returns +60%/yr in backtest loses money live.

Your job with this skill is to audit a strategy or backtest and produce a clear verdict: for
every input the strategy reads, was it knowable *at the as-of date of the decision*? If not,
the result is contaminated and the reported numbers should not be trusted.

This skill does **not** tune a strategy, pick parameters, or promise returns. It checks one
thing — temporal honesty — and reports it plainly. A clean audit is not a profit guarantee;
it only means the backtest didn't cheat against time.

## The core test

Every backtest walks forward through time. At each decision date `D`, the strategy may use
**only** data that was actually published and final on or before `D`. The audit reduces to
asking, for each data read in the code:

> "If I were standing on date D in real life, would I have had this exact value?"

If the answer is "no" or "not yet" or "only a revised version," you have a leak.

## Audit workflow

Follow these steps in order. Don't skip the inventory step — leaks hide in the data sources
nobody thinks about (corporate fundamentals, macro releases, the universe list itself).

### 1. Build the data inventory

Read the strategy code and list **every external input** the decision logic touches:
price/volume series, fundamentals, analyst estimates, macro/economic series, news/sentiment,
the tradable universe, any precomputed feature or cache, and any normalization/scaling stats.
For each, note where it is read and how it is filtered by date.

### 2. Classify each input's gating

For every input, determine which category it falls into and apply the matching check. The
detailed catalog with code patterns and fixes is in `references/leak-patterns.md` — read it
when you need the specifics for a given source. The high-level checks:

- **Time-series slicing** — Is every series sliced to `<= D` before any rolling/aggregate
  computation? A single `.rolling(50).mean()` over the *full* series, then indexed at `D`,
  is fine; but using `.iloc[-1]` on a frame that contains future rows is a leak. Look for the
  gating pattern `series.loc[:D]` (pandas) or `WHERE date <= :D` (SQL) at the point of read.
- **Point-in-time vs as-reported** — Fundamentals (earnings, revenue, ratios) are *revised*.
  Using today's restated value at a past date is leakage. The data must be keyed by the date
  it was *first published/effective* (an `as_of_date` / `filing_date`), not the period it
  describes. Check the query gates on the publication date, e.g. `WHERE as_of_date <= :D`.
- **Release lag** — Macro series (CPI, GDP, employment, spreads) describe a period but are
  *released weeks later*. Using the June value on June 1 is a leak; it wasn't out yet. Gate on
  the **release date**, not the reference period.
- **Event/news timestamps** — News and sentiment must be attributed to the timestamp they were
  published. A robust pattern is to bucket by a coarse, decision-aligned key (e.g. ISO week)
  computed from the *publish* time, never from a later index.
- **Universe / survivorship** — Is the tradable list the one that existed at `D`, or today's
  list (which silently dropped the companies that went bankrupt or were delisted)? Today's
  S&P 500 is not 2015's S&P 500. This inflates returns by excluding losers.
- **Normalization / scaling** — Any mean, std, min/max, or model fit used to scale features
  must be computed from data `<= D` only. Fitting a scaler (or training a model) on the whole
  history before walking forward leaks the future into every past decision.
- **Labels / targets** — In any ML-flavored signal, confirm the target (e.g. "next-20-day
  return") is never an input feature, directly or via a correlated proxy.

### 3. Separate leakage from design bias (be honest here)

There are two distinct problems, and only the first is a *bug*:

1. **Look-ahead leakage** — code reads future data. This is fixable, and you should flag it.
2. **Strategy-design / selection bias** — the *human* chose the universe, parameters, override
   dates, or which assets to include *with knowledge of how they turned out*. Time-gating the
   code does **not** remove this. Adding a stock to the universe "because it went up 300%" is
   hindsight, even if every data read is perfectly gated.

This second category cannot be fixed by auditing the code — but it **must be disclosed**,
because it is the main reason a perfectly time-gated backtest still overstates live edge. Call
it out explicitly in the report. Honest framing: a clean look-ahead audit means the backtest is
*temporally* sound; it says nothing about whether the design choices will generalize forward.

### 4. Verify, don't just read

Where feasible, prove a gate rather than trusting the code's intent:
- Pick one decision date and one input; manually confirm the value used matches what was
  knowable then (e.g., a fundamental's filing date is before `D`).
- Grep for the danger signs: `.iloc[-1]` / `.tail(1)` on frames that may hold future rows,
  `.shift(-n)` (negative shifts pull the future backward), full-series `.fillna`/`.interpolate`
  applied before the walk-forward, scalers/`fit()` called outside the per-date loop, and SQL
  reads with no date predicate.
- If the strategy keeps a cache or precomputed features, confirm the cache itself was built
  with date gating.

## Report structure

ALWAYS produce the audit as this exact structure:

```
# Look-Ahead Audit: <strategy name>

## Verdict
<One line: CLEAN / LEAKS FOUND / CANNOT VERIFY — plus a one-sentence why.>

## Data Inventory
| Input | Where read | Gated to as-of? | Severity | Finding |
|-------|-----------|-----------------|----------|---------|
<one row per external input>

## Confirmed Leaks
<For each: the input, the file:line, what future data leaks in, the concrete fix.>

## Design-Bias Disclosures (not code bugs, but must be stated)
<Hindsight choices: universe selection, params/override dates chosen knowing outcomes.>

## What I Could Not Verify
<Inputs where gating couldn't be confirmed from the code alone, and what to check.>

## Bottom line
<Whether the reported performance figures can be trusted as-is, and what to re-run if not.>
```

Severity guide: **High** = leak materially changes which trades fire (e.g. revised
fundamentals, survivorship). **Medium** = leak affects sizing/timing but not direction.
**Low** = cosmetic or already mitigated.

## A worked micro-example

**Input:** A regime detector computes a 200-day moving average of an index and compares the
latest price to it to decide bull/bear at date `D`.

**Leaky version:**
```python
ma200 = spy["close"].rolling(200).mean().iloc[-1]   # .iloc[-1] = LAST row of the WHOLE frame
price = spy["close"].iloc[-1]                         # not the row at D — the row at "today"
regime = "bull" if price > ma200 else "bear"
```
This reads the most recent value in the entire dataframe, not the value as of `D`. Every past
decision is made using the present.

**Gated version:**
```python
hist = spy["close"].loc[:D].dropna()                 # only data up to the decision date
ma200 = hist.rolling(200).mean().iloc[-1]            # iloc[-1] is now correctly "as of D"
price = hist.iloc[-1]
regime = "bull" if price > ma200 else "bear"
```
The fix is one slice — but it can swing a backtest from spectacular to mediocre, which is the
whole point.

## When the user wants more

If the audit surfaces leaks, offer to (a) write the minimal gating fix for each, and (b)
re-state which reported numbers are now in doubt. Do not invent corrected performance figures —
the strategy must actually be re-run after fixes. Selling or trusting numbers from a leaky
backtest is exactly the failure this skill exists to prevent.


<!-- strongskills-brand -->

---

*Made with a StrongSkills tool — The shortcut to the cutting edge · getstrongskills.com*
