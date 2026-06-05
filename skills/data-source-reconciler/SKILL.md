---
name: data-source-reconciler
description: Reconcile multiple price and data feeds (yfinance, Alpaca, Polygon, Alpha Vantage, FRED, etc.) into a single trusted series — catching adjustment mismatches, symbol gaps, and stale data before they corrupt signals. Use this whenever someone asks "why do my returns differ between data sources?", "my backtest numbers changed when I switched from yfinance to Alpaca", "how should I handle multiple price feeds?", "which data source should I trust?", "my prices look off after a stock split", "I'm getting NaN for some symbols", or "how do I add a second source without breaking my existing pipeline?" Also use proactively before running any backtest that pulls from more than one feed, before switching a live system to a new primary source, or when a data vendor goes down and the team needs a safe fallback.
---

# Data Source Reconciler

Every quant system eventually touches more than one price feed. You need a fallback when a vendor
goes down, a second source for assets the primary doesn't cover, or a third source for a data
type (volatility, macro, fundamentals) that the primary vendor never offered. Adding sources is
additive value — but only if you understand *why* the numbers disagree, because they always do.

The core insight: **compare deltas, not absolutes**. Two sources that disagree on the price of
AAPL on Jan 15 may be perfectly consistent with each other for momentum signals, because both
apply the same split but differ only in dividend reinvestment treatment. Panicking on the absolute
difference and throwing away a source wastes coverage. Understanding the cause of the difference
lets you use both safely.

This skill does not recommend specific vendors or claim any source is more accurate for all uses.
It teaches the framework for finding, classifying, and resolving inter-source differences so your
pipeline uses every feed with confidence.

## Why sources disagree: the adjustment taxonomy

Before comparing two series, identify which adjustment type each applies. The same underlying
price data can produce meaningfully different numbers depending on this choice.

| Adjustment type | What it does | Best for |
|----------------|--------------|----------|
| **Raw / unadjusted** | No changes; shows actual traded price | Execution simulation, options strike mapping |
| **Split-only** | Rescales history for stock splits, reverse splits | Momentum, technical signals (splits change price level, not value) |
| **Fully adjusted** | Split + dividend reinvestment folded back into price | Total-return comparisons, buy-and-hold performance |

A fully-adjusted series will show a lower absolute price for a high-dividend stock (e.g., a utility
or REIT) than a split-only series — not because the data is wrong, but because dividends are being
"backed out" of the historical price. This is correct for total-return analysis and wrong for
comparing live quotes.

The most common source of confusion in multi-source pipelines: **Source A applies full adjustment,
Source B applies split-only**. Their prices diverge over time in proportion to cumulative dividends.
Neither is incorrect; they answer different questions.

## Reconciliation workflow

Follow these steps each time you add a source or investigate a discrepancy.

### 1. Inventory and classify each source

For every feed in your pipeline, record:
- **Coverage**: which symbols, which date range, which fields (OHLCV, fundamentals, news, etc.)
- **Adjustment type**: raw, split-only, or fully adjusted (check the vendor docs or the API parameter)
- **Role**: primary (always queried first), supplemental (covers symbols the primary misses),
  fallback (queried only when the primary fails), or exclusive (only source for this data type)

Sources should be additive, not competing. Assign each source a role before reconciling.

### 2. Build a delta comparison, not an absolute comparison

Never compare raw prices across sources and declare one "right." Instead:

1. Choose a shared anchor: a well-known, high-liquidity, non-dividend-paying index ETF such as
   SPY or QQQ. These have essentially no dividend drag, so fully adjusted and split-only series
   are nearly identical — eliminating dividend confusion.
2. Compute the same **percentage return** (e.g. 20-day return) from each source for the anchor.
3. If the two return series agree within a tight tolerance (e.g. ±0.1 pp per period), the
   sources are consistent for momentum signals — even if their absolute prices differ.
4. Then check a high-dividend name. If the return series diverge, you have found an adjustment
   mismatch. Check the `adjustment` / `auto_adjust` parameter on each source.

