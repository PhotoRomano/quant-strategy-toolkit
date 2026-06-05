# profit-ladder — use this in any AI

Paste everything below the line into ChatGPT, Gemini, Copilot, or any assistant — as your
first message or a system/custom instruction. (In Claude you don't need this file — the skill
activates automatically.) Same method, same results; you just trigger it yourself.

*A StrongSkills tool — The shortcut to the cutting edge · getstrongskills.com*

---

Act as an expert and follow this method exactly.

# Profit-Taking Ladder

A profit-taking ladder sells your position in pre-defined tranches as the price climbs,
each tranche firing exactly once. The goal is to lock in partial gains on the way up
without closing a position that may continue to run.

Getting this wrong produces subtle, expensive bugs: a level fires twice (doubling your
exit), a level is skipped when a candle gaps through it, or a crash recovery re-fires
every already-triggered level. A clean implementation prevents all three.

This skill does **not** select target levels for you — the right levels depend on your
strategy's average winner profile, your position sizing model, and your risk tolerance.
The worked examples use illustrative numbers as concrete starting points; treat them as
scaffolding to tune, not as prescriptions.

---

## The core idea in three sentences

Define N price-gain thresholds and an exit fraction for each. When the current price
crosses a threshold, sell that fraction of the **original** position once and mark the
level fired. Never reconsider a fired level.

---

## Step 1 — Specify the ladder

A ladder is a list of `(gain_pct, fraction_to_sell)` pairs, ordered from smallest to
largest gain. Fractions refer to the **original** position size on entry, not the
remaining size, which avoids fraction-math surprises as shares shrink.

```python
LADDER = [
    (0.15, 0.25),   # sell 25% of original position at +15%
    (0.30, 0.25),   # sell another 25% at +30%
    (0.50, 0.25),   # sell another 25% at +50%
    # remaining 25% rides with a trailing stop — handled elsewhere
]
```

Why original-position fractions? Because remaining-size fractions compound: "sell 33% of
what's left at each level" means you keep shrinking the base and the math is hard to
reason about. Original-size fractions are transparent and audit-friendly.

**Design consideration:** leave the final slice open (no target). That slice rides until
your trailing stop or max-hold rule fires. A ladder that takes 100% of the position into
fixed targets eliminates upside on your best winners.

---

## Step 2 — Anchor the cost basis at entry; never update it on partial sells

The cost basis is the entry price multiplied by the original share count. Partial sells do
**not** change the cost basis — the cost basis represents what you paid for the entire
position. Gain percentage is always:

```
gain_pct = (current_price - entry_price) / entry_price
```

The most common ladder bug is recomputing cost basis after each partial sell. After
selling 25% at +15%, a naive system recalculates the "new cost basis" using the 15% sale
proceeds. This inflates the apparent cost of remaining shares and causes subsequent
thresholds (+30%, +50%) to fire late or not at all. Lock cost basis to entry and never
touch it.

---

## Step 3 — Track fired levels in persistent state

Each level needs a boolean `fired` flag stored alongside the position. This is the state
the ladder depends on. If it lives only in memory, a crash or scheduled-restart will
re-fire every level the next time the price is above those thresholds.

Minimal position state:

```python
@dataclass
class Position:
    symbol: str
    entry_price: float
    original_shares: float      # never decremented — needed for tranche math
    remaining_shares: float     # decremented on each partial sell
    entry_date: str
    ladder_fired: list[bool]    # one flag per tranche, same length as LADDER
```

Persist this to disk (JSON, SQLite, or your database of choice) on every state change,
before executing the order. If the order itself fails, roll back the flag. The pattern:

```
1. Mark level as fired in memory
2. Persist state to disk
3. Submit order
4. If order fails: un-mark the flag, persist again, alert
```

Never persist after order submission — if the process crashes between submit and persist,
you will re-fire the next startup.

---

## Step 4 — Evaluate the ladder each bar

On each new price update (candle close, tick, or polling interval):

```python
def evaluate_ladder(pos: Position, current_price: float, ladder: list) -> list[dict]:
    """
    Returns a list of sell orders to place.
    Each order: {symbol, shares, reason}.
    Modifies pos.ladder_fired in place (caller must persist before submitting).
    """
    orders = []
    gain_pct = (current_price - pos.entry_price) / pos.entry_price

    for i, (threshold, fraction) in enumerate(ladder):
        if pos.ladder_fired[i]:
            continue                          # already done — skip
        if gain_pct >= threshold:
            shares_to_sell = pos.original_shares * fraction
            shares_to_sell = min(shares_to_sell, pos.remaining_shares)  # safety cap
            if shares_to_sell <= 0:
                pos.ladder_fired[i] = True    # nothing left to sell at this level
                continue
            pos.ladder_fired[i] = True
            pos.remaining_shares -= shares_to_sell
            orders.append({
                "symbol":  pos.symbol,
                "shares":  shares_to_sell,
                "reason":  f"ladder_L{i+1}_{int(threshold*100)}pct",
            })

    return orders
```

