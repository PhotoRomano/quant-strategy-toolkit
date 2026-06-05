# metrics-report — use this in any AI

Paste everything below the line into ChatGPT, Gemini, Copilot, or any assistant — as your
first message or a system/custom instruction. (In Claude you don't need this file — the skill
activates automatically.) Same method, same results; you just trigger it yourself.

*A StrongSkills tool — The shortcut to the cutting edge · getstrongskills.com*

---

Act as an expert and follow this method exactly.

# Metrics Report

A backtest report that gets the formulas wrong, omits caveats, or frames numbers out of context
is worse than no report. It creates false confidence and leads to bad live-trading decisions.

This skill covers three things: computing the standard metrics correctly, interpreting them
honestly, and structuring a report that a reader can actually trust. It does not tell you
whether a strategy is worth trading — only you can decide that after paper trading and proper
out-of-sample testing.

> Backtest metrics describe the past. They do not predict future returns. Every number in a
> backtest report should be read as "what this strategy *would have done*" — not as a return
> guarantee.

---

## Core metrics: formulas and what they actually measure

### CAGR — Compound Annual Growth Rate

```
CAGR = (end_value / start_value) ^ (1 / years) - 1
```

**Why it matters:** Total return inflates with time; CAGR normalizes across periods so you can
compare a 3-year backtest to a 7-year one fairly.

**Watch out for:** CAGR alone says nothing about the ride. A strategy with 40% CAGR and a -70%
drawdown is not the same as one with 25% CAGR and a -10% drawdown. Always report both.

### Max Drawdown (MDD)

```
MDD = min over all dates of (portfolio_value[t] - running_peak[t]) / running_peak[t]
```

In code:
```python
rolling_peak = portfolio_curve.cummax()
drawdown = (portfolio_curve - rolling_peak) / rolling_peak
max_drawdown = drawdown.min()   # a negative number, e.g. -0.22 = -22%
```

**Why it matters:** MDD is the largest peak-to-trough loss a real investor would have sat
through. It is the primary risk metric for a buy-and-hold position — the moment most people
psychologically capitulate and abandon a strategy is at or near the max drawdown.

**Complement it with:** max drawdown duration (how many calendar days the drawdown lasted),
and recovery time (days from trough back to prior peak). A 20% drawdown that recovered in
two weeks is very different from one that lasted two years.

### Sharpe Ratio

```
Sharpe = (mean_period_return - risk_free_rate) / std_dev_period_return
         * sqrt(annualization_factor)
```

Common annualization factors: daily returns → 252, weekly → 52, monthly → 12.

```python
daily_excess = daily_returns - risk_free_daily   # e.g. T-bill rate / 252
sharpe = daily_excess.mean() / daily_excess.std() * (252 ** 0.5)
```

**Why it matters:** Sharpe measures return per unit of volatility. A strategy with 30% CAGR
and Sharpe 0.4 took on enormous volatility to get there; one with 20% CAGR and Sharpe 1.8
had a much smoother ride. Smoother strategies are easier to stick with in live trading.

**Rough benchmarks** (use as orientation, not pass/fail thresholds — tune to your context):
- Below 0.5: hard to justify the volatility
- 0.5 – 1.0: acceptable for a concentrated equity strategy
- 1.0 – 2.0: solid risk-adjusted performance
- Above 2.0: investigate carefully — backtests with Sharpe > 2 are frequently over-fit

**Don't cherry-pick the risk-free rate.** Use the prevailing short-term rate for the backtest
period (e.g., 3-month T-bill average). Using 0% inflates Sharpe; using a rate from a
different era is misleading.

### Sortino Ratio

```
Sortino = (mean_period_return - risk_free_rate) / downside_deviation
          * sqrt(annualization_factor)
```

where `downside_deviation` uses only returns below the target (often 0 or the risk-free rate):

```python
negative_returns = daily_returns[daily_returns < target]
downside_dev = negative_returns.std() * (252 ** 0.5)
sortino = (annualized_return - risk_free_annual) / downside_dev
```

**Why it matters:** Sharpe penalizes upside volatility equally with downside. Sortino focuses
only on the harmful kind. Trend-following and momentum strategies often show more favorable
Sortino than Sharpe — that asymmetry is worth surfacing.

### Win Rate

```
Win Rate = winning_trades / total_trades
```

