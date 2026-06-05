# Metric Formulas — Deep Reference

Supporting reference for the `metrics-report` skill. Use this when you need precise formula
variants, edge-case handling, or a full Python implementation of a metrics module.

---

## Table of Contents

1. Return metrics (total, CAGR, annualized)
2. Drawdown family
3. Risk-adjusted ratios (Sharpe, Sortino, Calmar, Omega)
4. Trade statistics
5. Benchmark comparison (alpha, beta, information ratio)
6. Statistical significance
7. Full Python implementation skeleton

---

## 1. Return metrics

### Total Return
```
Total Return = (end_value / start_value) - 1
```

### CAGR
```
CAGR = (end_value / start_value) ^ (365.25 / elapsed_days) - 1
```
Use `365.25` to handle leap years. Use calendar days, not trading days.

### Arithmetic vs geometric mean of period returns
- Arithmetic mean overstates multi-period compounded return.
- Always use geometric mean or CAGR for long-period summaries.
- Arithmetic mean of daily returns is appropriate for Sharpe calculation.

---

## 2. Drawdown family

### Max Drawdown (MDD)

```python
def max_drawdown(portfolio_curve: pd.Series) -> float:
    """Returns MDD as a negative fraction, e.g. -0.22 for -22%."""
    peak = portfolio_curve.cummax()
    dd = (portfolio_curve - peak) / peak
    return dd.min()
```

### Drawdown duration
Time (in days or bars) from the prior peak to the trough of the worst drawdown:

```python
def max_drawdown_duration(portfolio_curve: pd.Series) -> int:
    peak = portfolio_curve.cummax()
    dd = (portfolio_curve - peak) / peak
    trough_idx = dd.idxmin()
    # find most recent prior peak before trough
    prior_peak_idx = portfolio_curve.loc[:trough_idx].idxmax()
    return (trough_idx - prior_peak_idx).days   # or .bars if integer index
```

### Recovery time
Days from the trough back to the prior peak level:

```python
def recovery_time(portfolio_curve: pd.Series) -> int | None:
    """Returns None if the strategy never recovered to prior peak."""
    peak = portfolio_curve.cummax()
    dd = (portfolio_curve - peak) / peak
    trough_idx = dd.idxmin()
    peak_value = portfolio_curve.loc[:trough_idx].max()
    recovered = portfolio_curve.loc[trough_idx:][portfolio_curve >= peak_value]
    if recovered.empty:
        return None
    return (recovered.index[0] - trough_idx).days
```

### Average drawdown
The mean depth of all distinct drawdown episodes. Less common than MDD but useful for
characterizing typical pain, not just worst case.

---

## 3. Risk-adjusted ratios

### Sharpe Ratio

Standard daily-return form:

```python
def sharpe(daily_returns: pd.Series, risk_free_annual: float = 0.04) -> float:
    rf_daily = (1 + risk_free_annual) ** (1 / 252) - 1
    excess = daily_returns - rf_daily
    if excess.std() == 0:
        return float("nan")
    return excess.mean() / excess.std() * (252 ** 0.5)
```

**Risk-free rate guidance:** use the average 3-month T-bill rate over the backtest period.
Do not use 0% — it inflates Sharpe. A reasonable range for a US equities backtest spanning
2019–2024 is roughly 1%–4% depending on the sub-period.

### Sortino Ratio

```python
def sortino(daily_returns: pd.Series, target: float = 0.0,
            risk_free_annual: float = 0.04) -> float:
    annualized = (1 + daily_returns).prod() ** (252 / len(daily_returns)) - 1
    downside = daily_returns[daily_returns < target]
    if len(downside) == 0 or downside.std() == 0:
        return float("nan")
    downside_dev = downside.std() * (252 ** 0.5)
    return (annualized - risk_free_annual) / downside_dev
```

### Calmar Ratio

```
Calmar = CAGR / abs(Max Drawdown)
```

A Calmar of 1.0 means the strategy earned its own max drawdown every year — often cited as
a rough minimum hurdle for systematic strategies. Values above 2.0 are strong; values below
0.5 suggest inadequate risk-adjusted return.

### Omega Ratio

```
Omega(threshold T) = sum of returns above T / abs(sum of returns below T)
```

