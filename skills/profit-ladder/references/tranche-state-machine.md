# Tranche State Machine — Reference

Detailed mechanics for the profit-taking ladder. Read this when you need to implement
crash recovery, reload guards, multi-asset state, or audit an existing implementation
for correctness.

---

## State fields — complete definition

```python
@dataclass
class LadderPosition:
    # Identity
    symbol: str
    trade_id: str               # stable UUID generated at entry

    # Entry anchor — IMMUTABLE after creation
    entry_price: float
    entry_date: str             # ISO-8601, UTC
    original_shares: float      # never modified

    # Live state — mutable
    remaining_shares: float
    ladder_fired: list[bool]    # len == len(LADDER), all False at entry
    peak_price: float           # for trailing stop on the open slice

    # Audit trail
    tranches: list[dict]        # one entry per fired tranche (see below)
```

Each fired tranche records:

```python
{
    "level":          1,           # 1-indexed
    "threshold_pct":  15.0,
    "fired_at_price": 57.50,
    "fired_at_date":  "2025-03-14",
    "shares_sold":    25.0,
    "order_id":       "abc123",    # filled in after broker confirms
    "status":         "confirmed", # "pending" | "confirmed" | "failed"
}
```

Keeping the full tranche log (not just `ladder_fired` booleans) lets you audit exactly
what happened at every level, reconcile with broker statements, and replay decisions
without re-running market data.

---

## Crash-recovery protocol

The safe order of operations on every tranche fire:

```
1. Set ladder_fired[i] = True in memory
2. Append a "pending" tranche record to pos.tranches
3. Flush pos to persistent storage (atomic write or transaction commit)
4. Submit sell order to broker
5a. On success: update tranche record to "confirmed", set order_id, flush again
5b. On failure: set ladder_fired[i] = False, update tranche to "failed", flush again,
    alert operator
```

On startup, load all positions and check for any tranche in status "pending". A pending
tranche means the process crashed between the flush (step 3) and the order result (step
5). Treat it as uncertain: query the broker for the order, then reconcile.

Never re-fire a level that is already `True` in `ladder_fired`, even if the tranche
record shows "failed". A failed order should trigger an alert and human review, not
automatic retry, because the failure reason matters (insufficient funds, market closed,
symbol halted, etc.).

---

## Position reload guard

When loading positions from storage or from a broker API at startup:

```python
def load_position_safe(raw: dict) -> LadderPosition:
    """
    Construct a LadderPosition from stored data.
    Validates that entry_price is the original entry, not a broker-recalculated average.
    """
    entry_price = raw["entry_price"]     # must come from YOUR storage, not broker API
    # DANGER: broker APIs often expose "averageCost" which is recalculated after partial
    # sells. Never substitute averageCost for entry_price here.
    # If raw["entry_price"] is missing or zero, raise — do not silently fall back.
    if not entry_price or entry_price <= 0:
        raise ValueError(f"Invalid entry_price for {raw['symbol']}: {entry_price!r}. "
                         "Do not load position without a valid immutable entry price.")
    return LadderPosition(**raw)
```

---

## Multi-asset state serialization

For systems tracking many simultaneous positions, store state as a dict keyed by
`trade_id` (not symbol — you may re-enter the same symbol multiple times):

```python
# state.json schema
{
  "positions": {
    "<trade_id>": { ...LadderPosition fields... },
    ...
  },
  "last_saved": "2025-03-14T18:30:00Z"
}
```

Use atomic writes: write to a `.tmp` file and rename it over the real file. On most
filesystems (including macOS HFS+/APFS and Linux ext4), a rename within the same
directory is atomic, so a crash mid-write never corrupts the previous good state.

```python
import json, os, tempfile, pathlib

def persist_state(state: dict, path: pathlib.Path) -> None:
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w") as f:
        json.dump(state, f, indent=2)
    os.replace(tmp, path)   # atomic on POSIX
```

---

## Fraction math edge cases

**Shares-sold rounding.** Brokers require integer or fixed-decimal share quantities.
Round down the computed fraction to avoid trying to sell more than you hold:

```python
import math
shares_to_sell = math.floor(pos.original_shares * fraction * 100) / 100  # 2 decimal places
```

**Remaining-shares underflow.** After several tranches, floating-point accumulation can
cause `remaining_shares` to differ from the broker's record by a tiny epsilon. Add a
guard before the final tranche:

```python
if i == len(LADDER) - 1:
    shares_to_sell = pos.remaining_shares   # sell exactly what is left, broker-reconciled
```

**Zero-remaining early exit.** If remaining_shares reaches zero before all levels fire
(e.g., because an earlier level over-sold due to a manual trade), mark all remaining
levels fired and close the position record.

---

## Gap-through detection and logging

```python
def detect_gap_through(prev_close: float, current_price: float,
                       threshold: float, entry_price: float) -> bool:
    """True if the price gapped through the threshold without trading at it."""
    prev_gain = (prev_close - entry_price) / entry_price
    curr_gain = (current_price - entry_price) / entry_price
    return prev_gain < threshold <= curr_gain and current_price > prev_close * 1.01
    # 1% gap filter avoids false positives on normal intraday moves
```

Log gap-throughs but do not treat them as errors. The fill at the open is the correct
economic outcome; the threshold was crossed, the tranche fires, the fill happens at
market price. The log entry is useful for post-trade analysis of slippage by level.

---

## Checklist — auditing an existing ladder implementation

- [ ] `entry_price` is stored at first fill and never overwritten
- [ ] Gain-pct formula uses `entry_price`, not broker's average-cost or current basis
- [ ] `original_shares` is stored at entry and never decremented
- [ ] Each tranche has a fired flag persisted to disk before order submission
- [ ] On startup, fired flags are reloaded and unfired levels are not re-fired
- [ ] All unfired levels are evaluated in a single pass per bar (gap-through safety)
- [ ] `remaining_shares` is capped to prevent negative sells
- [ ] State is written atomically (temp-file rename or DB transaction)
- [ ] Failed orders do not auto-retry; they alert and halt that position's ladder
- [ ] Open slice (post-last-tranche) is handled by a separate trailing-stop rule
