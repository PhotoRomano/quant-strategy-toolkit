# PIT Fundamentals — Data Sources & EDGAR Implementation Reference

Companion to the `point-in-time-fundamentals` skill. Use this when you need the
specifics of sourcing, querying, or troubleshooting historical fundamental data.

---

## SEC EDGAR XBRL (recommended free source)

### Why EDGAR is the best free PIT source

Every XBRL fact returned by the EDGAR API includes three time fields:

| Field | Meaning | Use |
|-------|---------|-----|
| `filed` | The date the company submitted the filing | Your PIT gate — `filed <= as_of_date` |
| `end` | The last day of the accounting period the fact covers | Identifies which quarter/year |
| `start` | First day of the period (duration facts only) | Used to identify TTM vs. single-period |

Because `filed` is attached to every individual fact, you can implement true PIT gating
without any lag assumptions.

### API endpoints

```
# Ticker → CIK mapping (needed first)
GET https://www.sec.gov/files/company_tickers.json

# All XBRL facts for one company
GET https://data.sec.gov/api/xbrl/companyfacts/CIK{10-digit}.json

# Submission history (includes SIC code for sector lookup)
GET https://data.sec.gov/submissions/CIK{10-digit}.json
```

Rate limits: 10 requests/second. Use a 0.12-second inter-request delay. EDGAR requires
a `User-Agent` header identifying your application and contact email.

### Bulk download option

For backtests covering many symbols and years, the bulk download is much faster than
per-company API calls:

- `companyfacts.zip` — all XBRL facts for all filers (~3 GB compressed, ~20 GB extracted)
- Released quarterly at: `https://www.sec.gov/Archives/edgar/daily-index/xbrl/companyfacts.zip`
- Extract and index by `CIK{10-digit}.json`; use local file reads instead of HTTP calls

### Standard XBRL concept names

The concept name (the key inside `us-gaap` in the EDGAR response) varies by how a company
filed. Always provide a fallback list of synonyms and try them in order.

**Income Statement (duration facts — check `start`/`end` span)**

| Financial metric | Primary concept | Common fallbacks |
|-----------------|-----------------|-----------------|
| Revenue | `RevenueFromContractWithCustomerExcludingAssessedTax` | `Revenues`, `SalesRevenueNet` |
| Cost of goods | `CostOfRevenue` | `CostOfGoodsAndServicesSold`, `CostOfGoodsSold` |
| Gross profit | `GrossProfit` | Compute as Revenue - COGS if missing |
| Operating income (EBIT) | `OperatingIncomeLoss` | `IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest` |
| Net income | `NetIncomeLoss` | `ProfitLoss`, `NetIncomeLossAvailableToCommonStockholdersBasic` |
| SG&A | `SellingGeneralAndAdministrativeExpense` | `GeneralAndAdministrativeExpense` |
| Depreciation | `DepreciationDepletionAndAmortization` | `Depreciation`, `DepreciationAndAmortization` |
| R&D | `ResearchAndDevelopmentExpense` | — |

**Balance Sheet (instant facts — use the `end` date as the balance date)**

| Financial metric | Primary concept | Common fallbacks |
|-----------------|-----------------|-----------------|
| Total assets | `Assets` | — |
| Current assets | `AssetsCurrent` | — |
| Current liabilities | `LiabilitiesCurrent` | — |
| Cash | `CashAndCashEquivalentsAtCarryingValue` | `CashAndCashEquivalents`, `CashCashEquivalentsAndShortTermInvestments` |
| Accounts receivable | `AccountsReceivableNetCurrent` | `ReceivablesNetCurrent` |
| PP&E (net) | `PropertyPlantAndEquipmentNet` | — |
| Long-term debt | `LongTermDebt` | `LongTermDebtNoncurrent`, `LongTermNotesPayable` |
| Short-term debt | `ShortTermBorrowings` | `LongTermDebtCurrent`, `NotesPayableCurrent` |
| Total liabilities | `Liabilities` | — |
| Retained earnings | `RetainedEarningsAccumulatedDeficit` | `RetainedEarnings` |
| Stockholders' equity | `StockholdersEquity` | `StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest` |
| Shares outstanding | `CommonStockSharesOutstanding` | `CommonStockSharesIssued` |
| Goodwill | `Goodwill` | — |
| Intangibles (net) | `IntangibleAssetsNetExcludingGoodwill` | `FiniteLivedIntangibleAssetsNet` |

**Cash Flow Statement (duration facts)**

| Financial metric | Primary concept | Common fallbacks |
|-----------------|-----------------|-----------------|
| Operating cash flow | `NetCashProvidedByUsedInOperatingActivities` | — |
| Capital expenditures | `PaymentsToAcquirePropertyPlantAndEquipment` | `CapitalExpendituresIncurringObligation` |

Note: EDGAR reports capex as a positive outflow. Adjust sign to match your convention
(most systems treat capex as negative in the cash flow statement).

### Filtering by filing type

Most fundamental scores require annual (10-K) data for year-over-year comparisons.
Restrict to relevant filing types using the `form` field in each XBRL entry:

```python
ANNUAL_FORMS   = {"10-K", "20-F"}          # annual; 20-F for foreign private issuers
QUARTERLY_FORMS = {"10-K", "10-Q", "20-F"} # include quarterly for TTM construction
```

Exclude `NT 10-K` (notification of late filing), `10-K/A` (amended), and `10-Q/A`
(amended quarterly) unless you specifically want amended filings. Amended filings have
a later `filed` date — including them respects PIT because you only see the amendment
after it was filed.

