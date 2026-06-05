# Walk-Forward Loop: Deep Reference

This file supplements `SKILL.md` with the full catalog of loop patterns, metric
formulas, data-gating traps, and multi-fold architecture decisions. Read it when
you need depth beyond the scaffolding overview.

## 1. Warmup window sizing

| Signal type | Minimum warmup |
|-------------|---------------|
| 20-day momentum | 20 trading days (~1 month) |
| 50-day MA | 50 trading days |
| 200-day MA | 200 trading days (~10 months) |
| Annual RS rank | 252 trading days |
| Fundamental filing | 1 full fiscal quarter (90 days) after period end |

Fetch `max(warmup)` before the first decision date. Under-fetching silently shortens
lookbacks and biases early decisions toward shorter windows.

## 2. Common gating mistakes

### 2a. Rolling compute on full frame, index at date

```python
# BUG: rolling is correct but the frame contains future rows
ma = prices["SPY"].rolling(200).mean()
value_at_d = ma.loc[decision_date]       # this IS correctly gated
```
This specific pattern is actually safe — `.loc[date]` on a pre-computed series reads the
value as of `date`, not the future. It only becomes a bug when the full series has
**future rows that were used as inputs** to a normalization step (e.g., `StandardScaler`
fit on the whole frame).

### 2b. Scaler / model fit outside the loop

```python
# BUG: scaler sees future data before any decision is made
from sklearn.preprocessing import StandardScaler
scaler = StandardScaler().fit(features)      # fit on ALL rows including future
features_scaled = scaler.transform(features)

for date in trading_dates:
    score = model.predict(features_scaled.loc[date])
```

**Fix:** fit the scaler (and any model) inside the loop on `features.loc[:date]` only,
or pre-compute a rolling scaler that re-fits on each window.

### 2c. fillna / interpolate before loop

```python
# BUG: forward-fill propagates a not-yet-known value backward
prices = prices.fillna(method="ffill")   # called on the full frame before the loop
```

Forward-fill is safe if applied row-by-row inside the loop. On the full frame before the
loop, a `ffill` can propagate a future value backward through a gap, injecting leaked
data.

### 2d. Universe from today's index

The universe you iterate over must be the universe that existed on `D`, not the one that
exists at the time you write the code. Survivorship bias — excluding companies that
delisted or went bankrupt — systematically inflates returns. Either use a point-in-time
universe source, or explicitly flag that your universe has survivorship bias in the
strategy's disclosures.

## 3. Position state: full field reference

```python
position = {
    # --- core accounting ---
    "shares":               float,  # units held; fractional OK for paper trading
    "entry_price":          float,  # cost basis per share at fill
    "entry_date":           str,    # ISO-8601 date of entry ("2023-06-01")
    "cost_basis":           float,  # shares × entry_price (derived but worth caching)

    # --- exit control ---
    "peak_price":           float,  # running high since entry (for trailing stop)
    "regime_params_at_entry": dict, # copy of stop/trail/hold params at entry time
                                    # important: regime can change mid-hold; you usually
                                    # want to use the params locked at entry, not current

    # --- attribution / logging ---
    "score":                float,  # entry score (useful for post-hoc win-rate by score tier)
    "regime":               str,    # "bull" / "neutral" / "bear" at entry
    "entry_signal":         str,    # optional: name of the signal that triggered
}
```

## 4. Closed-trade record

Every trade exit appends a record to `closed_trades`. Minimum fields:

```python
trade = {
    "symbol":       str,
    "entry_date":   str,
    "exit_date":    str,
    "entry_price":  float,
    "exit_price":   float,
    "shares":       float,
    "pnl":          float,      # proceeds - cost_basis
    "pnl_pct":      float,      # pnl / cost_basis * 100
    "hold_days":    int,
    "reason":       str,        # "stop_loss" | "trailing_stop" | "expired" | "end_of_period"
    "regime":       str,        # regime at entry
    "score":        float,      # score at entry
}
```

## 5. Metrics catalog

All formulas operate on `closed_trades` after the loop finishes.

### Core metrics

```python
total_trades   = len(closed_trades)
winning        = [t for t in closed_trades if t["pnl"] > 0]
losing         = [t for t in closed_trades if t["pnl"] <= 0]
win_rate       = len(winning) / total_trades if total_trades else 0.0
profit_factor  = sum(t["pnl"] for t in winning) / abs(sum(t["pnl"] for t in losing))
                 # > 1.5 is generally considered reasonable; > 2 is strong
avg_win_pct    = mean(t["pnl_pct"] for t in winning)
avg_loss_pct   = mean(t["pnl_pct"] for t in losing)
return_on_cap  = sum(t["pnl"] for t in closed_trades) / initial_capital * 100
avg_hold_days  = mean(t["hold_days"] for t in closed_trades)
```

