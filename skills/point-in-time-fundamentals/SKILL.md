---
name: point-in-time-fundamentals
description: Gate fundamental data on the date it was actually filed/published, not the period it describes — preventing the single most common and least-visible source of look-ahead bias in factor and quality-score backtests. Use this whenever someone asks "how do I backtest fundamental signals without cheating?", "how do I use earnings data historically?", "what is point-in-time data?", "how do I avoid using restated financials in my backtest?", "why does my quality factor work in backtest but not live?", "how do I handle SEC EDGAR filing dates?", or "how do I build a historical fundamental approval cache?". Also use proactively whenever you see code reading financial statement data (revenue, earnings, ratios, balance sheet, cash flow) inside a walk-forward loop without an explicit filing-date gate.
---

# Point-in-Time Fundamentals

A company's quarterly revenue figure describes a period that ended, say, June 30. But you
did not know that number on June 30 — the 10-Q was filed weeks later. If your backtest
reads the June 30 value on June 30, it is using information that did not exist yet. This
is the core point-in-time problem: **accounting period-end dates are not the same as
data availability dates**.

This is distinct from the general look-ahead audit covered by the sibling `lookahead-audit`
skill. This skill goes deeper on the specific mechanics of fundamental data: filing lags,
XBRL fact gating, restatements, stale-data penalties, and how to build or verify an
approval cache that is provably clean.

A clean point-in-time implementation does not guarantee the strategy is profitable.
It only guarantees that your fundamental scores reflect what was knowable at each
decision date.

## Why this matters more than it looks

Fundamental factors — Piotroski F-Score, Altman Z, Beneish M, ROIC, Sloan Accrual
Ratio — are computed from annual and quarterly filings. Those filings:

- Are released on a **filing date**, not the period-end date
- Are sometimes **restated** months or years after first release
- Have different lags by filing type: 10-K (annual, up to 60 days), 10-Q (quarterly, up to 40 days)
- May arrive in your data vendor with the **restated** value already substituted, silently

Using the most-current value for a past decision date contaminates every fundamental
score you compute. The magnitude of contamination is large: restatements exist precisely
because the as-reported number was wrong or incomplete. A Beneish M-Score that just barely
passes today may have been a hard fail when the original filing hit.

## The correct gating model

For every fundamental data point, two dates matter:

```
period_end_date   — the last day of the quarter/year the fact describes
filed_date        — the day the filing was submitted to the regulator
```

Your backtest gate must be on `filed_date`, not `period_end_date`:

```python
# LEAKY — uses period end, ignores when the filing actually arrived
WHERE period_end <= :decision_date

# CORRECT — only uses facts the market actually had
WHERE filed_date <= :decision_date
```

The intuition: standing on `decision_date` in real time, you could read any filing whose
`filed_date` is on or before that date. You could not read any filing whose `filed_date`
is in the future, even if its `period_end` was already in the past.

## Workflow

### 1. Identify your data source's time dimension

Before fixing anything, determine what timestamps your source exposes:

| Source | What it gives you | PIT-safe by default? |
|--------|------------------|----------------------|
| yfinance `.income_stmt` | Period-end columns only | No — always returns latest/restated values |
| SEC EDGAR XBRL (data.sec.gov) | Each fact has `filed`, `end`, `form` fields | Yes — if you gate on `filed` |
| Compustat (via WRDS) | `datadate` (period end) + `rdq` (report date) | Gate on `rdq`, not `datadate` |
| FactSet / Bloomberg | Varies by dataset; check vendor docs | Check for an `as_of` or `publication_date` field |
| Pandas-datareader / Alpha Vantage | Period-end only | No — same problem as yfinance |

The safest sources include an explicit filing date per data point. If your source only
gives period-end dates, add a fixed lag (see section 3) as a conservative approximation —
but understand it is an approximation, not a true PIT implementation.

### 2. Gate on filed_date in every query

When reading from an XBRL-style store (each row has a `filed` field):

```python
# Leaky — selects by period end, no filing date gate
candidates = [v for v in fact_values if v["end"] <= as_of_date]

# Correct — gate on when the filing actually arrived
candidates = [v for v in fact_values if v["filed"] <= as_of_date]
# Then take the most recent among those that passed the gate
candidates.sort(key=lambda v: (v["filed"], v["end"]), reverse=True)
value = candidates[0]["val"] if candidates else None
```

When reading from a SQL approval cache (pre-computed per quarter):

```sql
-- Correct: get the most recent approval that was computed on or before the decision date
SELECT a.symbol, a.approved
FROM approvals a
INNER JOIN (
    SELECT symbol, MAX(as_of_date) AS max_date
    FROM approvals
    WHERE as_of_date <= :decision_date    -- <-- the gate
    GROUP BY symbol
) latest ON a.symbol = latest.symbol
       AND a.as_of_date = latest.max_date
```

