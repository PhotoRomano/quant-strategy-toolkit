# Data Stack Guide — Reference for the Strategy Brief

This reference expands section 4 of the strategy-brief skill. Use it when your strategy consumes more than five distinct data sources, or when a technical reviewer needs full documentation of what each source provides and where its limitations lie.

## Column definitions

| Column | What to write |
|--------|--------------|
| **Tier** | The logical layer the data serves (see tier taxonomy below) |
| **Source / Authority** | Provider name and series ID or endpoint, so the data can be independently verified |
| **Data Points** | Specific fields consumed: price, volume, ratio, text, etc. |
| **How Used** | The decision it informs: regime gate, quality screen, scoring, sizing, filtering |
| **Lag / Revision Risk** | Release lag from reference period; whether values are revised after publication |
| **Point-in-Time Handling** | How the strategy avoids using data that was not available at the decision date |

## Tier taxonomy

### Tier 1 — Macro Intelligence
Sources that characterize the broad economic and credit environment. Typical examples: central bank policy series, credit spread indices, yield curve shape, cyclically adjusted valuation ratios. These series frequently have release lags (a monthly macro release describes last month, published mid-next-month) and some are subject to revision. Document the release schedule and state whether the strategy gates on the reference period or the release date. Gating on the reference period is a look-ahead error for macro data.

### Tier 2 — Market Structure
Sources that describe the current price and breadth environment of the tradable universe. Typical examples: index daily OHLCV, volatility indices, breadth indicators (equal-weight vs cap-weight divergence). Price data is generally available same-day and not subject to material revision, but note any adjustments (split/dividend-adjusted vs. unadjusted) and confirm the strategy uses a consistent series.

### Tier 3 — Fundamental Quality
Sources derived from company financial filings. Typical examples: balance sheet, income statement, cash flow statement, computed ratios. This is the highest-risk tier for look-ahead bias because financial filings describe a past period but are filed weeks or months later, and GAAP figures are subject to restatement. For any fundamental data source, document: (a) the as-of date logic — is the query gated on filing date or period date? (b) whether the data provider supplies point-in-time snapshots or only current (restated) values.

### Tier 4 — Insider and Sentiment Intelligence
Sources that capture human behavior signals. Typical examples: regulatory insider transaction filings, news sentiment feeds, analyst revision data. Document the disclosure lag for regulatory filings (they are not instantaneous) and the timestamp convention for news/sentiment — sentiment must be attributed to the time the article was published, not when it was indexed or retrieved.

### Tier 5 — Universe and Execution
The tradable list and the mechanism for entering and exiting positions. Document how the universe was constructed and whether it is point-in-time (reflecting only companies that existed and were tradable at each historical date) or survivorship-biased (using today's index composition). Also document execution assumptions: commissions, fractional shares, market-vs-limit order assumptions, and whether the backtest uses the open or close price on signal day.

## Common data-stack mistakes to disclose

**Survivorship bias in the universe.** If the backtest uses a static ticker list drawn from today's index, it excludes companies that were in the index historically but were later removed (due to bankruptcy, acquisition, delisting). This inflates returns because the backtest never takes the losses those companies generated. Disclose whether the universe is survivorship-biased and, if so, estimate the directional impact.

**Fundamental revision leakage.** Most financial data providers supply current restated values, not the value that was available at filing time. If the strategy uses a financial data API that returns today's GAAP figures for past dates, every fundamental computation in the backtest used information that was not available at the time. This is a confirmed look-ahead error. The fix requires a point-in-time data source keyed by filing date; the disclosure is that without that fix, fundamental-based screening results in the backtest overstate the real-time quality gate's ability to identify outperformers.

**Macro series release lag.** Monthly macro releases (CPI, employment, credit spreads) are typically published four to six weeks after the reference period ends. Using the June value on June 1 is a look-ahead error — it was not published yet. Disclose the release schedule for each macro series and confirm that the strategy gates on release date, not reference-period end date.

**News and sentiment timestamp confusion.** Sentiment derived from articles that were indexed hours or days after publication, or that were retrieved in bulk without preserving the publication timestamp, introduces variable look-ahead. The practical minimum is to bucket sentiment by a coarse, decision-aligned key (for example, the ISO week prior to the trade date) derived strictly from the publication timestamp.

## Example completed row

| Tier | Source | Data Points | How Used | Lag / Revision Risk | Point-in-Time Handling |
|------|--------|-------------|----------|----------------------|------------------------|
| 1 — Macro | FRED BAMLH0A0HYM2 (ICE BofA HY OAS) | Monthly credit spread in basis points | Regime gate: above a spread threshold, the strategy reduces position sizing or switches to a defensive posture | Published ~5 business days after month-end; not materially revised | Strategy gates on the publication date, not the reference month-end date. Backtest uses the FRED release date column, not the observation date. |
| 3 — Fundamental | SEC EDGAR XBRL balance sheet | Total assets, total liabilities, net income, operating cash flow | Quality gate: Piotroski F-Score computation (9-factor checklist) | 10-Q filed within 40 days of quarter-end; 10-K within 60–90 days. Historical GAAP figures may be restated. | Backtest queries by `filed_date <= decision_date`. Acknowledged limitation: provider does not guarantee absence of restated values for all historical periods. |

## A note on sources you cannot fully verify

For some data sources — particularly hand-curated overrides, proprietary sentiment feeds, or manually applied event dates — you cannot produce a machine-verifiable point-in-time audit trail. In those cases, the correct approach is not to omit them from the data stack table, but to document them clearly and classify their contribution to the result as non-verifiable. A reader can then apply their own judgment about how much weight to place on those elements of the backtest.