```python
# Compare 20-day returns from two sources
def returns_20d(series: pd.Series) -> pd.Series:
    return series.pct_change(20).dropna()

r_primary     = returns_20d(primary_df["SPY"])
r_supplemental = returns_20d(supplemental_df["SPY"])

diff = (r_primary - r_supplemental).abs()
print(f"Max delta (SPY 20d return): {diff.max():.4f}")
print(f"Mean delta (SPY 20d return): {diff.mean():.4f}")
```

If the max delta is below your signal resolution (e.g. 0.001 for a system that uses 5%+ moves),
the sources are fungible for that signal. If it is material, investigate before mixing.

### 3. Classify the discrepancy

Once you confirm a real difference, determine the cause before deciding which source to use:

| Symptom | Likely cause | Resolution |
|---------|-------------|------------|
| Prices diverge gradually over years | Adjustment type mismatch (split-only vs fully adjusted) | Standardize adjustment parameter across sources |
| Prices jump on one date, then track again | Split reflected on different dates | Use the source that applied the split on the actual ex-date |
| One source missing a symbol entirely | Coverage gap | Assign supplemental source for that symbol |
| Both sources have the symbol but disagree on recent bars | Stale cache or delayed feed | Add freshness check; prefer the source with the later last-update |
| Large differences on a single day | Corporate action (merger, spinoff, special dividend) | Verify against exchange records; neither source may be "right" |

### 4. Normalize to one adjustment type for the pipeline

Pick **one adjustment type** for your signals and enforce it across all sources. Momentum signals
should use the same type. Split-only is a reasonable default for pure price-momentum systems
because it preserves the actual price level for position sizing while eliminating the split noise
that would otherwise create false momentum signals at split dates.

If you also need total-return comparisons (e.g., for benchmarking), keep a separate series with
full adjustment — but do not mix the two in the same signal calculation.

### 5. Implement a graceful fallback chain

Design the data fetch so that sources are tried in priority order, with each fallback covering
the gaps of the previous layer. The key properties of a healthy chain:

- **Single entry point**: signal code calls one function and receives a clean DataFrame; it never
  knows which source provided each column.
- **Partial fallback**: if Source A returns data for 80 of 100 symbols and Source B fills the
  remaining 20, combine them. Don't discard A's 80 because B is the fallback.
- **Explicit logging**: whenever a fallback fires, log which source was skipped and why. Silent
  fallbacks hide API failures for weeks.
- **Missing-column handling**: after the fetch, log symbols the pipeline expected but no source
  returned. These are coverage gaps, not bugs in the fetch logic.

```python
def fetch_prices(symbols: list[str], start: str, end: str) -> pd.DataFrame:
    df = _fetch_primary(symbols, start, end)

    missing = [s for s in symbols if s not in df.columns]
    if missing:
        log.warning(f"Primary missing {len(missing)} symbols — querying supplemental")
        df_supp = _fetch_supplemental(missing, start, end)
        df = pd.concat([df, df_supp], axis=1)

    still_missing = [s for s in symbols if s not in df.columns]
    if still_missing:
        log.warning(f"No source returned data for: {still_missing}")

    return df
```

### 6. Validate freshness, not just existence

A column present in the DataFrame is not the same as a column that is current. Add a freshness
check: confirm the last non-NaN row for each symbol is within an acceptable lag (e.g. 2 trading
days for daily bars). Stale data in a live signal is worse than a gap, because it produces
plausible-but-wrong prices with no visible warning.

```python
# Freshness check after loading
today = pd.Timestamp.today().normalize()
for col in df.columns:
    last_date = df[col].last_valid_index()
    if last_date is None or (today - last_date).days > 3:
        log.warning(f"[freshness] {col} last valid: {last_date} — may be stale")
```

### 7. Handle source-exclusive data types without cross-contamination

