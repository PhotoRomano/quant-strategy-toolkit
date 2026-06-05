# Sentiment Sources — Patterns and Pitfalls

Reference for the `sentiment-overlay` skill. Read this when you need source-specific
wiring details, score normalization patterns, or aggregation strategies beyond what the
main SKILL.md covers.

---

## Source comparison

| Source | History depth | Article timestamps | Symbol linking | Rate limits |
|--------|--------------|-------------------|---------------|-------------|
| Alpaca Markets News API | ~5 years | UTC, article-level | Direct (`symbols` field) | Varies by plan |
| Polygon.io News | ~3 years | UTC, article-level | Direct | Varies by plan |
| NewsAPI | ~1 month (free tier) | UTC, article-level | Keyword/query only | 100 req/day free |
| yfinance `.news` | Recent only | Unix timestamp | Direct (per ticker) | Informal, no SLA |
| SEC EDGAR 8-K filings | Full history | Filing date | EDGAR ticker/CIK | No rate limit |

For backtesting beyond 1 year, Alpaca or Polygon are the practical choices for
symbol-linked article history. SEC 8-K filings are a good complement for material event
signals (earnings preannouncements, material adverse changes) because filing dates are
authoritative and auditable.

---

## Alpaca Markets News API

Endpoint: `GET https://data.alpaca.markets/v1beta1/news`

Key parameters:
- `symbols` — comma-separated ticker list
- `start`, `end` — ISO-8601 UTC timestamps
- `limit` — max articles per page (default 50, max 50; paginate with `next_page_token`)
- `sort` — `asc` or `desc` by publish date

Pagination pattern:
```python
articles = []
params = {"symbols": ",".join(symbols), "start": start_utc, "end": end_utc,
          "limit": 50, "sort": "asc"}
while True:
    resp = requests.get(url, headers=headers, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    articles.extend(data.get("news", []))
    token = data.get("next_page_token")
    if not token:
        break
    params["page_token"] = token
```

Each article contains: `id`, `author`, `created_at` (publish time, UTC ISO-8601),
`updated_at`, `headline`, `summary`, `url`, `symbols` (list of tickers).

Use `created_at` as the publish timestamp, not `updated_at`. An update may reflect an
editorial correction hours or days after original publication; the original `created_at`
is what a trader would have seen first.

---

## Polygon.io News API

Endpoint: `GET https://api.polygon.io/v2/reference/news`

Key parameters:
- `ticker` — single ticker (repeat calls for each symbol, or use `ticker.gte`/`ticker.lte` range)
- `published_utc.gte`, `published_utc.lte` — UTC date range
- `order` — `asc`
- `limit` — max 1000 per request

Polygon returns `published_utc` in ISO-8601; use this as the publish timestamp. The
`tickers` array in each result links articles to symbols.

Polygon does not support multi-symbol bulk fetches in a single call (as of mid-2025). For
weekly bulk fetches across a large universe, call the endpoint without a `ticker` filter
and filter the returned `tickers` arrays in code — this is more efficient than one call
per symbol per week.

---

## yfinance `.news`

```python
news = yf.Ticker(symbol).news or []
for item in news:
    publish_ts = item.get("providerPublishTime")  # Unix timestamp
    headline   = item.get("title", "")
```

This source is not suitable for historical backtesting: it returns only recent articles
(typically the last 20–50 headlines) and has no reliable `start`/`end` filtering. Use it
for live signal scanning only.

---

## SEC EDGAR 8-K filings

EDGAR provides free, auditable material-event timestamps via:
`https://data.sec.gov/submissions/CIK{cik:010d}.json`

The `filings.recent` object contains arrays of form type, filing date, document dates, etc.
Filter for form type `"8-K"`. The `filed` date is the date the company submitted the
filing — this is the first moment a trader could have read the material. It is point-in-time
exact and does not change after submission.

8-K sentiment is binary by nature: a material adverse event (item codes 1.01–1.03, 1.05,
2.04, 4.01, 4.02, 8.01) signals negative news; a material positive event (2.02 earnings
announcement, 1.01 new material contract) signals positive. You can map EDGAR item codes
to a simple sentiment direction rather than doing word-scoring.

---

## Score aggregation strategies

### Simple mean (recommended for weekly keys)

```python
scores = [score_article(a) for a in week_articles if score_article(a) != 0.0]
weekly_score = sum(scores) / len(scores) if scores else 0.0
```

Weight each article equally. Works well when article volume is consistent across symbols.

### Volume-weighted mean

```python
weekly_score = sum(scores) / (len(week_articles) + 1)  # denominator includes zero-score
```

Dividing by total article count (not just scored articles) penalizes symbols with high
noise-to-signal ratios. Useful when your universe includes heavily covered large-caps that
generate many neutral articles.

### Recency-weighted mean

Weight articles published closer to the end of the week (Thursday/Friday) more heavily,
since those are more likely to be priced in by the following Monday's open. Implement by
computing day-of-week offsets from Monday=0 and scaling weights accordingly. This adds
complexity; only add it if simple mean underperforms on your hold-out set.

---

## Word list maintenance

The positive/negative word lists used in headline scoring drift over time — "AI" was
neutral in 2015 and strongly positive in 2023. Maintain the lists as a versioned artifact
alongside the cache file. Include the word list version in the cache file's metadata or
filename so you can detect stale scores when the list changes.

Minimum viable lists (illustrative, not exhaustive):

```python
POSITIVE_WORDS = {
    "beat", "beats", "surge", "surges", "record", "upgrade", "upgraded",
    "approval", "approved", "growth", "profit", "raised", "strong",
    "outperform", "boost", "launch", "launches", "expand", "win", "wins",
    "breakthrough", "partnership", "contract", "dividend",
}
NEGATIVE_WORDS = {
    "miss", "misses", "cut", "cuts", "fraud", "recall", "downgrade",
    "downgraded", "investigation", "loss", "losses", "decline", "declines",
    "weak", "warning", "lawsuit", "bankruptcy", "suspend", "suspended",
    "delisted", "restatement", "probe", "subpoena", "breach", "hack",
}
```

Avoid stemming unless you are consistent across the full pipeline. A simple `word in
headline` membership check after `.lower()` and `.split()` is reproducible and debuggable.

---

## Debugging a sentiment score

If a backtest shows unexpected entry blocks or suspiciously high conviction boosts, inspect
the underlying articles:

```python
def explain_sentiment(symbol: str, iso_week: str, articles: list[dict]) -> None:
    week_articles = [
        a for a in articles
        if symbol in (a.get("symbols") or [])
        and datetime.fromisoformat(
            a["created_at"].replace("Z", "+00:00")
        ).strftime("%G-W%V") == iso_week
    ]
    for a in week_articles:
        headline = a.get("headline", "")
        pos = [w for w in POSITIVE_WORDS if w in headline.lower()]
        neg = [w for w in NEGATIVE_WORDS if w in headline.lower()]
        print(f"  [{a['created_at']}] {headline}")
        print(f"    pos={pos}  neg={neg}")
```

This makes individual scoring decisions auditable, which is essential when a hard block
prevents an entry that you expected to fire.
