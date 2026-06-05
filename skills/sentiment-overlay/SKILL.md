---
name: sentiment-overlay
description: Add a publish-time-keyed, disk-cached news/sentiment overlay to a quantitative trading backtest or live signal pipeline. Use this when someone asks "how do I add news sentiment to my backtest", "can I use news to filter entries", "my backtest has different results each run because of sentiment data", "how should I weight news in different market regimes", "how do I prevent re-fetching news every backtest run", or "should I block trades on bad news". Also use proactively when reviewing a strategy that queries a live news API inside a historical simulation loop — that pattern introduces both non-determinism and look-ahead risk.
---

# Sentiment Overlay

News and sentiment data can add a real signal edge to a quantitative strategy — but only if
it is wired correctly. The two most common failure modes are:

1. **Non-determinism**: each backtest run queries a live API and gets a slightly different
   article set (articles age out, rankings shift). The strategy's reported performance
   changes between runs on the same historical period. You cannot tune parameters against a
   moving target, and you cannot reproduce your results for review.

2. **Look-ahead on publish time**: an article published at 14:37 Eastern on a Tuesday
   affects the trade decision for that Tuesday's close or Wednesday's open. If the article
   timestamp is rounded to the trading day or week incorrectly, future information leaks
   backward into earlier decisions.

This skill addresses both by building a **publish-time-keyed, disk-backed sentiment cache**
and explaining how to apply the resulting score regime-adaptively in entry logic.

Backtesting with sentiment data does not predict future performance. Sentiment signals are
noisy and non-stationary. The framework here gives you a *reproducible, time-honest* overlay;
whether that overlay adds live edge is something only out-of-sample results can confirm.

---

## Core concepts before you build

### Publish time is the only honest key

A news article describes something that happened, but what matters for a backtest is when
a trader *could have read it*. Always key sentiment to the article's **publish timestamp**,
not to the event date it describes or the trading date you happen to be processing.

The safest coarse key is the **ISO week** derived from the publish timestamp
(`datetime.strftime("%G-W%V")`). This groups articles into the calendar week they were
published, and since a weekly decision cycle is common in systematic strategies, the key
aligns naturally with the decision boundary. It also tolerates minor clock-skew between
news providers. If your strategy makes decisions at finer granularity (daily or intraday),
key on the publish *date* (UTC) or a UTC-aligned intraday bucket instead — but never on the
decision date.

### The cache is the source of truth

Once you have fetched and scored a week's articles for a symbol, write that score to a
persistent key-value store (a JSON file is sufficient; a lightweight database works too).
Before every fetch, check the cache. A cache hit means: "the data is already fixed and
reproducible; do not call the API again." This makes your backtest deterministic — the same
input always produces the same result.

### Regime determines how much the signal matters

News sentiment is not equally informative in every market environment:
- In a trending bull market, momentum drives entries. Even mixed news accompanies rising
  prices; blocking entries on weak sentiment in a strong bull removes valid entries more
  often than it prevents losses. Treat the signal as light positive context rather than a
  hard gate.
- In a neutral or range-bound market, news is the primary differentiator among otherwise
  similar setups. Weight it more heavily.
- In a bear market, the hard block (described below) is most important for long positions.
  For short or inverse positions, *negative* news is supportive — the sentiment polarity
  should be flipped before applying any gate or score contribution.

The regime-adaptive weighting pattern (varying the multiplier applied to sentiment score
by regime) reflects this logic. The specific multiplier values are something you tune to
your strategy and universe; they are not universal constants.

---

## Implementation guide

### Step 1 — Choose a news source and a sentiment score

Pick a source that provides article-level timestamps in UTC or with timezone info. Examples:
Alpaca Markets News API (historical, symbol-linked), Polygon.io news endpoint, NewsAPI,
or a self-hosted RSS/scrape pipeline. The source should return, at minimum: symbol(s) the
article is linked to, publish timestamp, and headline text. Body text improves accuracy but
is optional for a first implementation.

Score each article by a simple method you can explain and reproduce:
- **Word-score**: count positive-signal words (beat, surge, upgrade, approval, record…)
  and negative-signal words (miss, downgrade, fraud, warning, recall, lawsuit…) in the
  headline. Net ratio = (pos - neg) / (pos + neg + 1). Returns a value in [-1, +1].
