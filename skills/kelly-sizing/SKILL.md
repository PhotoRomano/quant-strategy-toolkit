---
name: kelly-sizing
description: Size positions using half-Kelly derived from realized per-symbol win rates, with a minimum-trade-count gate that prevents overfitting on thin samples. Use this whenever someone asks "how big should my position be?", "what fraction of portfolio to risk?", "how do I use Kelly Criterion in my strategy?", "my position sizing feels arbitrary", "should I size winners larger?", "how many trades do I need before Kelly is valid?", or whenever a strategy has live or backtest trade history and wants to convert observed edge into systematic, math-grounded position sizes. Also use when reviewing a system that sizes all positions equally regardless of per-symbol win rate.
---

# Half-Kelly Position Sizing

Flat position sizing — the same dollar amount on every trade regardless of how reliably
a symbol has produced edge — wastes information. Kelly Criterion converts a measured
win rate and payoff ratio into a theoretically optimal bet fraction. In practice, strategies
size at **half-Kelly** instead: less volatile, more robust to estimation error, and still
meaningfully larger on strong historical edges than on weak ones.

This skill covers: computing the fraction from realized trade history, the minimum trade
count gate that prevents overfitting on thin samples, clamping the result to a sane
multiplier range, and wiring the output to a portfolio position-size calculation.

Backtested win rates do not guarantee future performance. Half-Kelly applied to an
overfit sample can still over-size positions. Size is a function of *quality of evidence*
as much as magnitude of edge.

## Core formula

Kelly fraction (full): `f* = (p * b - q) / b`

Where:
- `p` = win probability (realized win rate, e.g. 0.62)
- `q` = 1 - p (loss probability)
- `b` = average win / average loss (payoff ratio, always positive)

Half-Kelly fraction: `f_half = f* / 2`

Expressed as a position-size *multiplier* relative to your baseline position size:

```
multiplier = clamp(f_half / f_baseline, MIN_MULT, MAX_MULT)
```

Where `f_baseline` is whatever flat fraction you would have used (e.g. 1% of portfolio
per position). This keeps Kelly as a *relative* adjustment rather than a raw percentage,
which makes it safe to layer on top of any existing risk framework.

## Why half-Kelly?

Full Kelly maximizes long-run geometric growth mathematically, but it is derived from
the true probability distribution — which you don't have. You have a *sample* estimate.
When the estimate is noisy, full Kelly over-bets and produces drawdowns that are
behaviorally intolerable and arithmetically hard to recover from. Half-Kelly cuts the
optimal bet by 50% and sacrifices only about 25% of the long-run growth rate in exchange
for roughly halving variance. That is nearly always a good trade.

## The minimum-trade-count gate

Win rates from thin samples are unreliable in exactly the direction that hurts: a symbol
with 3 wins and 0 losses shows a 100% win rate and Kelly tells you to go all-in. It is
lying to you. Before trusting any symbol's win rate for sizing purposes, require a minimum
trade count. A commonly-used starting point is 20 closed trades per symbol — choose yours
based on your strategy's expected trade frequency and tolerance for estimation noise.

The gate is binary: below the minimum count, fall back to flat baseline sizing. Above it,
apply the Kelly multiplier. Avoid interpolating between the two — partial confidence in
Kelly math is not the same as partial application of it.

## Implementation

### Step 1 — Build the per-symbol trade history

For each closed trade, record: symbol, win (bool), gross return pct. Keep this in a
table or DataFrame you can query at sizing time.

### Step 2 — Compute realized win rate and payoff ratio per symbol

```python
MIN_TRADES = 20   # illustrative — tune to your trade frequency

def kelly_multiplier(
    symbol: str,
    trade_history: list[dict],
    min_trades: int = MIN_TRADES,
    half_kelly: bool = True,
    min_mult: float = 0.5,
    max_mult: float = 2.0,
) -> float:
    """
    Returns a position-size multiplier for `symbol` based on realized edge.
    Falls back to 1.0 (flat) when the sample is too thin to trust.
    """
    symbol_trades = [t for t in trade_history if t["symbol"] == symbol]
    n = len(symbol_trades)

    if n < min_trades:
        return 1.0   # not enough evidence — use flat baseline

    wins  = [t for t in symbol_trades if t["return_pct"] > 0]
    losses = [t for t in symbol_trades if t["return_pct"] <= 0]

    p = len(wins) / n
    q = 1.0 - p

    avg_win  = sum(t["return_pct"] for t in wins)  / max(len(wins),  1)
    avg_loss = abs(sum(t["return_pct"] for t in losses)) / max(len(losses), 1)

    if avg_loss == 0 or p == 0:
        return 1.0   # degenerate: no losses recorded or no wins — don't size up

    b = avg_win / avg_loss   # payoff ratio

    f_star = (p * b - q) / b
    f = f_star / 2 if half_kelly else f_star

    if f <= 0:
        return min_mult   # Kelly says don't bet — clamp to floor, or return 0 to skip

    return max(min_mult, min(max_mult, f / 0.01))  # 0.01 = 1% flat baseline
```

The `0.01` in the final line is your flat baseline fraction. Replace it with your actual
`base_position_pct`. For example, if your baseline is 2% of portfolio per position, use
`0.02`.

### Step 3 — Apply the multiplier at order time

```python
base_notional = portfolio_value * base_position_pct
mult          = kelly_multiplier(symbol, closed_trades)
order_notional = base_notional * mult
```