### Constructing TTM values

To build a trailing twelve-month figure for an income-statement metric:

1. **Preferred:** use the most recent 10-K annual value if it is within the past year.
   Annual values already represent 12 months.
2. **Alternative:** sum the four most recent quarterly values whose `filed` date
   is on or before `as_of_date`. Check that the four quarters are contiguous
   (no overlapping periods) and cover approximately 12 months.

Mixing annual and quarterly facts from different filings without checking for overlap
is a common source of double-counting.

### Handling missing concepts

Some companies use non-standard or industry-specific concept names not in the tables above.
Safe fallback chain:

1. Try each concept name in your list in order; return the first non-null match.
2. For gross profit specifically: if `GrossProfit` is missing, compute Revenue - COGS.
3. For total liabilities: if `Liabilities` is missing, try `LiabilitiesAndStockholdersEquity`
   minus `StockholdersEquity`.
4. If a critical metric (e.g., total assets) is completely unavailable, return `None`
   for the score rather than substituting a default. Prefer explicit data gaps over
   silent errors.

---

## Compustat / WRDS

Compustat exposes two date fields per annual observation:

- `datadate` — fiscal period-end date (NOT safe for PIT gating)
- `rdq` — the earnings announcement date (report date quarter); use this as the
  availability date for quarterly data

For annual 10-K data, use `rdq` of the Q4 observation of the fiscal year as a proxy
for when the full-year filing became public. This still slightly precedes the 10-K
`filed` date but is much closer than `datadate`.

---

## yfinance (live/current use only)

yfinance returns only the most recent (restated) values keyed to period-end dates.
It has no `filed` date per fact. It is appropriate for:

- Computing fundamental scores for a current live-trading decision
- Cache invalidation: detecting when a new earnings report has arrived since the
  last cache write (compare the most recent period-end column against a stored
  `last_seen_period_end`)

It is not appropriate for historical backtests that need PIT accuracy. If yfinance
is your only source, add the fixed-lag approximation and flag the limitation.

---

## Pre-compute cache design

When backtesting across many dates and symbols, pre-compute and cache fundamental
approvals rather than scoring inside the walk-forward loop.

### Recommended schema (SQLite)

```sql
CREATE TABLE approvals (
    symbol          TEXT    NOT NULL,
    as_of_date      TEXT    NOT NULL,  -- YYYY-MM-DD; the date the score is valid FROM
    computed_at     TEXT    DEFAULT (datetime('now')),
    approved        INTEGER NOT NULL,  -- 1 = pass all layers, 0 = fail
    fail_phase      TEXT,              -- "L1-survival", "L1-integrity", "L2", "L3", "no_data"
    -- Key scores for debugging / analysis
    altman_z        REAL,
    beneish_m       REAL,
    piotroski_f     INTEGER,
    sloan_ratio     REAL,
    sector          TEXT,
    PRIMARY KEY (symbol, as_of_date)
);
```

### Choosing as_of_date values

Pre-compute one entry per (symbol, quarter). A practical cadence:

1. Enumerate all quarter-ends for your backtest range: (Mar 31, Jun 30, Sep 30, Dec 31).
2. Add your filing lag to each quarter-end to get the `as_of_date`:
   `as_of_date = quarter_end + timedelta(days=filing_lag_days)`.
3. Score the symbol using only EDGAR data with `filed <= as_of_date`.
4. The resulting approval is valid from `as_of_date` through the next quarter's
   `as_of_date` (or until overridden by a new entry).

### Querying the cache in the walk-forward loop

```python
def get_approved_symbols(conn, decision_date: str, universe: list[str]) -> set[str]:
    """
    Return symbols approved by the fundamental gate as of decision_date.
    Uses the most recent cached entry on or before decision_date.
    """
    rows = conn.execute("""
        SELECT a.symbol, a.approved
        FROM approvals a
        INNER JOIN (
            SELECT symbol, MAX(as_of_date) AS max_date
            FROM approvals
            WHERE as_of_date <= ?
            GROUP BY symbol
        ) latest
          ON a.symbol = latest.symbol
         AND a.as_of_date = latest.max_date
    """, (decision_date,)).fetchall()

    return {r["symbol"] for r in rows if r["approved"] == 1}
```

This pattern is O(n_symbols) per decision date. For large universes, add an index:

```sql
CREATE INDEX IF NOT EXISTS idx_approvals_symbol_date
    ON approvals (symbol, as_of_date DESC);
```

---

## Common bugs and fixes

| Bug | Symptom | Fix |
|-----|---------|-----|
| Gating on `period_end` instead of `filed` | Scores available 30–60 days too early | Switch gate to `filed` field |
| Taking `iloc[0]` on full DataFrame (yfinance) | Uses current period, not as-of period | Slice by available date first |
| Including `10-K/A` amendments with original filed date | Revision visible before it was filed | Use each row's own `filed` date; amendments have a later date automatically |
| Using `datetime.now()` as filed date in the cache | Future production data bleeds into old decisions | Cache `filed_date` from EDGAR; never substitute wall-clock time |
| Missing `GROUP BY symbol` in max-date subquery | Returns one row total, not one per symbol | Always group by symbol in the inner query |
| Counting the first quarter after fiscal year-end as "annual" | Under-reports 12-month totals | Filter by `fp = "FY"` or check that `end - start >= 350 days` for annual duration facts |
| Filing lag too short for small companies | Small-cap 10-Ks may file up to 90 days after year-end | Use 90 days as the lag for any company not classified as a "large accelerated filer" |