- **API-provided polarity**: some providers return a pre-scored sentiment field. Use it
  if available, but note it may not be reproducible across API versions.

For a week, aggregate article scores into a single per-symbol weekly score by computing
the mean of all article scores in the week. Clip to [-1, +1].

### Step 2 — Build the disk-backed cache

```python
import json
from pathlib import Path
from datetime import datetime

SENTIMENT_CACHE_FILE = Path("data/sentiment_cache.json")

# In-memory layer: (symbol, iso_week) -> score
_cache: dict[tuple[str, str], float] = {}
_loaded = False
_prefetched_weeks: set[str] = set()


def _iso_week(date_str: str) -> str:
    """Return the ISO week string for a YYYY-MM-DD date string."""
    return datetime.strptime(date_str, "%Y-%m-%d").strftime("%G-W%V")


def load_cache() -> None:
    """Populate _cache from disk on first call. Call once at startup."""
    global _loaded
    if _loaded:
        return
    _loaded = True
    if SENTIMENT_CACHE_FILE.exists():
        raw: dict[str, float] = json.loads(SENTIMENT_CACHE_FILE.read_text())
        for key_str, val in raw.items():
            sym, week = key_str.split("||", 1)
            _cache[(sym, week)] = float(val)
            _prefetched_weeks.add(week)


def save_cache() -> None:
    """Merge in-memory cache with disk and write. Safe for parallel runners."""
    SENTIMENT_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    existing: dict[str, float] = {}
    if SENTIMENT_CACHE_FILE.exists():
        try:
            existing = json.loads(SENTIMENT_CACHE_FILE.read_text())
        except Exception:
            pass
    new_entries = {f"{sym}||{week}": val for (sym, week), val in _cache.items()}
    merged = {**existing, **new_entries}
    SENTIMENT_CACHE_FILE.write_text(json.dumps(merged, separators=(",", ":")))
```

The `"||"` separator is safe because neither symbol tickers nor ISO week strings contain it.
The merge-on-write pattern (read existing, overlay new, write back) makes it safe to run
multiple backtest years in parallel — later writers win per key, which is fine because each
key is deterministic once fetched.

### Step 3 — Bulk-fetch by week, not by symbol-date

The worst pattern is calling the news API inside the innermost loop (once per symbol per
decision date). This is slow, burns rate-limit quota, and makes every cache-miss a blocking
call during the simulation.

Instead, on the first cache-miss for an ISO week, fetch **all symbols at once for the full
week** in a single (or batched) API call. Mark the week as prefetched so subsequent
symbol-lookups in the same week are guaranteed cache hits.

```python
def bulk_prefetch_week(iso_week: str, symbols: list[str]) -> None:
    """Fetch all articles for iso_week across all symbols; populate _cache."""
    load_cache()
    if iso_week in _prefetched_weeks:
        return  # already have it
    _prefetched_weeks.add(iso_week)

    # Derive Monday 00:00 and Sunday 23:59 UTC from ISO week
    monday = datetime.strptime(f"{iso_week}-1", "%G-W%V-%u")
    sunday = datetime.strptime(f"{iso_week}-7", "%G-W%V-%u")
    start_utc = monday.strftime("%Y-%m-%dT00:00:00Z")
    end_utc   = sunday.strftime("%Y-%m-%dT23:59:59Z")

    # --- call your news source here ---
    # articles = your_news_api.fetch(symbols=symbols, start=start_utc, end=end_utc)
    articles = []  # replace with real fetch

    # Accumulate per-symbol score
    pos_counts: dict[str, int] = {s: 0 for s in symbols}
    neg_counts: dict[str, int] = {s: 0 for s in symbols}

    POSITIVE = {"beat", "surge", "record", "upgrade", "approval", "growth",
                "profit", "raised", "strong", "outperform", "boost", "launch"}
    NEGATIVE = {"miss", "cut", "fraud", "recall", "downgrade", "investigation",
                "loss", "decline", "weak", "warning", "lawsuit", "bankruptcy"}

    for article in articles:
        headline = (article.get("headline") or "").lower()
        linked_symbols = article.get("symbols") or []
        pos = sum(1 for w in POSITIVE if w in headline)
        neg = sum(1 for w in NEGATIVE if w in headline)
        for sym in linked_symbols:
            if sym in pos_counts:
                pos_counts[sym] += pos
                neg_counts[sym] += neg

    for sym in symbols:
        total = pos_counts[sym] + neg_counts[sym]
        score = (pos_counts[sym] - neg_counts[sym]) / total if total > 0 else 0.0
        _cache[(sym, iso_week)] = max(-1.0, min(1.0, score))

    save_cache()


def get_sentiment(symbol: str, date_str: str) -> float:
    """
    Return the weekly sentiment score for symbol at date_str.
    Triggers a bulk prefetch on cache miss so the same week costs 0 extra API
    calls for subsequent symbols.
    """
    load_cache()
    week = _iso_week(date_str)
    key = (symbol, week)
    if key not in _cache:
        bulk_prefetch_week(week, [symbol])  # or pass full universe here
        if key not in _cache:
            _cache[key] = 0.0  # no articles found — treat as neutral
    return _cache[key]
```