Not every source covers every data type. A vendor that excels at equity price bars may not offer
macro series (CAPE, credit spreads, yield curve), and the vendor that does offer macro may not
have intraday bars. Treat each data type as its own sub-pipeline with its own source hierarchy.

The adjustment taxonomy applies differently to different data types:

- **Volatility indices** (e.g., VIX): raw values only; no adjustment applies
- **Macro series** (CPI, CAPE, HY spreads): raw; the critical variable is the release date, not
  an adjustment type (see the lookahead-audit skill for release-lag handling)
- **Fundamentals**: point-in-time filing dates, not adjustment types, are the key concern

Keeping these as separate fetch functions prevents an equity-price fix from silently changing the
macro series. Design for independence.

## Worked micro-example: adjustment mismatch

A strategy uses 60-day momentum. It runs fine on Source A (split-only). When the developer adds
Source B as a fallback and Source B uses full adjustment, some high-dividend tickers start
scoring differently across runs — even when Source A is available.

**The problem:** the two sources are not interchangeable for the same signal call.

```python
# Broken: mixes adjustment types silently
df = source_a_df.combine_first(source_b_df)   # fills gaps with B's fully-adjusted prices
momentum_60d = df.pct_change(60)               # returns now mix adjustment types per column
```

The momentum calculation is now inconsistent: some columns use split-only prices, others use
fully-adjusted prices. The returns look correct in isolation but diverge from each other for
dividend-heavy names.

**The fix:** normalize before merging, or document the accepted divergence and signal scope.

```python
# Option 1: standardize adjustment before combining
# Source B forced to split-only mode (if the API supports it)
source_b_df = _fetch_source_b(symbols, start, end, adjustment="split")
df = source_a_df.combine_first(source_b_df)   # now both split-only

# Option 2: if Source B can't be changed, document and limit scope
# Use Source B only for non-dividend symbols (pure growth, non-dividend ETFs)
NON_DIVIDEND_SYMBOLS = {"QQQ", "NVDA", "TSLA", ...}  # illustrative; maintain your own list
fallback_candidates = [s for s in missing if s in NON_DIVIDEND_SYMBOLS]
```

Neither option is universally correct. The choice depends on the signal and the universe.
Document the decision explicitly.

## Report structure

When investigating or documenting a reconciliation, use this structure:

```
# Data Source Reconciliation: <strategy / dataset name>

## Source Inventory
| Source | Role | Coverage | Adjustment type | Notes |
|--------|------|----------|-----------------|-------|

## Discrepancy Log
| Symbol | Date range | Source A value | Source B value | Delta | Cause | Resolution |
|--------|-----------|----------------|----------------|-------|-------|------------|

## Adjustment Mismatch Assessment
<Are all sources producing the same adjustment type for the signals they feed?>
<If not, which signals are affected and what is the maximum observed delta?>

## Coverage Gaps
<Symbols expected but returned by no source. Impact on universe coverage.>

## Freshness Audit
<Symbols where the last valid date exceeds the acceptable lag threshold.>

## Recommendation
<Which sources to trust for which signals, and any pipeline changes needed.>
```

## Key principles summary

- Compare returns, not prices — percentage deltas reveal whether two sources are signal-equivalent
- Adjustment type is the most common root cause of persistent inter-source differences
- Sources are additive; build a fetch chain that uses coverage from all of them
- Log every fallback explicitly — silent fallbacks hide failures
- Keep data-type sub-pipelines independent — equity price fixes should not reach macro series
- A backtest that switches data sources mid-run is not comparable to one that used a single source throughout

Pair this skill with the **lookahead-audit** skill (to confirm that your multi-source fetch chain
is temporally sound) and the **backtest-harness** skill (to standardize how fetch functions are
invoked across experiments).

> Backtests are only as trustworthy as the data that feeds them. Reconciling sources removes one
> class of silent error — it does not predict whether the strategy will be profitable forward.


<!-- strongskills-brand -->

---

*Made with a StrongSkills tool — The shortcut to the cutting edge · getstrongskills.com*