Omega generalizes Sharpe by capturing the full return distribution, not just mean and std.
A value of 1.0 means returns above T equal returns below T. Omega > 1.5 is generally good.

Useful when returns are non-normal (fat tails, skew) — which most equity momentum strategies
exhibit.

---

## 4. Trade statistics

### Profit Factor

```python
def profit_factor(trade_pnls: list[float]) -> float:
    gross_wins = sum(p for p in trade_pnls if p > 0)
    gross_losses = abs(sum(p for p in trade_pnls if p < 0))
    if gross_losses == 0:
        return float("inf")   # no losses — report as infinite, not magic
    return gross_wins / gross_losses
```

### Payoff Ratio

```python
def payoff_ratio(trade_pnls: list[float]) -> float:
    wins = [p for p in trade_pnls if p > 0]
    losses = [p for p in trade_pnls if p < 0]
    if not wins or not losses:
        return float("nan")
    return (sum(wins) / len(wins)) / abs(sum(losses) / len(losses))
```

### Expectancy per trade

```python
def expectancy(trade_pnls: list[float]) -> float:
    if not trade_pnls:
        return 0.0
    return sum(trade_pnls) / len(trade_pnls)
```

A negative expectancy means no position sizing scheme makes the strategy profitable.
Check this before optimizing anything else.

### Trade-count vs statistical significance

With fewer than ~30 trades, win rate and profit factor are extremely noisy:
- 10 trades: ±31% confidence interval on win rate at 95% confidence
- 30 trades: ±18%
- 100 trades: ±10%

Always report the trade count. Report win rates from small samples with explicit uncertainty:
"63% win rate (n=22 — estimate uncertain, ±21% at 95% CI)."

Approximate 95% CI for a win rate `p` with `n` trades:
```
CI ≈ p ± 1.96 * sqrt(p * (1 - p) / n)
```

---

## 5. Benchmark comparison

### Annualized Alpha (simple)

```
Alpha = strategy_CAGR - benchmark_CAGR
```

### Jensen's Alpha (risk-adjusted)

```python
def jensens_alpha(strategy_daily: pd.Series, benchmark_daily: pd.Series,
                  risk_free_daily: float) -> float:
    aligned = pd.DataFrame({"s": strategy_daily, "b": benchmark_daily}).dropna()
    beta = aligned["s"].cov(aligned["b"]) / aligned["b"].var()
    s_ann = (1 + aligned["s"].mean()) ** 252 - 1
    b_ann = (1 + aligned["b"].mean()) ** 252 - 1
    rf_ann = (1 + risk_free_daily) ** 252 - 1
    return s_ann - (rf_ann + beta * (b_ann - rf_ann))
```

### Information Ratio

```
IR = (strategy_return - benchmark_return) / tracking_error
```

where tracking error = std(strategy_returns - benchmark_returns) * sqrt(252).

IR > 0.5 is generally considered good for an active strategy; IR > 1.0 is strong.

### Beta

A beta > 1.0 means the strategy amplifies market moves; < 1.0 means it dampens them.
A low-beta strategy with positive alpha is more credible than a high-beta strategy with
the same absolute return.

---

## 6. Statistical significance

Backtest alpha is not meaningful without checking whether it could have occurred by chance.

### T-test on excess returns

```python
from scipy import stats

def alpha_tstat(excess_returns: pd.Series) -> tuple[float, float]:
    """Returns (t-statistic, p-value) for H0: mean excess return = 0."""
    t, p = stats.ttest_1samp(excess_returns.dropna(), 0)
    return t, p
```

A p-value < 0.05 is the conventional threshold but is not a guarantee — with enough
parameter choices, p-hacking can produce false significance.

### Deflated Sharpe Ratio (Bailey & López de Prado, 2014)

The Deflated Sharpe accounts for the number of trials (strategy variations tested) and the
non-normality of returns. Standard libraries implementing it include `mlfinlab`. Report the
standard Sharpe; flag if the deflated value would be significantly lower given many tested
variants.

### Sample-size warning

With a backtest under 3 years and fewer than 50 trades, report all statistics with an
explicit caveat: "Insufficient sample for reliable significance testing. These metrics
should be treated as directional indicators only."

