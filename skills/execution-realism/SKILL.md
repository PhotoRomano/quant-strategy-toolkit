---
name: execution-realism
description: Audit and repair the fill-price assumptions in a quantitative backtest so simulated trades reflect what a real broker would actually execute — accounting for next-bar timing, slippage, spread, commissions, and volume-based capacity constraints. Use this whenever someone asks "why does my backtest beat live trading?", "am I filling at unrealistic prices?", "how do I add slippage to my backtest?", "should I fill at open or close?", "my position sizes are too large for the stock's volume", "add realistic fees", "how do I simulate intraday entry quality?", "what is a volume participation cap?", "my backtest uses the signal bar's close but I can't trade the close in real life", or "how do I model VWAP-based entry quality". Also use proactively when reviewing any backtest that fills at the close of the signal bar, ignores commissions entirely, sizes positions without checking average daily volume, or uses bar-low for buys and bar-high for sells.
---

# Execution Realism

A backtest can be temporally honest — every data read correctly gated to the decision date —
and still overstate live performance by a wide margin because of how it assumes trades get
filled. Execution assumptions are the second silent leak after look-ahead bias.

The most aggressive fill assumptions are:
- fill at the **close of the signal bar** (you can't trade a close you haven't seen yet)
- fill at the **day's low for buys / day's high for sells** (best possible intraday price)
- **zero slippage and zero fees** (no broker has ever existed without these)
- **unlimited liquidity** — size a position to 100% of a single day's volume if needed

Each of these inflates simulated P&L. Together they can make a losing strategy look like a
winner. This skill teaches you to audit for each one and apply realistic corrections.

> **Honesty caveat:** Realistic fill simulation makes a backtest more honest, not more
> profitable. Tightening fill assumptions typically reveals that live-tradeable edge is smaller
> than the original backtest suggested. That is correct information, not a failure.

## The four execution gaps

### 1. Fill timing: close vs. next-bar open

**The problem.** If a signal is generated using close-of-day data (prices, indicators, scores),
the decision is made at the close. A real trader cannot simultaneously consume the close price
*and* execute at that same close. The fill happens at the *next available price*, which is
typically the following bar's open.

**The danger sign.**
```python
# Signal fires on date D using today's close
score = compute_score(hist.loc[:D])
if score > threshold:
    entry_price = hist.loc[D, "close"]   # WRONG — uses the price that triggered the signal
```

**The fix: next-bar fill.**
```python
# Signal fires on D; fill on D+1 at open
if score > threshold:
    next_bar = trading_dates[trading_dates.index(D) + 1]
    entry_price = prices.loc[next_bar, "open"]   # realistic: D+1 open
```

This single change — shifting the fill one bar forward — is often the largest single
drag on simulated performance. If the strategy survives it, that is a meaningful positive
signal. If it collapses, the apparent edge was living entirely in the signal bar's close.

### 2. Slippage

**The problem.** Even after fixing fill timing, the next-bar open is only where the market
*starts* trading. Real fills deviate from the opening print due to market impact, bid-ask
spread, and queue position. This deviation is **slippage**.

Slippage grows with:
- Position size relative to average daily volume (ADV): larger = more market impact
- Volatility: wider intraday ranges make the open print less representative
- Stock liquidity: micro/small-cap names move further on the same dollar order size

**A practical model** (illustrative starting point; calibrate to your asset class and size):

```python
def slippage_cost(price: float, shares: float, adv_shares: float,
                  base_bps: float = 5.0, impact_factor: float = 0.1) -> float:
    """
    Returns total slippage cost in dollars (already signed: positive = always a cost).

    base_bps:      minimum spread/slippage regardless of size (tune this)
    impact_factor: how much participation % amplifies slippage (tune this)
    """
    participation = shares / adv_shares          # fraction of a day's volume
    slippage_bps  = base_bps + impact_factor * participation * 10_000
    return price * shares * (slippage_bps / 10_000)
```

Apply slippage symmetrically: buys pay more (fill above open), sells receive less (fill
below open).

```python
fill_price_buy  = open_price * (1 + slippage_bps / 10_000)
fill_price_sell = open_price * (1 - slippage_bps / 10_000)
```

You will need to calibrate `base_bps` and `impact_factor` to your actual asset class.
Large-cap equities in normal conditions might warrant a lower base than micro-caps or
illiquid names. The numbers above are a starting framework, not a prescription.

### 3. Commissions and fees

**The problem.** Every executed fill incurs cost. Even at a "zero-commission" broker,
payment-for-order-flow and exchange fees mean you do not receive the theoretical midpoint.
For strategies with high turnover, cumulative fee drag is substantial.

**A minimal fee model:**

```python
COMMISSION_PER_SHARE = 0.005    # illustrative starting point; adjust to your broker
SEC_FEE_PER_DOLLAR   = 0.0000229  # US SEC fee for sells (as of mid-2025; verify current rate)

def trade_cost(shares: float, price: float, direction: str) -> float:
    commission = abs(shares) * COMMISSION_PER_SHARE
    sec_fee    = (abs(shares) * price * SEC_FEE_PER_DOLLAR) if direction == "sell" else 0.0
    return commission + sec_fee
```

Subtract trade cost from P&L at both entry and exit. Over hundreds of trades a year, even
small per-share fees accumulate into multiple percentage points of annual drag. A backtest
with zero fees will overstate performance by exactly this amount — predictably.

### 4. Volume-based position caps (capacity constraints)

**The problem.** Sizing a position without regard to the stock's traded volume can produce
hypothetical trades that are physically impossible: you cannot buy $5M of a stock that trades
$200K/day without moving the price against yourself catastrophically.

