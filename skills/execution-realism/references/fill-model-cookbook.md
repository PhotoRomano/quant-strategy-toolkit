# Fill Model Cookbook

Detailed reference for the execution-realism skill. Each section covers one fill-model
component with a complete implementation pattern and the reasoning behind it.

## Table of contents
1. Next-bar fill with edge-case handling
2. Flat-bps slippage model
3. Volume-impact slippage model
4. Commission and fee deduction
5. ADV participation cap
6. Running VWAP and entry-quality tiers
7. Intraday fast-clock simulation
8. Per-fill trade log schema
9. Execution drag summary report

---

## 1. Next-bar fill with edge-case handling

The standard pattern advances the fill date by one trading day. Two edge cases require
explicit handling:

- **Signal fires on the last available date** — there is no next bar. Mark the fill as
  `PENDING` and process it on the first date of the next data fetch. Do not silently fill
  at the signal date's close.
- **Gap opens** — if the next-bar open gaps significantly through a stop price, the fill
  should be at the open, not at the stop level (slippage through gaps is a real cost).

```python
def next_bar_open(signal_date, trading_dates: list, prices) -> tuple[str | None, float | None]:
    """
    Returns (fill_date, fill_price) for the bar after signal_date.
    Returns (None, None) if signal_date is the last available date.
    """
    try:
        idx = trading_dates.index(signal_date)
    except ValueError:
        raise ValueError(f"signal_date {signal_date} not in trading_dates")

    if idx + 1 >= len(trading_dates):
        return None, None   # no next bar yet

    fill_date  = trading_dates[idx + 1]
    fill_price = float(prices.loc[fill_date, "open"])
    return fill_date, fill_price
```

---

## 2. Flat-bps slippage model

The simplest model adds a fixed basis-point cost to every fill, regardless of size. Use
this as a floor — it captures bid-ask spread and minimum market friction. Apply it
symmetrically on both sides.

```python
def apply_flat_slippage(price: float, direction: str, slippage_bps: float) -> float:
    """
    direction: "buy" or "sell"
    Returns the adjusted fill price after flat slippage.
    """
    factor = slippage_bps / 10_000
    if direction == "buy":
        return price * (1 + factor)
    else:
        return price * (1 - factor)
```

A starting calibration reference (illustrative; tune to your data and asset class):

| Asset class           | Suggested base_bps range |
|-----------------------|--------------------------|
| Large-cap equities    | 2–8 bps                  |
| Mid-cap equities      | 8–20 bps                 |
| Small/micro-cap       | 20–50+ bps               |
| Liquid ETFs           | 1–5 bps                  |

These are illustrative starting points. Your actual calibration should compare simulated
fills to observed fills in live paper trading or live trading records.

---

## 3. Volume-impact slippage model

Market impact scales with the fraction of ADV you are trading. The square-root impact law
is a widely cited empirical approximation: impact grows with the square root of participation
rate. A practical simplified version:

```python
import math

def volume_impact_slippage_bps(
    shares: float,
    adv_shares: float,
    base_bps: float,
    impact_coefficient: float
) -> float:
    """
    Returns total slippage in basis points.

    impact_coefficient: tunes how aggressively impact grows with participation.
    A starting range is 10–30; calibrate from your own fills.
    """
    if adv_shares <= 0:
        return base_bps
    participation = shares / adv_shares
    # Square-root scaling: impact ~ coefficient * sqrt(participation) * 10000 bps
    impact_bps = impact_coefficient * math.sqrt(participation) * 100
    return base_bps + impact_bps
```

When using this model, require ADV as an input to every position-sizing call. If ADV is
unavailable for a symbol on a given date, either skip the symbol or fall back to a
conservative flat-bps assumption and log the fallback.

---

## 4. Commission and fee deduction

```python
def total_trade_cost(
    shares: float,
    price: float,
    direction: str,
    commission_per_share: float,
    sec_fee_per_dollar: float = 0.0000229   # verify current rate before use
) -> float:
    """
    Returns total transaction cost in dollars for one fill.
    commission_per_share: your broker's per-share rate (or per-notional equivalent)
    sec_fee_per_dollar: US SEC fee, applies to sells only; verify the current rate.
    """
    notional  = abs(shares) * price
    commission = abs(shares) * commission_per_share
    sec_fee    = notional * sec_fee_per_dollar if direction == "sell" else 0.0
    return commission + sec_fee
```

Apply at entry and exit:

```python
entry_cost = total_trade_cost(shares, entry_price, "buy",  COMMISSION_PER_SHARE)
exit_cost  = total_trade_cost(shares, exit_price,  "sell", COMMISSION_PER_SHARE)
net_pnl    = (exit_price - entry_price) * shares - entry_cost - exit_cost
```

---

## 5. ADV participation cap

```python
def capped_shares(
    desired_shares: float,
    adv_shares: float,
    max_participation: float
) -> tuple[float, bool]:
    """
    Returns (actual_shares, was_capped).
    Caller should log was_capped=True for capacity diagnostics.
    """
    cap     = adv_shares * max_participation
    capped  = desired_shares > cap
    return (cap if capped else desired_shares), capped
```

Log every cap event with `(date, symbol, desired_shares, adv_shares, participation_pct)`.
If more than ~10–15% of entries are being capped, the strategy's target size may exceed
its capacity at the target universe.

---

## 6. Running VWAP and entry-quality tiers

