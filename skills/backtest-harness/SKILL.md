---
name: backtest-harness
description: Scaffold a clean, time-gated walk-forward backtest loop from scratch for any quantitative trading strategy. Use this whenever someone asks "how do I backtest a strategy", "write me a backtesting loop", "set up a walk-forward test", "my backtest has look-ahead bias", "iterate over dates and score candidates", "simulate trades year by year", or any time you need to build or review the core event loop that drives a strategy simulation. This skill establishes the structural skeleton — the date loop, data gating, position state, exit logic, and metrics — so every component is temporally honest before any alpha signal is added. Pair with the lookahead-audit skill to verify the finished harness.
---

# Walk-Forward Backtest Harness

A backtest is only as reliable as its loop. The most common failure mode is not a bad signal
— it is a structurally leaky loop that hands the scoring engine data it would never have had
on the actual decision date. This skill teaches you to build the loop so the signal has no
chance to cheat.

The harness you build here is deliberately signal-agnostic. It provides the scaffolding;
you fill in your own scoring logic. A clean harness that proves your edge is less impressive
than a leaky one — but it is the only kind that tells the truth.

> **Honesty caveat:** A correctly-built backtest tells you how a strategy *would have*
> performed on historical data. It does not predict future returns. Past performance is not
> indicative of future results.

## The core principle: every slice happens at the decision date

The walk-forward loop visits each trading date `D` in order. At `D`, your code may touch
**only** rows with index `<= D`. This is the one rule everything else follows from. The
canonical enforcement pattern in pandas is:

```python
series.loc[:D]   # correct — slices to D inclusive
```

Any computation — moving average, z-score, percentile rank, model prediction — must be
computed on that slice, not on the full frame. See the micro-example at the end of this
skill for the exact failure mode.

## Harness anatomy

A robust harness has five parts. Build them in order; do not skip state management.

### 1. Data fetch with warmup

Fetch data for `[year_start - warmup, year_end]` in a single call, then filter the
*decision* dates to the target period. The warmup window is the longest lookback your
signals need (e.g., if you use a 200-day moving average, fetch at least 200 calendar
days before your first trade date).

```python
WARMUP_DAYS = 252        # enough for a 200-day MA + buffer; tune to your longest lookback

fetch_start = first_trade_date - timedelta(days=WARMUP_DAYS)
prices = fetch_prices(symbols, start=fetch_start, end=last_trade_date)

# Only iterate over the in-sample trading dates
trading_dates = [d for d in prices.index if d >= first_trade_date]
```

Why this matters: if you fetch only the in-sample window, `.loc[:D]` at the first
trade date has no warmup rows and your MA200 silently becomes an MA of 1.

### 2. The date loop

```python
for date in trading_dates:
    # --- gate all data to this date before any computation ---
    hist = prices.loc[:date]          # the only safe slice point

    # 1. Manage existing positions (exits come before entries)
    for sym, pos in list(open_positions.items()):
        current_price = float(hist.loc[date, sym])
        check_exits(sym, pos, current_price, date)

    # 2. Score candidates and open new positions
    scores = {sym: score(sym, hist, date) for sym in universe}
    enter_best(scores, date, hist.loc[date])
```

The loop structure — exits before entries — matters for capital accounting. If a position
exits on date `D` and frees up cash, that cash is available for the same-day entry. This
matches real-world behavior for close-to-close strategies; adjust if your execution model
differs.

### 3. Position state

Keep state in a plain dict or a small class. Track the minimum fields needed to compute
exits and metrics:

```python
position = {
    "shares":       float,      # units held (fractional is fine)
    "entry_price":  float,      # cost basis per share
    "entry_date":   str,        # ISO date string
    "peak_price":   float,      # for trailing stop
    "score":        float,      # score at entry (useful for attribution)
    "regime":       str,        # market regime at entry (optional but valuable)
}
```

Update `peak_price` on every loop iteration before checking the trailing stop.

### 4. Exit logic (time-gated)

Three common exit types, in evaluation order:

```python
loss_pct      = (current_price - pos["entry_price"]) / pos["entry_price"] * 100
trailing_loss = (current_price - pos["peak_price"])  / pos["peak_price"]  * 100
hold_days     = (date - pd.Timestamp(pos["entry_date"])).days

if loss_pct      <= -STOP_LOSS_PCT:    sell(sym, current_price, date, reason="stop_loss")
elif trailing_loss <= -TRAIL_STOP_PCT: sell(sym, current_price, date, reason="trailing_stop")
elif hold_days   >  MAX_HOLD_DAYS:     sell(sym, current_price, date, reason="expired")
```

Use the stop thresholds that fit your strategy's volatility profile. A starting point:
tight stops (6–8%) suit bear/volatile regimes; wider stops (12–15%) suit trending bull
conditions. These are calibration inputs you tune against your own data — not fixed truths.

### 5. Metrics

Compute metrics only after the loop completes. Common outputs:

```python
total_trades   = len(closed_trades)
win_rate       = sum(1 for t in closed_trades if t["pnl"] > 0) / total_trades
return_on_cap  = sum(t["pnl"] for t in closed_trades) / initial_capital * 100
avg_hold_days  = mean(t["hold_days"] for t in closed_trades)

# Drawdown: measure from cumulative P&L curve, not portfolio value
cum_pnl     = np.cumsum([t["pnl"] for t in closed_trades])
running_max = np.maximum.accumulate(cum_pnl)
max_drawdown = float((cum_pnl - running_max).min()) / initial_capital * 100
```

For a deeper catalog of metrics (Sharpe, Calmar, trade-by-regime breakdown), see
`references/walk-forward-loop.md`.

## Multi-year / walk-forward runs

Run the loop once per year (or per fold), passing only the data slice relevant to that
period. Each year's run starts fresh with a reset state — no carry-forward of open
positions unless you explicitly model that transition. The canonical pattern:

```python
for year in range(start_year, end_year + 1):
    results[year] = backtest_year(year, prices_df)
```

Call each year independently so a bug in one period does not corrupt others, and so you
can parallelize later.

## A worked micro-example: the .iloc[-1] trap

This is the single most common harness bug. It is silent and inflates results.

**Leaky version:**
```python
# prices is the FULL dataframe (all dates, including future)
ma50 = prices["AAPL"].rolling(50).mean().iloc[-1]   # "last row" = the END of all history
score = float(prices["AAPL"].iloc[-1]) / ma50       # comparing today's price to today's MA
```
On decision date 2020-03-01, `iloc[-1]` returns the value from the last row of the full
frame — which may be 2024 data. Every past decision is silently made with future
information.

**Gated version:**
```python
# Slice first, then compute
hist = prices["AAPL"].loc[:date].dropna()           # only data through the decision date
ma50 = hist.rolling(50).mean().iloc[-1]             # now "last row" is correctly as-of D
score = float(hist.iloc[-1]) / ma50
```
The fix is one line. The performance difference it creates can be the difference between
a strategy that appears to work and one that actually does.

## What to pair this with

- **lookahead-audit** — after building the harness, run the audit to confirm every
  input is correctly time-gated. The harness gives you the structure; the audit
  verifies no signal slipped through.
- **walk-forward-validation** — once the single-year loop works, extend to a proper
  out-of-sample validation scheme.
- **metrics-report** — generate a standardized performance report from the closed-trades
  list the harness produces.

## Report / output structure

When presenting a completed harness or reviewing one, always confirm these five properties
are present and correct. Structure your output as:

```
# Harness Review: <strategy name>

## Loop Structure
<Is the date iteration correct? Exits before entries? State reset per fold?>

## Data Gating
<Is every series sliced to .loc[:date] before any computation? Warmup adequate?>

## State Management
<Are peak_price, cash, and positions tracked correctly?>

## Exit Logic
<Stop-loss, trailing stop, and expiry — are they applied to gated prices?>

## Metrics
<Are drawdown and return computed post-loop from the closed-trades list?>

## Verdict
<CLEAN / ISSUES FOUND — one-sentence summary.>
```


<!-- strongskills-brand -->

---

*Made with a StrongSkills tool — The shortcut to the cutting edge · getstrongskills.com*