**The fix: participation cap.** Limit position size so your simulated order is a bounded
fraction of average daily volume (ADV). A commonly cited starting point for a non-market-
impact strategy is 5–15% of ADV; crossing 20–25% typically means meaningful market impact
that the slippage model must account for. Calibrate this to your strategy's holding period
and the liquidity tier of your universe.

```python
def volume_capped_shares(
    desired_shares: float,
    adv_shares: float,
    max_participation: float = 0.10   # illustrative: tune this
) -> float:
    """Returns the smaller of desired_shares and the volume cap."""
    cap = adv_shares * max_participation
    return min(desired_shares, cap)
```

When the cap binds, record that the position was size-constrained. If it binds frequently,
the strategy may have a genuine capacity problem: it requires more liquidity than exists at
its target size.

## Intraday entry quality: VWAP-band tiers

For strategies that execute intraday (e.g., on 5-minute bars), fill quality can be modeled
more finely than a flat slippage assumption. A VWAP-band approach assigns a quality tier to
each potential entry based on where the current price sits relative to the day's running VWAP:

```
Tier A: price <= VWAP - 0.5 * band_width   (buying below VWAP — favorable)
Tier B: VWAP - 0.5 * band_width < price <= VWAP + 0.5 * band_width  (near VWAP — neutral)
Tier C: price > VWAP + 0.5 * band_width    (buying above VWAP — unfavorable)
```

The VWAP and band width are computed from the intraday price/volume up to the current bar
(never using future bars within the session). The tier then drives a sizing multiplier:
Tier A entries may warrant full size; Tier C entries may warrant reduced size or a pass.
The specific thresholds and multipliers are calibration parameters you tune to your data;
the tier structure itself is the framework.

**Implementation note:** the running VWAP must be recomputed bar-by-bar, using only the
bars that have already printed. Never compute VWAP over the full session and look it up —
that introduces intraday look-ahead bias.

```python
def running_vwap(prices: list[float], volumes: list[float]) -> float:
    """VWAP through bar i; call with prices[:i+1], volumes[:i+1]."""
    pv = sum(p * v for p, v in zip(prices, volumes))
    return pv / sum(volumes)
```

See `references/fill-model-cookbook.md` for a complete worked example with tier assignment,
sizing multiplier lookup, and per-tier trade log.

## A worked micro-example: close fill vs. next-bar fill

**Scenario.** A momentum strategy fires a buy signal on a stock that rallied +3% on the
signal day. The close is at $103. The next morning the stock gaps down to $100 (the
market's efficient re-pricing of the move), then continues lower.

**Leaky version (close fill):**
```python
entry_price = prices.loc[signal_date, "close"]   # $103
# Strategy sees it "bought" at the top of the signal day's run
```

**Realistic version (next-bar open fill):**
```python
next_day    = trading_dates[trading_dates.index(signal_date) + 1]
entry_price = prices.loc[next_day, "open"]        # $100 — gap-down open
```

In this case the fill difference is $3/share (2.9%). Compounded across dozens of similar
trades — all of which fired after a strong-close day — the aggregate fill optimism can
account for a large fraction of a strategy's apparent backtest alpha.

## Audit workflow

When reviewing a backtest for execution realism, check each item in this sequence:

1. **Fill timing** — Does every entry and exit use a price from a bar *after* the signal
   bar? Specifically: if the signal is computed from bar D's close, is the fill on bar D+1
   open (or later)? Flag any `prices.loc[signal_date, "close"]` used as fill price.

2. **Slippage** — Is there any slippage model at all? If not, is there at least a per-trade
   cost approximation? A zero-slippage backtest is acceptable only as a "gross" baseline;
   never as the final performance claim.

3. **Fees** — Are commission and exchange fees deducted from P&L? Is turnover high enough
   that fee drag would be material (generally: >1 round-trip per week per position)?

4. **Volume caps** — Is maximum position size bounded by a participation fraction of ADV?
   Are any desired fills larger than 20–25% of ADV? If so, slippage for those fills will
   be substantially higher than the baseline model assumes.

5. **Symmetric treatment** — Are buys and sells treated symmetrically? A common asymmetry:
   slippage only on entries, none on exits; or fees only on buys. Both directions incur costs.

## Report structure

Produce the execution review in this format:

```
# Execution Realism Review: <strategy name>

## Verdict
<CLEAN / ISSUES FOUND / CANNOT VERIFY — one sentence.>

## Fill Timing
<Signal-bar close or next-bar? Confirmed / Issue / Cannot verify.>

## Slippage Model
<Model present? Type (flat bps / volume-impact)? Calibrated to asset class?>

## Fee Model
<Commission and exchange fees included? Turnover impact estimated?>

## Volume / Capacity
<ADV-based participation cap present? Largest simulated fills as % of ADV?>

## Net Effect Estimate
<If issues found: rough estimate of the aggregate fill-optimism in annual return terms.>

## Recommended Fixes
<For each issue: the specific code change.>
```

## What to pair this with

- **lookahead-audit** — execution realism is the complement to temporal gating; audit both
  before trusting any reported number.
- **backtest-harness** — the harness provides the loop structure; wire the fill model into
  the entry/exit handlers that the harness calls.
- **kelly-sizing** — realistic fill costs change the effective edge per trade; re-run Kelly
  calculations after applying the corrected fill model.
- **metrics-report** — regenerate the performance report after applying fill corrections so
  any comparison to the "gross" (pre-correction) baseline is explicit.


<!-- strongskills-brand -->

---

*Made with a StrongSkills tool — The shortcut to the cutting edge · getstrongskills.com*