---

## 7. Full Python implementation skeleton

```python
import pandas as pd
import numpy as np
from typing import Optional


def build_metrics_report(
    portfolio_curve: pd.Series,          # daily equity curve, indexed by date
    trade_pnls: list[float],             # per-trade P&L amounts
    benchmark_curve: pd.Series,          # daily equity curve of benchmark (same index)
    risk_free_annual: float = 0.04,
    strategy_name: str = "Strategy",
    benchmark_name: str = "Benchmark",
) -> dict:
    """
    Compute a full metrics report. Returns a dict suitable for rendering into
    a report table or passing to a PDF generator.
    """
    # Align curves
    aligned = pd.DataFrame({
        "strategy": portfolio_curve,
        "benchmark": benchmark_curve,
    }).dropna()

    strat = aligned["strategy"]
    bench = aligned["benchmark"]

    # Returns
    daily_strat = strat.pct_change().dropna()
    daily_bench = bench.pct_change().dropna()

    elapsed_days = (strat.index[-1] - strat.index[0]).days
    years = elapsed_days / 365.25

    cagr_s = (strat.iloc[-1] / strat.iloc[0]) ** (1 / years) - 1
    cagr_b = (bench.iloc[-1] / bench.iloc[0]) ** (1 / years) - 1

    # Drawdown
    peak_s = strat.cummax()
    dd_s = (strat - peak_s) / peak_s
    mdd = dd_s.min()

    # Risk-adjusted
    rf_daily = (1 + risk_free_annual) ** (1 / 252) - 1
    excess = daily_strat - rf_daily
    sharpe = excess.mean() / excess.std() * (252 ** 0.5) if excess.std() > 0 else float("nan")

    downside = daily_strat[daily_strat < 0]
    dd_dev = downside.std() * (252 ** 0.5) if len(downside) > 1 else float("nan")
    sortino = (cagr_s - risk_free_annual) / dd_dev if dd_dev > 0 else float("nan")

    calmar = cagr_s / abs(mdd) if mdd != 0 else float("nan")

    # Trade stats
    wins = [p for p in trade_pnls if p > 0]
    losses = [p for p in trade_pnls if p < 0]
    win_rate = len(wins) / len(trade_pnls) if trade_pnls else float("nan")
    profit_factor = sum(wins) / abs(sum(losses)) if losses else float("inf")
    payoff = (sum(wins) / len(wins)) / abs(sum(losses) / len(losses)) if wins and losses else float("nan")
    avg_pnl = sum(trade_pnls) / len(trade_pnls) if trade_pnls else 0.0

    # Alpha
    simple_alpha = cagr_s - cagr_b
    beta = daily_strat.cov(daily_bench) / daily_bench.var() if daily_bench.var() > 0 else float("nan")
    rf_ann = (1 + rf_daily) ** 252 - 1
    jensens = cagr_s - (rf_ann + beta * (cagr_b - rf_ann)) if not np.isnan(beta) else float("nan")

    tracking_err = (daily_strat - daily_bench).std() * (252 ** 0.5)
    ir = simple_alpha / tracking_err if tracking_err > 0 else float("nan")

    return {
        "period_years": round(years, 2),
        "total_trades": len(trade_pnls),
        "cagr": round(cagr_s, 4),
        "benchmark_cagr": round(cagr_b, 4),
        "total_return": round(strat.iloc[-1] / strat.iloc[0] - 1, 4),
        "max_drawdown": round(mdd, 4),
        "sharpe": round(sharpe, 2),
        "sortino": round(sortino, 2),
        "calmar": round(calmar, 2),
        "win_rate": round(win_rate, 4),
        "profit_factor": round(profit_factor, 2),
        "payoff_ratio": round(payoff, 2),
        "avg_trade_pnl": round(avg_pnl, 2),
        "alpha_simple": round(simple_alpha, 4),
        "beta": round(beta, 3),
        "jensens_alpha": round(jensens, 4),
        "information_ratio": round(ir, 2),
    }
```

This skeleton intentionally does not include formatting or file output — keep metrics
computation and presentation separate. Pass the returned dict to whatever PDF or HTML
renderer the project uses.