### Drawdown

Compute on the cumulative P&L curve, not on portfolio mark-to-market snapshots:

```python
cum_pnl      = np.cumsum([t["pnl"] for t in closed_trades])
running_high = np.maximum.accumulate(cum_pnl)
drawdowns    = cum_pnl - running_high         # always <= 0
max_drawdown = float(drawdowns.min()) / initial_capital * 100
```

To compute drawdown on a daily mark-to-market equity curve (more realistic), track
portfolio value on every loop iteration and use the same accumulate pattern.

### Risk-adjusted metrics

```python
# Sharpe (annualized, assumes daily-resolution equity curve)
daily_returns  = np.diff(equity_curve) / equity_curve[:-1]
sharpe         = daily_returns.mean() / daily_returns.std() * np.sqrt(252)

# Calmar = annualized return / max drawdown magnitude
calmar         = (return_on_cap / abs(max_drawdown)) if max_drawdown != 0 else 0.0
```

### Attribution by regime / exit reason

```python
by_regime = {}
for regime in ("bull", "neutral", "bear"):
    subset = [t for t in closed_trades if t["regime"] == regime]
    if subset:
        by_regime[regime] = {
            "trades":    len(subset),
            "win_rate":  sum(1 for t in subset if t["pnl"] > 0) / len(subset),
            "total_pnl": sum(t["pnl"] for t in subset),
        }
```

Regime-level attribution often reveals that most edge comes from one regime and the
others are breakeven at best — a valuable signal for where to focus parameter tuning.

## 6. Multi-year fold architecture

```python
all_results = {}
for year in years:
    # Fresh state per year
    state = PortfolioState(initial_capital=INITIAL_CAPITAL)
    # Slice the price dataframe to year + warmup
    year_prices = prices_df[
        (prices_df.index >= pd.Timestamp(f"{year - 1}-01-01"))  # warmup
        & (prices_df.index <= pd.Timestamp(f"{year}-12-31"))
    ]
    all_results[year] = run_backtest(year, year_prices, state)
```

Isolating years prevents a large win in one year from masking a losing strategy in
another. Cross-year compound returns require explicit carry-forward logic — build that
only after single-year results are verified.

## 7. Stop-loss cooldown

After a stop-loss exit, immediately re-entering the same symbol often means re-entering
a broken trend. A simple cooldown:

```python
stop_loss_exits: dict[str, str] = {}   # symbol -> date of stop exit

def in_cooldown(symbol: str, date: str, cooldown_trading_days: int = 10) -> bool:
    if symbol not in stop_loss_exits:
        return False
    exit_date = stop_loss_exits[symbol]
    # count trading days between exit and current date
    days_since = len([d for d in trading_dates if exit_date < d <= date])
    return days_since < cooldown_trading_days
```

A reasonable starting cooldown is 5–15 trading days in neutral/bear conditions. In a
strong bull trend, a very short or zero cooldown may actually be correct — the stop-out
was a brief dip and re-entry is valid. Test both against your own data.

## 8. Output summary table

After a multi-year run, print a summary table before saving results:

```
Year  | Trades | Win%   | Return | MaxDD  | AvgHold
------|--------|--------|--------|--------|--------
2019  |     22 |  63.6% | +18.4% |  -5.2% |   41d
2020  |     31 |  58.1% | +42.7% | -11.8% |   38d
...
```

Save full trade-level results (list of `closed_trade` dicts) to JSON alongside the
summary. The trade list is what you audit and attribute; the summary is what you
communicate.

## 9. Common structural bugs checklist

Before trusting any backtest number, confirm all of these:

- [ ] Warmup window is at least as long as the longest lookback signal.
- [ ] Every feature computation calls `.loc[:date]` (or equivalent) before any math.
- [ ] Scalers and ML models are fit inside the loop on `hist.loc[:date]` only.
- [ ] `fillna` / `interpolate` is not called on the full frame before the loop.
- [ ] Universe is point-in-time, or survivorship bias is explicitly disclosed.
- [ ] Exits are evaluated before entries on each date.
- [ ] `peak_price` is updated every loop iteration, not just at entry.
- [ ] Regime parameters are locked at entry time (not updated mid-hold to current regime).
- [ ] End-of-period close-out sells all open positions at the last available price.
- [ ] Metrics are computed post-loop, not accumulated inside the loop.

This checklist overlaps with the lookahead-audit skill — run that audit after the harness
is built to catch anything this list misses.