The double-query pattern (inner join to find the `max_date` per symbol, then join back)
is the standard safe pattern. A simpler `WHERE as_of_date <= :d ORDER BY as_of_date DESC
LIMIT 1` also works for single-symbol queries.

### 3. Apply a filing lag when true PIT dates are unavailable

If your source gives period-end dates only, add a conservative lag before making data
available in the backtest:

- **10-K (annual):** up to 60 calendar days after fiscal year-end for large accelerated filers;
  use 60–90 days as a safe buffer.
- **10-Q (quarterly):** up to 40 days for large accelerated filers; use 45–60 days.
- **Earnings releases (press release):** typically 20–35 days after quarter-end; but the
  10-Q with audited detail follows weeks later. Decide which you trust.

Example: a company with a fiscal year ending December 31 should not have its annual
fundamentals available to your backtest before roughly March 1 of the following year
(December 31 + 60 days).

```python
FILING_LAG_DAYS = 60   # conservative; tune down only if you have actual filed dates

# When building the as_of_date for each quarter-end:
q_end  = date(year, month, day)           # e.g. 2022-12-31
as_of  = q_end + timedelta(days=FILING_LAG_DAYS)   # 2023-03-01
```

This is a blunt instrument. Companies file at different speeds; using their actual
`filed` date is always more accurate when available.

### 4. Handle restatements correctly

Restatements are the hardest part. A company may revise its Q3 2021 revenue figure
in its Q2 2022 filing. The question is: which version do you use at what date?

The correct answer for PIT backtesting is: **use the first-reported value, keyed to
the original filing date**. This is what an investor standing on that date would have
seen and acted upon.

Two practical approaches:

**A. Use as-filed snapshots (best)**
Store every version of each fact with its `filed` date. When querying as of date `D`,
pick the filing with the largest `filed` <= `D`. This naturally selects the most recent
*as-of-D* version of the fact, which may or may not be restated — but only reflects
information that existed on or before `D`.

```python
# Suppose each row: (concept, val, filed_date, period_end)
# Sort descending by filed_date, take the first entry with filed_date <= D
rows_as_of_D = sorted(
    [r for r in rows if r.filed_date <= D],
    key=lambda r: (r.filed_date, r.period_end),
    reverse=True
)
value = rows_as_of_D[0].val if rows_as_of_D else None
```

SEC EDGAR XBRL data has this structure natively — each entry carries `filed`, `end`,
and `val`. This is the main reason EDGAR is preferred for PIT backtesting.

**B. Apply a fixed lag and accept stale-data risk (fallback)**
If you only have the restated series, add the filing lag and accept that some values
reflect later revisions. Partially mitigate this by flagging entries where `filing_age`
(days between the period-end date and your as-of date) exceeds a threshold and applying
a haircut to any score computed from stale data:

```python
filing_age_days = (as_of_date - period_end_date).days
if filing_age_days > 180:
    # Data is more than 6 months old — a later filing may have revised it
    # Apply a penalty to the computed score rather than blocking entirely
    altman_z = round(altman_z * 0.90, 3)   # 10% haircut — illustrative starting point
```

The haircut amount should be tuned to your universe. The principle is sound: old
as-reported data is less reliable than recently filed data.

### 5. Pre-compute and cache approvals; query the cache in the backtest

Running full fundamental scoring inside the backtest walk-forward loop is slow
(many API calls or heavy SQL queries) and tempting to short-circuit in ways that
introduce bias. The robust pattern is to separate the two phases:

**Phase A — Pre-compute (offline, before the backtest):**
Walk every (symbol, quarter) pair. For each, fetch fundamentals as of that quarter's
as-of date (period-end + lag, or the actual filed date). Compute scores. Store pass/fail
and the key metrics in a local cache (SQLite is ideal). This runs once and takes minutes.

**Phase B — Query the cache (inside the backtest):**
At each decision date, query the cache for the most recent approval that is on or before
that date. Never re-compute scores inside the walk-forward loop.

This pattern guarantees the backtest cannot accidentally read fundamentals that are not
yet in the cache, because the cache was built with an explicit `as_of` gate.

### 6. Verify the gate empirically

Don't just trust the code — spot-check it:

1. Pick one symbol and one decision date. Look up the actual SEC filing date for the
   most recent 10-K or 10-Q before that decision date (SEC EDGAR search at sec.gov).
2. Confirm your code returns a value whose `filed` date matches, and that the filing
   was genuinely submitted before your decision date.