Why process all levels in one pass? A single candle can gap through multiple thresholds.
Without iterating all unfired levels each bar, a gap from +10% to +35% would miss the
+15% and +30% tranches entirely. Iterating all unfired levels in one pass ensures every
crossed threshold fires on the bar it was breached, even if the price skipped it.

---

## Step 5 — Handle the gap-through case gracefully

When a bar opens above a threshold it never traded through (e.g., overnight earnings
gap), the fill price will be the open, not the threshold price. This is expected behavior.
Do not attempt to reconstruct an "as if" price — use the actual fill. Log the gap for
review, but do not treat it as an error.

---

## Step 6 — Guard against stale cost basis on position reload

If your system loads positions from storage at startup, verify that `entry_price` is
the **original** entry price, not a weighted-average price recalculated from partial-fill
history. If your broker or data store reports a "current average cost" that reflects
partial sells, do not use that number. Store `entry_price` as an immutable field
recorded at first entry.

A concrete danger: some brokers update "average cost" to the sale price after a partial
exit, making remaining shares look as if they were bought at the exit price. If your
gain-pct calculation reads from the broker's average-cost field, subsequent ladder levels
will be computed relative to the wrong base and will never fire correctly.

---

## Worked micro-example — before and after

**Setup:** You buy 100 shares at $50. Ladder: +15% → sell 25%, +30% → sell 25%, +50% →
sell 25%.

**Stale-cost-basis version (broken):**

```python
# WRONG — recalculates cost basis after each sell
pos.avg_cost = (pos.remaining_shares * pos.avg_cost + proceeds) / pos.remaining_shares
# After selling 25 shares at $57.50 (+15%), avg_cost is now ~$47 — WRONG
# The +30% threshold is now relative to $47, so it fires at $61 instead of $65
```

**Immutable-entry-price version (correct):**

```python
# RIGHT — entry_price never changes
gain_pct = (current_price - pos.entry_price) / pos.entry_price
# entry_price stays $50 throughout the position's life
# +30% threshold fires at $65 as designed
```

The broken version under-collects at early levels and over-collects at later levels —
not dramatically wrong, but consistently wrong in a way that is hard to notice until you
audit it against your intended ladder design.

---

## Report / output format

When asked to design or audit a profit-taking ladder, produce:

```
# Profit-Ladder Design: <strategy or position name>

## Ladder Definition
| Level | Gain Threshold | Fraction (of original) | Shares (example) | Trigger Price (example) |
|-------|---------------|----------------------|-----------------|------------------------|
| L1    | +15%          | 25%                  | 25              | $57.50                 |
...

## State Integrity Check
- Cost basis source: [entry_price field / broker avg_cost / other — flag if stale risk]
- Fired-flag persistence: [yes/no/where stored]
- Crash-recovery path: [tested/untested/not present]
- Gap-through handling: [all levels evaluated per bar / only next level / other]

## Findings / Issues
<For each issue: what it is, where in the code, and the fix.>

## Open Slice
<What happens to the remaining position after the final ladder level fires.>
```

---

## Connection to other skills

- Pair with **stop-loss-designer** to define what happens to the open slice — the
  trailing stop on the remainder is the other half of a complete exit policy.
- Pair with **kelly-sizing** to size the original position; the ladder fractions then
  produce sensible dollar amounts per tranche.
- Pair with **backtest-harness** to simulate the ladder in walk-forward mode and measure
  its effect on average winner size versus a single-exit strategy.

---

## Crypto notes

The same ladder logic applies to crypto: persistent state is even more important because
crypto systems often restart frequently, and 24/7 markets mean gap-through events are
common (especially around macro events or exchange-specific liquidation cascades). Use
the same immutable `entry_price` anchor and per-level `fired` flags. Note that crypto
positions are often fractional; ensure your share-math uses float arithmetic throughout
and that minimum-order-size constraints from the exchange are enforced before submitting
a tranche sell.

---

## What this skill does not cover

- Which specific gain thresholds or fractions are "correct" — those are strategy
  parameters you tune to your own edge. Backtests don't predict the future; a ladder that
  worked well historically may behave differently in live markets.
- Execution mechanics (limit vs. market orders, slippage, partial fills from the broker).
  See the **execution-realism** skill for that layer.
- Tax-lot accounting — in taxable accounts, partial sells have tax implications. The
  logic here is economically correct but tax-agnostic.

For the full tranche-state machine reference with edge cases — crash recovery patterns,
position reload guards, and multi-asset state serialization — see
`references/tranche-state-machine.md`.


<!-- strongskills-brand -->

---

*Made with a StrongSkills tool — The shortcut to the cutting edge · getstrongskills.com*