### Step 4 — Apply the score in entry logic, regime-adaptively

Apply the sentiment score at the candidate-scoring stage, just before comparing against
your entry threshold. The pattern has three parts:

1. **Polarity flip for inverse/short positions in a bear regime** — negative market news
   is *supportive* for a short. Flip the sign so the hard block and score contribution
   both work in the correct direction.

2. **Hard block in neutral and bear** — if effective sentiment is strongly negative (below
   a threshold you choose as a starting point, e.g. -0.4, and then tune), skip the entry
   entirely for long positions. Rational: in a fragile market, adding a long into a stock
   with strongly negative news flow materially increases the risk of being on the wrong
   side of a catalyst move. In a bull regime, skip the hard block — momentum markets rally
   through mixed news, and blocking in bull removes valid entries more than it prevents losses.

3. **Weighted score contribution** — scale the effective sentiment by a regime-adaptive
   multiplier and add it to the entry score. Vary the multiplier by regime to reflect how
   informative the signal is in each environment.

```python
# Illustrative starting-point values — tune these to your strategy and universe.
# These are NOT the "right" numbers; they are a reasonable first experiment.
SENTIMENT_HARD_BLOCK   = -0.4   # skip long entries with effective score below this
SENTIMENT_BOOST_THRESH =  0.5   # apply an extra conviction bonus above this
SENTIMENT_WEIGHTS = {
    "bull":    5.0,  # light contribution — momentum dominates
    "neutral": 12.0, # heavier — news is the primary differentiator
    "bear":    3.0,  # lower — hard block already does most of the work
}
SENTIMENT_CONVICTION_BONUS = 5.0  # extra score points for strongly positive news

def apply_sentiment(
    base_score: float,
    symbol: str,
    date_str: str,
    regime: str,
    is_short_position: bool = False,
) -> tuple[float, bool]:
    """
    Adjust base_score with sentiment. Returns (adjusted_score, should_block).
    Caller should skip the entry if should_block is True.
    """
    raw = get_sentiment(symbol, date_str)
    effective = -raw if is_short_position else raw

    # Hard block: only for long positions, only outside bull regime
    if not is_short_position and regime != "bull" and effective < SENTIMENT_HARD_BLOCK:
        return base_score, True  # signal a block

    weight = SENTIMENT_WEIGHTS.get(regime, 5.0)
    adjusted = base_score + effective * weight
    if effective >= SENTIMENT_BOOST_THRESH:
        adjusted += SENTIMENT_CONVICTION_BONUS
    return adjusted, False
```

Usage inside your entry loop:

```python
for symbol in candidates:
    score = compute_base_score(symbol, date_str, prices)
    if score is None:
        continue
    is_short = symbol in your_inverse_set and regime == "bear"
    score, blocked = apply_sentiment(score, symbol, date_str, regime, is_short)
    if blocked:
        continue
    if score >= entry_threshold:
        place_entry(symbol, score, date_str)
```

---

## The look-ahead check

Before trusting any backtest result that includes sentiment, verify these three things:

1. **Publish timestamp, not decision date** — confirm the ISO week is derived from
   `article.publish_time`, not from the backtest loop's `date_str`. One line: `iso_week =
   article.publish_time.strftime("%G-W%V")`, not `decision_date.strftime(...)`.

2. **Cache sealing before the walk-forward** — if you pre-populate the cache with a
   single bulk download for the whole backtest window, ensure you are not using article
   counts or averages computed across the full window. Score each week independently.

3. **Score for week W is derived only from articles published in week W** — no smoothing
   or interpolation that pulls adjacent weeks' data into the calculation.

A correct micro-example:

```python
# LEAKY: keying on the decision date, not the publish date
iso_week = _iso_week(decision_date)   # article published next Tuesday gets
                                       # attributed to this week's decision