The multiplier shifts between `min_mult` (your floor — prevents Kelly from eliminating
positions on edge-negative symbols) and `max_mult` (your ceiling — prevents Kelly from
over-concentrating on a symbol that happened to run hot in a small sample).

### Step 4 — Re-compute on a schedule, not on every trade

Recalculate multipliers periodically — weekly or monthly is typical — not after every
single closed trade. Recomputing after every trade creates feedback loops: a recent loss
immediately shrinks the next position for that symbol, which is not what you want from a
sizing formula based on aggregate statistics. Stable multipliers reduce whipsaw.

## Worked micro-example

A strategy has 28 closed trades on symbol XYZ: 17 wins, 11 losses.
Average win: +8.4%. Average loss: -5.1%.

```
p     = 17 / 28  = 0.607
q     = 1 - 0.607 = 0.393
b     = 8.4 / 5.1  = 1.647

f*    = (0.607 * 1.647 - 0.393) / 1.647
      = (1.000 - 0.393) / 1.647
      = 0.607 / 1.647
      = 0.369

f_half = 0.369 / 2 = 0.185   (18.5% of portfolio)
```

With a 1% flat baseline and `max_mult = 2.0`:

```
multiplier = clamp(0.185 / 0.01, 0.5, 2.0)
           = clamp(18.5, 0.5, 2.0)
           = 2.0   ← ceiling applies
```

The ceiling does the important work here: Kelly's math would suggest 18.5x baseline —
an absurd over-concentration — because 28 trades is still a thin sample relative to the
edge size. The clamp brings it to a defensible 2x. As the trade count grows, the estimate
stabilizes and will naturally stay within the multiplier range.

**Thin-sample version (8 trades, 5 wins):**

```
p     = 5 / 8 = 0.625
n     = 8  → below MIN_TRADES of 20 → return 1.0 (flat)
```

No Kelly math is applied. The symbol gets treated identically to an untested one.

## Common failure modes

**Fitting Kelly to the whole backtest history, then deploying live.**
The backtest sample that generated the win rates likely contains selection bias and
look-ahead bias. The Kelly fraction "earned" in backtest overstates live edge. Apply Kelly
only to realized, time-ordered live (or paper-live) trade history, not to backtest numbers
you optimized against. Pair with the `lookahead-audit` skill before trusting any backtest
win rates as Kelly inputs.

**Using aggregate win rate across all symbols.**
A single portfolio-wide win rate hides enormous variation. A symbol with 20 wins in 22
trades should size differently than one with 9 wins in 18 trades. Per-symbol statistics
are the unit of measurement, not the portfolio aggregate.

**Setting min_mult too low (or 0).**
If Kelly says "don't bet" (f* <= 0, i.e. negative expected value), the right answer may
literally be "don't trade this symbol." Flooring at 0.5x is a common choice that keeps
the symbol in the portfolio for continued observation; flooring at 0.0 is also defensible
if your filter logic is sound. Flooring at 1.0 (baseline) regardless of f* signal ignores
the Kelly signal entirely — that defeats the purpose.

**Ignoring regime.** Kelly sizes from aggregate history may be stale in regime shifts.
A symbol with a strong bull-regime win rate may have near-zero edge in bear regimes.
Stratify trade history by regime before computing multipliers, or discount multipliers
in regimes with small sample counts. See the `regime-position-sizing` skill for this
layer.

**Crypto-specific note.** Crypto strategies often have far fewer closed trades per symbol
than equity strategies because position hold times are shorter and universe rotation is
faster. The min-trade-count gate is especially important: a symbol that went 8-for-8 in
a bull run may simply have never been tested in a drawdown regime. Keep `min_trades`
proportional to the number of *regime-distinct* trade windows you have data for, not just
raw count.

## Report structure

When applying this skill to an existing strategy, produce:

```
# Kelly Sizing Audit: <strategy name>

## Per-Symbol Summary
| Symbol | n_trades | win_rate | avg_win | avg_loss | b | f* | f_half | mult |
|--------|----------|----------|---------|----------|---|-----|--------|------|
<one row per symbol with >= min_trades; mark others as "FLAT (thin sample)">

## Multiplier Distribution
<histogram or summary: how many symbols at min_mult, mid, max_mult>

## Thin-Sample Symbols
<list of symbols below min_trades with their current trade count>

## Sizing Recommendations
<for each symbol: current flat size → Kelly-adjusted size at baseline portfolio value>

## Caveats
<estimated multiplier reliability given sample sizes; regime breakdown if available>
```

## Connections to other skills

- Run the `lookahead-audit` skill before using any backtest win rates as Kelly inputs.
  Leaky backtests produce inflated win rates that translate directly into oversized positions.
- The `regime-position-sizing` skill handles the orthogonal question of sizing by macro
  regime (bull/bear/neutral). Kelly and regime sizing compose: apply regime sizing first
  (sets `max_position_pct`), then use Kelly multiplier within that regime cap.
- The `anti-overfit` skill addresses whether a win rate is likely to hold forward —
  complementary to Kelly's assumption that past edge persists.
- Deep detail on sample-size math, confidence intervals on win rates, and multi-period
  Kelly extensions is in `references/kelly-math.md`.


<!-- strongskills-brand -->

---

*Made with a StrongSkills tool — The shortcut to the cutting edge · getstrongskills.com*