3. Check that the *next* filing (after the decision date) is NOT included.
4. Run the same check for a date immediately before a quarterly filing — confirm the
   system correctly falls back to the prior quarter's data.

## Report structure

When auditing a system for PIT compliance, produce this structure:

```
# PIT Fundamentals Audit: <system name>

## Verdict
<One line: PIT-CLEAN / PIT-LEAKY / PARTIALLY-GATED — plus a one-sentence why.>

## Data Source Inventory
| Source | Fields available | Filing date exposed? | Gate applied |
|--------|-----------------|---------------------|--------------|
<one row per fundamental data source>

## Gating Analysis
<For each source: how it is queried, what date is used as the gate, and whether
that date is the filed date, period-end date, or something else.>

## Restatement Handling
<Whether the system uses as-filed snapshots or restated values; impact.>

## Confirmed Gaps / Fixes
<Any specific code location where the gate is missing or wrong, plus the fix.>

## Stale-Data Policy
<Whether filing age is tracked and whether a haircut or staleness flag is applied.>

## Bottom line
<Whether the fundamental scores used in the backtest are PIT-sound, and if not,
what re-computation is needed.>
```

## A worked micro-example

**Scenario:** A backtest scores every stock on Piotroski F-Score quarterly and trades
the top decile. The data source is a third-party API that returns the latest annual
income statement, with column headers as the fiscal year-end date.

**Leaky version:**
```python
# Fetch annual income statement — columns are period-end dates
income = api.get_income_statement(symbol)   # returns DataFrame, columns = period-end dates

# At decision_date, take the most recent column
latest_col = income.columns[0]             # e.g. "2023-09-30" — but today is 2023-10-02!
revenue = income["Total Revenue"][latest_col]
```
On October 2, 2023, a fiscal year ending September 30 is almost certainly not yet filed.
Apple's 2023 annual 10-K was filed on November 3, 2023 — 34 days after fiscal year-end.
This code uses data that did not exist on October 2.

**Gated version:**
```python
FILING_LAG_DAYS = 60   # illustrative starting point; tune to your universe

def safe_annual_value(income_df: pd.DataFrame, decision_date: date, field: str):
    """Return the most recent annual value whose implied available date <= decision_date."""
    for col in income_df.columns:
        # col is the period-end date; add the lag to get the implied availability date
        period_end = pd.to_datetime(col).date()
        available_from = period_end + timedelta(days=FILING_LAG_DAYS)
        if available_from <= decision_date:
            return income_df[field][col]
    return None   # no filing yet available — do not score this symbol
```

The fix adds one date comparison per column lookup. It prevents the backtest from using
financial data before it could realistically have been known.

If you have actual SEC EDGAR `filed` dates (preferred), replace `period_end + lag` with
`filed_date` directly:

```python
# With EDGAR XBRL data (each entry has a 'filed' field):
candidates = [v for v in xbrl_values if v["filed"] <= decision_date.isoformat()]
if not candidates:
    return None
candidates.sort(key=lambda v: (v["filed"], v["end"]), reverse=True)
return float(candidates[0]["val"])
```

## When only as-reported data exists

Some environments (legacy data, restricted API tiers) only provide the restated, current
version of each financial fact with no historical filing dates. Options in roughly
decreasing order of quality:

1. **Switch to an EDGAR-based source** — SEC EDGAR is free, has filing dates per fact,
   and is the authoritative source. See `references/pit-data-sources.md` for setup notes.
2. **Apply a fixed lag** — Add 60 days for annual, 45 days for quarterly, accept that
   material restatements are not modeled. Flag this in any research output.
3. **Use a staleness gate** — Reject any data point whose period-end is within 60 days
   of the decision date (it would not be filed yet). Accept that recent quarters have no
   fundamental coverage and either skip scoring or carry forward the prior quarter's score.
4. **Add a filing-age haircut** — For data older than 180 days, reduce any computed score
   by a calibrated factor to reflect the higher probability of subsequent revision.

None of these approaches is as clean as true PIT data. Document whichever approach you use.

## What this skill does not cover

- General look-ahead bias in price series, universe construction, or normalization
  (see the `lookahead-audit` skill)
- Walk-forward validation methodology (see the `walk-forward-validation` skill)
- Whether the fundamental factors themselves are predictive going forward — no clean
  PIT implementation can address that

For deep detail on supported EDGAR XBRL concept names, filing type filters (10-K / 10-Q
/ 20-F), TTM construction from quarterly filings, and troubleshooting common gaps, see
`references/pit-data-sources.md`.


<!-- strongskills-brand -->

---

*Made with a StrongSkills tool — The shortcut to the cutting edge · getstrongskills.com*
