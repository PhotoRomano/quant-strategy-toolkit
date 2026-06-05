# survivorship-check — use this in any AI

Paste everything below the line into ChatGPT, Gemini, Copilot, or any assistant — as your
first message or a system/custom instruction. (In Claude you don't need this file — the skill
activates automatically.) Same method, same results; you just trigger it yourself.

*A StrongSkills tool — The shortcut to the cutting edge · getstrongskills.com*

---

Act as an expert and follow this method exactly.

# Survivorship Bias Check

A backtest that tests only the stocks that *survived* is not a backtest of the strategy — it is a
backtest of outcomes. Every company that went bankrupt, was delisted, was merged out of existence,
or was quietly dropped from an index is missing. The strategy never had to hold those losers because
they were never in the universe. The result is a systematic upward distortion that can easily add
10–30 percentage points to annualized backtest returns, depending on how long the history runs and
how volatile the universe is.

This skill audits a backtest universe for point-in-time correctness and produces a clear verdict.
A clean audit means the universe was honest; it does not mean the strategy will be profitable.
Backtests do not predict future returns.

## The core question

For every symbol in the backtest universe on a given decision date `D`:

> "Would this symbol have been available and eligible to trade on date D in real life, knowing
> only what was knowable then — and does the universe also include the symbols that were available
> then but are *gone* today?"

If the answer is "we only included stocks that still exist today," survivorship bias is present.

## Why it matters more than it looks

The bias is structural. Consider a universe built from today's S&P 500 list run back over a
five-year window:

- Survivors by definition had prices that existed over the full window (they are still listed).
- Companies removed during that period — for underperformance, financial distress, or bankruptcy —
  are absent. Their large negative returns never appear.
- Any momentum or quality signal will look stronger because the corpus is pre-filtered to companies
  that did not collapse.

The effect compounds: the longer the backtest window, the more names were removed from any given
index, and the larger the distortion.

## Audit workflow

Work through these steps in order. Share your findings in the report structure at the end.

### 1. Identify how the universe is built

Read the code and locate every place the tradable symbol list is constructed. Common patterns:

- Fetching today's index constituents from a live API or Wikipedia scrape and using them unchanged
  for the entire historical simulation.
- Loading a hardcoded list that was assembled at the time the code was written.
- Pulling `yfinance` or similar for any symbol that returns data, without checking whether it was
  listed on the decision date.
- Filtering by liquidity/market-cap on today's data, then running history on the survivors.

For each pattern, note the exact source, the fetch date, and whether any historical membership
data is used.

### 2. Test for point-in-time membership

The valid pattern is: for decision date `D`, the universe contains only symbols that were listed,
liquid, and index-eligible *as of* `D`. That requires one of:

- A proper point-in-time constituent database (Compustat, CRSP, Sharadar, Norgate, or a vendor
  with a `date_added` / `date_removed` table).
- A hand-built historical membership table that explicitly records when each symbol entered and
  left the universe.
- A deliberate, conservative approximation: using only very large, stable names that clearly
  existed throughout the backtest window, combined with an explicit statement about the limitation.

Today's Wikipedia S&P 500 page is a current snapshot. Using it for a historical backtest treats
the present as the past. It is one of the most common sources of survivorship bias in open-source
backtesting code.

### 3. Verify delisted and bankrupt names are included

Pull a list of names removed from the relevant index or universe during the backtest window and
check whether they appear. For example, over a five-year S&P 500 backtest, dozens of companies
exit the index each year — check that at least a representative sample appears in the historical
data and that their full return histories (including terminal declines) are included.

If a symbol simply has "no data" in yfinance after its delisting date, the issue is that most
free data sources return nothing for delisted names — but the proper fix is not to exclude them,
it is to source their historical prices up to the delisting event.

### 4. Check the liquidity filter

A common secondary bias: filtering by current-day liquidity (e.g., "average volume > 500K shares"
computed today). Stocks that are liquid today were also liquid survivors. Small, illiquid names
that eventually failed were filtered out retroactively. Liquidity gates must be applied using
historical volume data as of each decision date `D`, not today's data.

### 5. Separate structural bias from design bias

Two distinct problems, only the first of which is a code bug:

1. **Structural survivorship bias** — The universe construction code mechanically excludes
   non-survivors. Fix it by using point-in-time data.