**Why it matters — and why it's incomplete:** A 40% win rate with a 3:1 average win/loss
ratio is a profitable strategy; a 65% win rate with a 0.5:1 ratio is a losing one. Always
report win rate alongside the **profit factor** and the **payoff ratio**.

### Profit Factor

```
Profit Factor = gross_winning_P&L / abs(gross_losing_P&L)
```

- Below 1.0: the strategy loses money in aggregate.
- Around 1.0 – 1.3: marginal; transaction costs may eliminate the edge.
- Above 1.5: meaningful positive expectancy (as of the backtest period).
- Above 3.0: investigate for data issues — unusually high values often trace to look-ahead
  bias or overfitting on a short sample.

### Payoff Ratio

```
Payoff Ratio = average_winning_trade_P&L / abs(average_losing_trade_P&L)
```

Combine with win rate to compute **expectancy per trade**:

```
Expectancy = (Win Rate * Avg Win) - (Loss Rate * Avg Loss)
```

If expectancy is negative, no position-sizing scheme makes the strategy profitable. Compute
this first before optimizing entry signals.

### Alpha vs Benchmark

```
Alpha = strategy_annualized_return - benchmark_annualized_return
```

For a risk-adjusted alpha (Jensen's Alpha):

```
Alpha_j = strategy_return - (risk_free + beta * (benchmark_return - risk_free))
```

where `beta = cov(strategy, benchmark) / var(benchmark)`.

**Why it matters:** Generating absolute returns in a bull market is not an edge — the index
itself did it. Alpha measures what you added beyond what a passive index investment would have
given you. Always compare to a relevant benchmark (e.g., SPY for US equities, not a bond index).

---

## The caveats that must appear in every report

These are not optional fine print — they are the difference between an honest report and a
misleading one. Include them even if nobody asks.

**1. Backtest period and market environment.** A strategy backtested only through 2019–2021
(a near-uninterrupted bull market) was never tested in a real bear market. State the full
period explicitly and characterize it: bull, bear, volatile, low-volatility.

**2. Out-of-sample vs in-sample.** Did you fit parameters on the same data you're reporting?
If so, all metrics are in-sample and will likely be optimistic. State this. Walk-forward
validation (pair with the `walk-forward-validation` skill) is the minimum standard for
credible out-of-sample evidence.

**3. Survivorship bias.** If the universe was built from today's index constituents applied to
a past date, failing companies are missing from the test. This inflates returns. State whether
the universe was point-in-time or survivorship-biased (see the `survivorship-check` skill).

**4. Transaction costs and slippage.** Report whether the backtest included commissions,
spread, and market impact. A strategy with 40+ trades per year looks very different once
realistic fill costs are applied (pair with the `execution-realism` skill).

**5. Look-ahead status.** State whether the backtest has been audited for look-ahead bias
(pair with the `lookahead-audit` skill). If it hasn't, say so.

**6. Design-bias disclosure.** If any parameters, universe inclusions, or event dates were
chosen with knowledge of how they turned out — even if every data read is temporally sound —
say so. This is honest, not embarrassing.

---

## Report structure

Produce every performance report in this exact format. Brevity is fine; omissions are not.

```
# Backtest Performance Report: <Strategy Name>

## Test Parameters
- Period: <start date> – <end date>  (<N> years)
- Universe: <how constructed, point-in-time or survivorship-biased>
- Starting capital: <amount>  |  Position sizing: <method>
- Transaction costs: <included / excluded / estimate>
- Out-of-sample: <yes / no / partial — walk-forward>

## Performance Summary
| Metric                  | Strategy | Benchmark (e.g. SPY) |
|-------------------------|----------|----------------------|
| Total Return            |          |                      |
| CAGR                    |          |                      |
| Max Drawdown            |          |                      |
| Max DD Duration         |          |                      |
| Sharpe Ratio            |          |                      |
| Sortino Ratio           |          |                      |
| Alpha vs Benchmark      |          |                      |

## Trade Statistics
| Metric          | Value |
|-----------------|-------|
| Total Trades    |       |
| Win Rate        |       |
| Payoff Ratio    |       |
| Profit Factor   |       |
| Avg Hold Period |       |
| Best Trade      |       |
| Worst Trade     |       |
| Avg Trade P&L   |       |

## Caveats and Limitations
1. <Backtest period / market environment characterization>
2. <In-sample / out-of-sample status>
3. <Survivorship bias status>
4. <Transaction cost assumptions>
5. <Look-ahead audit status>
6. <Any design-bias disclosures>

## Interpretation
<2-4 sentences: what the numbers actually say, framed as historical observations, not predictions>
```

---

## A worked micro-example

**Scenario:** a momentum strategy on US equities, 4-year backtest, 52 trades.

**Naive summary (problematic):**

> "The strategy returned 87% total, with a 63% win rate. Sharpe ratio was 1.9. Highly
> profitable — ready for live deployment."

This omits the period, costs, drawdown, whether it was in-sample, and the benchmark.
The Sharpe of 1.9 on a 4-year in-sample run of a momentum strategy is a strong reason
to be more skeptical, not less.

**Honest report (correct framing):**

```
## Test Parameters
- Period: Jan 2021 – Dec 2024  (4 years — predominantly bull market with one bear in 2022)
- Universe: Current S&P 500 members applied to historical dates (survivorship-biased)
- Transaction costs: excluded
- Out-of-sample: no — all parameters fitted on full period

## Performance Summary
| Metric          | Strategy | SPY    |
|-----------------|----------|--------|
| Total Return    | +87%     | +61%   |
| CAGR            | +17.1%   | +12.8% |
| Max Drawdown    | -19.4%   | -23.9% |
| Sharpe Ratio    | 1.9      | 1.1    |
| Alpha vs SPY    | +4.3 pp  | —      |

## Caveats and Limitations
1. Period is predominantly bullish; the single bear episode (2022) is the only stress test.
2. All parameters in-sample — Sharpe of 1.9 is likely optimistic; walk-forward validation
   is required before any live deployment.
3. Universe is survivorship-biased — companies that went bankrupt or were delisted are not
   present, which inflates returns by an unknown but likely material amount.
4. No transaction costs included — a strategy with this trade frequency should model
   realistic commissions and slippage before interpreting profitability.
5. Look-ahead bias audit not yet performed.

## Interpretation
On in-sample data the strategy outpaced SPY by 4.3 percentage points annually with lower
drawdown. The Sharpe of 1.9 cannot be trusted until walk-forward validated and survivorship
bias is addressed — the true out-of-sample figure is unknown. Do not treat these numbers as
a return projection.
```

The two reports contain the same numbers. The second one is the one that earns trust.

---

## Python implementation notes

When generating these metrics programmatically, watch three common formula errors:

**1. CAGR with fractional years** — use actual elapsed calendar days, not trade days:

```python
years = (end_date - start_date).days / 365.25
cagr = (end_value / start_value) ** (1 / years) - 1
```

**2. Annualizing Sharpe** — multiply the *ratio* (not the std) by sqrt(periods per year):

```python
# CORRECT
sharpe = (daily_excess.mean() / daily_excess.std()) * (252 ** 0.5)
# WRONG — don't annualize mean and std separately then divide
```

**3. Max drawdown on equity curve, not returns** — compute from the cumulative portfolio
value series, not from the daily return series:

```python
# CORRECT — from portfolio curve
peak = portfolio_curve.cummax()
mdd = ((portfolio_curve - peak) / peak).min()

# WRONG — from return series (gives max single-period loss, not true drawdown)
mdd_wrong = daily_returns.min()
```

---

## When the report surfaces a red flag

Some metric combinations should trigger further investigation before trusting the results:

- Sharpe > 2.5 on an in-sample run of less than 5 years: almost always overfitting.
- Win rate > 70% with profit factor > 3: verify there is no look-ahead bias; these
  combinations are extremely rare in honest backtests on equity momentum.
- Max drawdown significantly lower than the benchmark during a known market crash: check
  whether the strategy was actually flat (no trades) during the crash, or whether the
  crash period was excluded from the backtest window.
- CAGR far above benchmark but Sharpe below 0.7: strategy is likely taking large concentrated
  risks that happened to pay off in the test period; test for path dependence.

For deeper investigation of any of these, pair with the `lookahead-audit` skill (data
integrity), `walk-forward-validation` skill (overfitting), and `execution-realism` skill
(cost assumptions).

---

## Reference

Detailed metric formulas, edge cases, and code patterns for building a metrics module from
scratch are in `references/metric-formulas.md`.


<!-- strongskills-brand -->

---

*Made with a StrongSkills tool — The shortcut to the cutting edge · getstrongskills.com*
