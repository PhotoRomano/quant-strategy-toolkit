# Look-Ahead Leak Patterns — Catalog

Detailed reference for the audit. Each entry: what it is, why it leaks, the danger sign in
code, and the fix. Read the entry that matches the data source you're auditing.

## Table of contents
1. Price/volume time series
2. Point-in-time fundamentals (the big one)
3. Macro / economic series (release lag)
4. News & sentiment
5. Universe & survivorship bias
6. Normalization, scaling, and model fitting
7. Labels / target leakage
8. Caches & precomputed features
9. Corporate actions (splits, dividends, symbol changes)
10. Execution-price realism

---

## 1. Price/volume time series

**Leaks when:** a rolling/aggregate stat is computed over a frame that still contains rows
*after* the decision date `D`, then indexed with `.iloc[-1]`/`.tail(1)`.

**Danger signs:**
- `df["close"].iloc[-1]` where `df` is the full history, not sliced to `D`
- `.rolling(...).mean().iloc[-1]` without a preceding `.loc[:D]`
- `.shift(-1)` or any negative shift (pulls a future value into the present row)
- `.fillna(method="bfill")` / `.interpolate()` over the full series before walk-forward
  (back-fill carries future values backward across NaNs)

**Fix:** slice first, compute second:
```python
hist = series.loc[:D].dropna()
val = hist.rolling(n).mean().iloc[-1]
```

## 2. Point-in-time fundamentals (the most common high-severity leak)

**Leaks when:** earnings, revenue, margins, ratios, share counts, or any financial-statement
figure is read at its *as-reported-today* value for a past date. Companies restate; databases
overwrite. Using the restated number is using information that didn't exist yet.

Also leaks when a figure is attributed to the **period end** rather than the **filing date**.
Q2 ending June 30 might not be filed until early August — using it on July 1 is a ~5-week leak.

**Danger signs:**
- A fundamentals table queried by `period_end` / `fiscal_quarter` with no filing-date predicate
- `WHERE ticker = ?` with no `AND as_of_date <= ?` / `AND filing_date <= ?`
- A single "latest" row per company (no historical vintages = no point-in-time data at all)

**Fix:** store and gate on the publication/effective date:
```sql
SELECT * FROM fundamentals
WHERE ticker = :t AND filing_date <= :D
ORDER BY filing_date DESC LIMIT 1;
```
If the data source only has as-reported values (no vintages), say so in "What I Could Not
Verify" — you cannot fully clear it, and that's a real limitation worth disclosing.

## 3. Macro / economic series (release lag)

**Leaks when:** an economic series (CPI, GDP, payrolls, credit spreads, yield curve) is used on
a date before it was published. These describe a reference period but are released with a lag,
and many are revised afterward.

**Danger signs:** indexing a macro series by reference month/quarter; no separate release-date
column; using a provider's revised final series for historical dates.

**Fix:** gate on the **release date**. If only the reference period is available, lag it
conservatively (e.g., treat monthly data as available only after the typical release delay) and
note the approximation. Prefer vintage/ALFRED-style data where each value carries its first
release date.

## 4. News & sentiment

**Leaks when:** a news item or aggregate sentiment is attributed to a date earlier than its
publish timestamp, or when "today's" sentiment snapshot is applied to past dates.

**Danger signs:** sentiment keyed by article *subject date* instead of *publish time*; a single
sentiment score reused across the whole backtest; an API that returns current sentiment with no
historical timestamping.

**Fix:** bucket by a decision-aligned key derived from the publish timestamp (e.g., ISO week:
`(year, isoweek)` from `published_at`), and only read buckets whose key is `<= D`. Persist the
computed scores to a cache so re-runs are deterministic (live APIs drift).

## 5. Universe & survivorship bias

**Leaks when:** the tradable set is today's membership applied to the past. Today's index has
already dropped the bankruptcies and delistings — backtesting on it quietly removes the losers.

**Danger signs:** a hardcoded ticker list "as of now"; pulling current index constituents;
filtering out tickers that "have no recent data" (that's exactly how you delete the failures).

**Fix:** use point-in-time constituent lists (the membership as of `D`), include delisted
names with their final prices, and never drop a symbol just because it stopped trading later.

**Note on selection bias:** even a survivorship-clean universe can be hindsight-picked by a
human ("I added NVDA because I know it ran"). That's design bias, not a code leak — disclose it
separately (see SKILL.md step 3).

## 6. Normalization, scaling, and model fitting

**Leaks when:** any statistic used to transform features — mean, std, min/max, quantile bins,
PCA components, or a trained model — is fit on data that includes the future.

**Danger signs:** `scaler.fit(X_all)` then transform inside the loop; `StandardScaler` /
`MinMaxScaler` fit once on the whole dataset; z-scores using full-sample mean/std; a model
`.fit()` call outside the per-date (or per-fold, walk-forward) loop.

**Fix:** fit transforms and models using only `<= D` data — expanding-window or walk-forward
refits. For cross-validation, use time-series splits (no shuffling across the time boundary).

## 7. Labels / target leakage

**Leaks when:** the prediction target (e.g., forward return) sneaks into the feature set,
directly or via a tightly correlated proxy computed over an overlapping future window.

**Danger signs:** a feature and the label both derived from the same forward window; features
that use `.shift(-n)`; "current period return" used to predict "current period direction."

**Fix:** ensure every feature is computable strictly from data at or before `D`, and the label
strictly from data after `D`. Audit any feature whose importance is suspiciously high.

## 8. Caches & precomputed features

**Leaks when:** a precompute step (feature store, approvals list, signal cache) is built once
over the full history without date gating, then read during walk-forward.

**Danger signs:** a "precompute" script with no per-date logic; a cache keyed only by symbol;
features written before the backtest loop with global stats.

**Fix:** the cache must itself be point-in-time — either keyed by `(symbol, D)` or rebuilt
within the expanding window. Audit the cache builder, not just the consumer.

## 9. Corporate actions (splits, dividends, symbol changes)

**Leaks when:** split/dividend adjustments use the *full* adjustment factor (which includes
future splits) for historical prices, or a ticker's current symbol is used for a period when it
traded under a different one.

**Danger signs:** adjusted-close series where the adjustment reflects splits after `D`; symbol
remaps applied globally.

**Fix:** use as-of adjustment factors (only corporate actions `<= D`), or be consistent and use
deltas/returns rather than absolute adjusted levels when comparing across data vintages.

## 10. Execution-price realism (adjacent, not strictly look-ahead)

Not future-data per se, but commonly bundled with look-ahead audits because it inflates results
the same way: filling at the *close* of the signal day (you couldn't have known the close at
the moment you decided), using the day's low for buys / high for sells, ignoring slippage,
spread, and liquidity. Flag these as execution-optimism even when temporal gating is clean.

**Fix:** fill at next-bar open (or with a realistic delay), apply slippage/fees, and cap size
by historical volume.

---

## Quick grep checklist

Run these against the strategy code and inspect each hit:

```
\.iloc\[-1\]        # last row — is the frame sliced to D first?
\.tail\(            # same risk
\.shift\(-          # negative shift = future pulled backward
\.fit\(             # scaler/model fit — inside the walk-forward loop?
fillna|interpolate  # over full series before the walk-forward?
SELECT .* FROM      # any date predicate (WHERE ... <= D)?
constituents|universe  # point-in-time or today's list?
```

A hit is not automatically a bug — but every hit must be explained in the audit report as
either gated (and how) or a confirmed leak (with the fix).
