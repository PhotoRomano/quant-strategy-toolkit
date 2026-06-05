# Point-in-Time Universe Sources

This reference catalogs data sources for building a historically accurate, point-in-time backtest
universe — one that includes the symbols that *were* eligible on a given date, including companies
that later delisted, went bankrupt, or were removed from an index.

No backtest return numbers are implied or endorsed. These sources allow you to build an honest
universe; whether the strategy is profitable is a separate question entirely.

---

## What "point-in-time" means for a universe

A point-in-time (PIT) universe for date `D` contains every symbol that was:
1. Listed on the relevant exchange on `D`.
2. A member of the relevant index (if index-constrained) on `D`.
3. Liquid enough to trade on `D` — measured using historical volume, not today's.

It explicitly includes symbols that subsequently delisted, were merged, or went bankrupt — because
those names, and their eventual losses, were part of the investable universe at the time.

---

## Free and open sources

### 1. Hand-built historical CSVs
- **What:** Manually assembled tables of index membership with `date_added` and `date_removed`
  columns. Tedious to build but free and fully controllable.
- **Where to get historical S&P 500 changes:** Wikipedia "List of S&P 500 companies" change table
  (the second table on the page) records additions and deletions by date going back years. Scrape
  it once, store locally, and use it as your membership filter.
- **Limitation:** Wikipedia is community-maintained; spot-check entries against press releases for
  critical dates. Does not include full OHLCV history for delisted names.

### 2. SEC EDGAR historical filings
- **What:** 10-K, 10-Q, and DEF 14A filings provide CIK → ticker mappings at filing date, which
  gives evidence that a company existed and was reporting on that date.
- **API:** `https://efts.sec.gov/LATEST/search-index?q=...&dateRange=custom&startdt=...&enddt=...`
- **Limitation:** Gives existence evidence; does not provide OHLCV data for delisted names.

### 3. OpenBB historical constituents
- **What:** The `openbb` Python library has an `economy.available_indices()` and constituent
  endpoint that, for some indices, returns historical membership snapshots.
- **Limitation:** Coverage is inconsistent; verify the as-of date semantics for the specific
  index you need.

### 4. Stooq / Yahoo Finance delisted tickers
- **What:** Stooq.com sometimes retains historical price data for delisted tickers in its flat
  file downloads. yfinance occasionally returns data for delisted names if you provide the
  correct ticker string (e.g., appending `.DE` or using the CUSIP).
- **Limitation:** Coverage is incomplete and inconsistent. Treat returned data skeptically and
  cross-check against a known source.

### 5. Academic data repositories
- **WRDS / CRSP samples:** Some university data libraries provide limited CRSP sample datasets
  for academic use. If you have university affiliation, check your institution's WRDS access.
- **Ken French Data Library:** Provides factor portfolio returns computed on survivorship-free
  universes, useful for benchmarking but not for strategy-level simulation.

---

## Low-cost paid sources

### Sharadar Core US Equities (Nasdaq Data Link)
- **What:** A clean, point-in-time fundamental and price dataset covering active and delisted US
  equities. Includes a `TICKERS` table with `firstpricedate` and `lastpricedate` for each symbol,
  enabling proper historical membership filtering.
- **Price range:** Subscription-based; check current pricing at data.nasdaq.com.
- **Best for:** Small to mid-size backtesting projects that need fundamentals + price history for
  delisted names without institutional data costs.
- **Integration pattern:**
  ```python
  import nasdaqdatalink
  tickers = nasdaqdatalink.get_table("SHARADAR/TICKERS", table="SF1")
  # filter: firstpricedate <= D and (lastpricedate is null or lastpricedate >= D)
  universe_as_of_D = tickers.loc[
      (tickers["firstpricedate"] <= D) &
      (tickers["lastpricedate"].isna() | (tickers["lastpricedate"] >= D)),
      "ticker"
  ].tolist()
  ```

### Norgate Data
- **What:** High-quality historical US and AU equity data including delisted names, with point-in-
  time index membership for major US indices (S&P 500, Russell 1000/2000, etc.).
- **Integration:** Uses a proprietary Python API (`norgatedata` package) that directly queries
  membership by date: `norgatedata.index_constituent_timeseries(index_name, start_date, end_date)`.
- **Best for:** Serious retail backtesting; handles delisting adjustments and corporate actions.

### Polygon.io
- **What:** Real-time and historical market data API. The `v3/reference/tickers` endpoint returns
  ticker metadata including `list_date` (IPO) and can be filtered by active status at a point in
  time using `date` parameter.
- **Limitation:** Historical membership for specific indices (S&P 500) requires cross-referencing;
  Polygon provides listing/delisting dates but not index constituent history natively.
- **Best for:** Recent windows (2010–present) where listing/delisting dates are reliable.

---

## Institutional sources

### CRSP (Center for Research in Security Prices)
- **What:** The academic gold standard. Full US equity history including delisted names, with
  PERMNO identifiers that survive ticker changes and corporate events. Available via Wharton WRDS.
- **Best for:** Academic research and institutional-grade backtesting.
- **Access:** Requires WRDS subscription (institutional) or university affiliation.

### Compustat
- **What:** Financial statement data and price history, also via WRDS. The `GVKEY` identifier
  persists through name changes and mergers.
- **Best for:** Fundamental-driven strategies requiring survivorship-free financial data.

---

## Approximate (best-effort) approaches

When no paid source is available, these conservative approximations reduce (but do not eliminate)
survivorship bias:

1. **Restrict to large, stable names.** Use only companies with a long, unbroken price history
   and very large market caps throughout the window. The bias still exists but is smaller because
   mega-caps rarely delist.

2. **Apply a haircut to reported results.** Acknowledge in any report that the universe is
   survivorship-biased and that live performance is likely to be materially lower. Some
   practitioners apply a rough 1–3% per annum deduction as a conservative adjustment, but this is
   illustrative, not a formula — actual impact depends on universe size, holding period, and market
   conditions during the backtest window.

3. **Validate on a known-clean subset.** Run the strategy on the Dow 30 historical members (a
   small universe with well-documented, publicly available historical changes) as a sanity check.

---

## Integrating historical membership into a typical screener funnel

The standard funnel pattern:

```
Full historical universe (PIT)
    ↓ index membership gate (was it in the index on D?)
    ↓ listing gate (was it listed and trading on D?)
    ↓ liquidity gate (historical avg volume on D, not today's)
    ↓ quality / fundamental gate (using PIT fundamentals)
    ↓ scoring / signal engine
```

The most common bug is applying the liquidity or quality gate using *current* data before the
historical membership gate. Always establish historical eligibility first, then apply filters using
the data that was available on each decision date.