2. **Design-time selection bias** — A human curated the list with knowledge of which companies
   fared well. Adding a stock to the universe "because it was a strong performer" or assembling
   a sector list weighted toward companies you know succeeded is hindsight, even if every data
   read is perfectly time-gated. This cannot be patched in code; it must be disclosed.

Report both, but be precise about which is which.

## A worked micro-example

**Setup:** A strategy backtests 2019–2024 using the S&P 500 list.

**Biased version:**
```python
# Fetches TODAY's S&P 500 from Wikipedia — a live snapshot
import pandas as pd
sp500 = pd.read_html(
    "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
)[0]["Symbol"].tolist()

# Then runs the full historical simulation using this list
for date in trading_dates_2019_2024:
    candidates = [s for s in sp500 if passes_score(s, date)]
    ...
```
Every company that was in the S&P 500 at some point during 2019–2024 but exited due to poor
performance is invisible to this simulation. The strategy only holds companies that survived
to be on today's list.

**Point-in-time version:**
```python
# Load a membership table with entry/exit dates
# (source: Compustat, Sharadar, or a curated historical CSV)
membership = pd.read_csv("sp500_historical_members.csv")
# columns: symbol, date_added, date_removed (NaT if still current)

def get_universe_as_of(date):
    mask = (
        (membership["date_added"] <= date) &
        (membership["date_removed"].isna() | (membership["date_removed"] > date))
    )
    return membership.loc[mask, "symbol"].tolist()

for date in trading_dates_2019_2024:
    candidates = [s for s in get_universe_as_of(date) if passes_score(s, date)]
    ...
```
The fix requires a historical membership source, not just a code change. That is the key insight:
survivorship bias cannot be corrected without acquiring historically accurate data.

## Report structure

Produce the audit as this exact structure:

```
# Survivorship Check: <strategy or backtest name>

## Verdict
<One line: CLEAN / SURVIVORSHIP BIAS PRESENT / CANNOT VERIFY — plus a one-sentence why.>

## Universe Construction
| Source | Method | Point-in-time? | Delist coverage | Finding |
|--------|--------|----------------|-----------------|---------|
<one row per universe source>

## Confirmed Bias Sources
<For each: what the code does, why it excludes non-survivors, severity, and the fix.>

## Design-Bias Disclosures (not code bugs, but must be stated)
<Human curation choices made with hindsight: which names were added or excluded and why.>

## What I Could Not Verify
<Universe sources or filters where point-in-time status couldn't be confirmed.>

## Recommended Fix
<The minimum data source / code change needed to achieve a sound universe.
 If the fix requires a paid data source, name the free alternatives too.>

## Bottom line
<Whether the reported backtest returns are inflated and by how much (qualitative estimate only —
 no corrected return figures).>
```

Severity guide: **High** = the entire universe is built from current survivors (every result is
suspect). **Medium** = a secondary filter (liquidity, market-cap) is applied using current data.
**Low** = a small, known-stable subset of names that clearly existed throughout the window.

## Free and paid data sources for point-in-time universes

See `references/pit-universe-sources.md` for a catalog of options, their coverage, and how to
integrate them. The short version:

- **Free / open:** Norgate Data trial exports, academic CRSP samples, hand-built CSVs from SEC
  historical filings, `openbb` historical constituents module.
- **Low-cost paid:** Sharadar Core US Equities (Nasdaq Data Link), Norgate Data subscription,
  Portfolio123 historical universe API.
- **Full institutional:** CRSP, Compustat (via Wharton WRDS) — the gold standard but expensive.

When no point-in-time source is available, the correct approach is to narrow the universe to
large, demonstrably stable names (e.g., consistent S&P 100 members over the full window),
document the limitation explicitly, and treat the backtest as an upper-bound estimate that likely
overstates live performance.

## Pairing with other skills

- **lookahead-audit** — once the universe is sound, audit every *data read* inside the loop for
  temporal correctness. Survivorship and lookahead bias are independent; a strategy can have one
  without the other, or both.
- **walk-forward-validation** — after fixing the universe, confirm that parameter choices are
  validated out-of-sample before any reported numbers are shared.
- **point-in-time-fundamentals** — if fundamental data (earnings, ratios) is used for scoring,
  verify that it too is keyed by publication date, not period-end date.


<!-- strongskills-brand -->

---

*Made with a StrongSkills tool — The shortcut to the cutting edge · getstrongskills.com*