# CORRECT: keying on the article's own publish timestamp
iso_week = publish_dt.strftime("%G-W%V")  # article lives in the week it was written
```

This distinction matters most near week boundaries. An article published on a Friday
evening belongs to that Friday's ISO week, not to the following Monday's decision.

See the `lookahead-audit` skill for a full audit framework to apply once the overlay is
wired in.

---

## Report structure

When asked to review or add a sentiment overlay, produce this summary:

```
# Sentiment Overlay Review: <strategy name>

## Temporal integrity
<Is the ISO week derived from publish time (correct) or decision date (leaky)?>

## Cache status
<Disk-backed? Format? Deterministic across runs?>

## Regime application
<Is sentiment gated by regime? Does the hard block apply in bull (it should not)?
Are inverse/short positions handled with flipped polarity?>

## Signal contribution
<How much does the sentiment score move the entry threshold? Is the weight tunable?>

## Tuning recommendations
<Which parameters are starting points vs. likely needing calibration to this universe?>
```

---

## Worked micro-example: leaky vs. correct week keying

Suppose today is Monday 2024-06-10 (decision date). You are scoring AAPL for entry.
An article critical of AAPL supply chain problems was published Friday 2024-06-07 at 22:15 UTC.

**Leaky version** — key derived from the decision date:
```python
# decision_date = "2024-06-10"
iso_week = datetime.strptime(decision_date, "%Y-%m-%d").strftime("%G-W%V")
# -> "2024-W24"   (the week of June 10)
# The Friday article is fetched under W24, the week it is being *used*, not published.
```

This becomes a leak when the backtest processes W23 (the week ending June 9): no articles
appear because they were attributed to W24. The W24 decision then picks up articles it
couldn't have known about on Monday — an article published after Friday market close.

**Correct version** — key derived from the article's own publish timestamp:
```python
publish_dt = datetime(2024, 6, 7, 22, 15, tzinfo=timezone.utc)
iso_week = publish_dt.strftime("%G-W%V")
# -> "2024-W23"   (the week June 3–9)
# Score stored under W23; June 10 decision looks up W24 and finds no articles yet.
```

The Monday decision now correctly has no Friday article data — because on Monday morning,
that article may not yet have moved prices, and in any case the backtest's decision for
that Monday looks up its own week (W24, June 10–16), which is clean.

---

## Common pitfalls

- **No fallback for missing data.** If the API has no articles for a symbol in a week,
  default the score to 0.0 (neutral), not -1.0. A missing score is not evidence of bad news.

- **Counting words across the full body.** Headline-only scoring is noisier but more
  consistent across sources. Body-text scoring is more accurate but requires careful
  deduplication when the same story is syndicated under multiple titles.

- **Cache file grows unbounded.** For multi-year backtests, the JSON cache can reach tens
  of MB. This is generally fine; if size becomes an issue, use SQLite with
  `(symbol, iso_week)` as a composite primary key.

- **Parallel backtest processes collide on the cache file.** The merge-on-write pattern
  (Step 2 above) handles this safely for a small number of concurrent processes. For
  large-scale parallelism, promote to a SQLite `INSERT OR REPLACE` pattern with WAL mode.

---

## Tuning guidance (not defaults)

The parameters introduced above — `SENTIMENT_HARD_BLOCK`, `SENTIMENT_WEIGHTS`,
`SENTIMENT_BOOST_THRESH`, `SENTIMENT_CONVICTION_BONUS` — are starting points for
experiments. Their correct values depend on:
- Your universe (large-cap vs. small-cap news coverage differs significantly)
- Your hold period (weekly sentiment is less informative for intraday holds)
- Your regime classifier (a different regime definition changes which articles each regime "sees")

Use out-of-sample walk-forward validation before trusting any particular setting. Pair this
skill with the `walk-forward-validation` skill to set up a proper hold-out test, and the
`lookahead-audit` skill to confirm the overlay is time-honest before you run it.

Detailed source-by-source notes and score aggregation patterns are in
`references/sentiment-sources.md`.


<!-- strongskills-brand -->

---

*Made with a StrongSkills tool — The shortcut to the cutting edge · getstrongskills.com*