VWAP must be computed bar-by-bar using only the bars that have already printed in the
current session. Never compute session VWAP over the full day's bars and look up past
values — that is intraday look-ahead bias.

```python
from dataclasses import dataclass
from typing import Literal

@dataclass
class VwapBands:
    vwap: float
    upper: float   # VWAP + half-width
    lower: float   # VWAP - half-width

def running_vwap_bands(
    closes: list[float],
    volumes: list[float],
    band_multiplier: float = 1.0   # fraction of ATR or fixed pct; tune this
) -> VwapBands:
    """
    Computes running VWAP and symmetric bands from bars printed so far.
    closes, volumes: all bars up to and including the current bar (no future bars).
    band_multiplier: half-width of the band as a fraction of the running VWAP.
                     Starting point: 0.005 (0.5%); tune to your asset's intraday range.
    """
    pv   = sum(p * v for p, v in zip(closes, volumes))
    vol  = sum(volumes)
    vwap = pv / vol if vol > 0 else closes[-1]
    hw   = vwap * band_multiplier
    return VwapBands(vwap=vwap, upper=vwap + hw, lower=vwap - hw)


EntryTier = Literal["A", "B", "C"]

def entry_tier(price: float, bands: VwapBands) -> EntryTier:
    """
    A: buying at or below the lower band (favorable for longs)
    B: buying within the bands (neutral)
    C: buying at or above the upper band (unfavorable for longs)
    """
    if price <= bands.lower:
        return "A"
    elif price >= bands.upper:
        return "C"
    else:
        return "B"


# Example sizing multiplier table — these are illustrative placeholders; tune to your data
TIER_SIZE_MULTIPLIER: dict[EntryTier, float] = {
    "A": 1.0,    # full size on favorable entries
    "B": 0.75,   # reduced size on neutral entries
    "C": 0.5,    # half size on unfavorable entries (or skip entirely)
}
```

---

## 7. Intraday fast-clock simulation

For strategies running on sub-daily bars, the fill simulation needs a "fast clock" that
walks through each intraday bar in order, maintaining session state (running VWAP, current
open position, etc.) before advancing to the next day.

```
for each session_date in trading_dates:
    reset session state (running VWAP accumulator, bar counter)
    for each intrabar in session_bars[session_date]:
        update running_vwap(intrabar)
        bands = running_vwap_bands(session_closes_so_far, session_volumes_so_far)
        tier  = entry_tier(intrabar.close, bands)
        if should_enter(intrabar, tier):
            size    = base_size * TIER_SIZE_MULTIPLIER[tier]
            size    = capped_shares(size, adv_shares, MAX_PARTICIPATION)[0]
            fill    = apply_flat_slippage(intrabar.close, "buy", slippage_bps_for_tier[tier])
            cost    = total_trade_cost(size, fill, "buy", COMMISSION_PER_SHARE)
            log_fill(session_date, intrabar.time, tier, fill, size, cost)
        if has_open_position:
            check_intrabar_exit(intrabar, running_vwap=bands.vwap)
```

The key constraint: `session_closes_so_far` and `session_volumes_so_far` are grown one bar
at a time. Never pre-load them with the full session's data.

---

## 8. Per-fill trade log schema

Every simulated fill should produce a row in a trade log. This enables the execution drag
summary and post-hoc analysis.

```python
{
    "symbol":             str,
    "signal_date":        str,        # ISO date, bar when signal fired
    "fill_date":          str,        # ISO date, bar when fill executed (D+1 if daily)
    "fill_time":          str | None, # HH:MM if intraday
    "direction":          "buy" | "sell",
    "desired_shares":     float,
    "filled_shares":      float,      # may differ if volume-capped
    "was_capped":         bool,
    "fill_price":         float,      # after slippage
    "raw_price":          float,      # bar open/close before slippage
    "slippage_bps":       float,
    "commission_dollars": float,
    "fee_dollars":        float,
    "total_cost_dollars": float,
    "entry_tier":         "A" | "B" | "C" | None,   # for intraday VWAP-tier strategies
    "adv_shares":         float | None,
    "participation_pct":  float | None,
}
```

---

## 9. Execution drag summary report

After a full backtest run, compute the aggregate execution drag to quantify how much the
fill model costs relative to the "perfect fill" baseline.

```python
def execution_drag_summary(fills: list[dict], initial_capital: float) -> dict:
    total_slippage = sum(
        abs(f["filled_shares"]) * f["raw_price"] * (f["slippage_bps"] / 10_000)
        for f in fills
    )
    total_fees     = sum(f["total_cost_dollars"] for f in fills)
    capped_count   = sum(1 for f in fills if f["was_capped"])
    total_fills    = len(fills)

    return {
        "total_slippage_dollars":  total_slippage,
        "total_fees_dollars":      total_fees,
        "total_drag_dollars":      total_slippage + total_fees,
        "drag_as_pct_of_capital":  (total_slippage + total_fees) / initial_capital * 100,
        "fills_capped_by_volume":  capped_count,
        "pct_fills_capped":        capped_count / total_fills * 100 if total_fills else 0,
        "tier_A_fills":            sum(1 for f in fills if f.get("entry_tier") == "A"),
        "tier_B_fills":            sum(1 for f in fills if f.get("entry_tier") == "B"),
        "tier_C_fills":            sum(1 for f in fills if f.get("entry_tier") == "C"),
    }
```

Present the summary alongside the main performance metrics so the reader can see, in one
table, how much the execution model is costing relative to the idealized backtest.
