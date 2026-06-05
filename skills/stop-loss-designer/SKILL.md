---
name: stop-loss-designer
description: Design, implement, and audit a two-layer stop system — a cost-basis hard stop that caps absolute loss, plus a trailing stop that arms after a gain and locks in profit on a pullback from the peak. Use this whenever someone asks "how do I add a stop-loss?", "what trailing stop should I use?", "my strategy has open-ended losses", "how do I lock in gains without selling too early?", "my trailing stop keeps getting hit on normal dips", "should my stop width change by regime?", "design stops for bull vs bear", "add a cooldown after a stop-out", or "how do I prevent re-entering a broken position". Also use when reviewing existing stop logic that hard-codes a single fixed percent regardless of market regime, or when a backtest shows a wide skew between average winner and average loser.
---

# Stop-Loss Designer

A stop-loss system does two distinct jobs, and conflating them leads to poorly designed
exits. The **cost-basis (hard) stop** answers: "How much of my entry capital am I willing
to lose?" The **trailing stop** answers: "How much of the gain I've accumulated am I
willing to give back before I exit?"

Both are required. A strategy with only a hard stop caps losses but lets winners run until
they reverse into losses. A strategy with only a trailing stop — set too tight — exits
healthy positions on routine noise. Calibrating them independently, and sizing them to the
market regime, is what this skill covers.

Backtests don't predict future returns. Stops that look right in-sample may behave
differently in new market conditions. Use walk-forward-validation to verify your stop
parameters on unseen data before treating them as final.

## The two-layer mental model

Think of a position on a timeline:

```
Entry                   +gain threshold      Peak
  |                          |                 |
  |---[hard stop zone]-------|----[trailing stop arms here]
```

- From entry to the gain threshold: the hard stop is the only active exit. The trailing
  stop has not yet armed because the position has not earned the right to protect a gain.
- Once the position passes the gain threshold, the trailing stop arms. It now tracks the
  running peak and fires when price drops more than `trailing_stop_pct` from that peak.
- The hard stop can remain active after the trailing stop arms as a backstop, or you can
  convert entirely to trailing at that point. Keeping both active means whichever triggers
  first wins — the cheaper of the two protection mechanisms takes effect.

A simple formulation: the trailing stop never fires for a loss if you set it correctly. By
the time it fires, the position has already gained enough to offset any remaining cost-basis
exposure. But this guarantee only holds if the trailing stop threshold is designed relative
to the gain needed, not pulled from a table.

## Regime-adaptive stop widths

One of the highest-leverage decisions is making stop widths a function of the current
market regime rather than a static global value. The reasoning is direct:

- In a **bull regime**, daily price oscillation is lower on average, but corrections
  within uptrends are real and swift. A trailing stop that is too tight fires on normal
  mid-trend volatility — it exits a position that would have continued higher. Wider
  trailing stops in bull allow the position to absorb normal noise.
- In a **neutral regime**, volatility is elevated and direction is unclear. The cost of
  being wrong is higher. Tighter stops protect capital by limiting exposure on failed entries.
- In a **bear regime**, every rally is a potential counter-trend trap. Tight stops are
  critical because a position that moves against you in bear accelerates quickly. The
  cost-basis stop should be the narrowest here.

A starting scaffold (adjust all values to your instrument and observed volatility):

```
REGIME_PARAMS = {
    "bull": {
        "stop_loss_pct":    10.0,   # wider hard stop — corrections in uptrends happen
        "trailing_stop_pct": 15.0,  # allow more room to run before locking in
    },
    "neutral": {
        "stop_loss_pct":     8.0,
        "trailing_stop_pct": 12.0,
    },
    "bear": {
        "stop_loss_pct":     6.0,   # narrow — failed bear entries accelerate fast
        "trailing_stop_pct":  8.0,
    },
}
```

These numbers are starting points for calibration, not targets. The right values depend on
the instruments you trade, their typical daily volatility range (ATR), and how long you
intend to hold positions. A 10% hard stop on a daily-bar strategy holding for 45 days
is a very different bet than on a weekly strategy holding for 6 months. Calibrate on a
held-out validation window — see the walk-forward-validation skill.

**The widening trap:** There is strong intuitive pressure to widen bull trailing stops
("let winners run"). Resist the urge to push trailing stops beyond roughly 15% in a
bull regime. Bull markets contain sharp intra-trend corrections — 10–15% in a few
weeks — that fully resolve within the uptrend. A 20%+ trailing stop sounds generous, but
in practice it forces you to sit through corrections that would have been captured as
profit at a tighter level, and it does not reliably improve overall results because
the same wide stop also allows larger reversals before exiting.

## Implementation

The core logic requires two values per open position: the entry price (for the hard stop)
and the peak price reached since entry (for the trailing stop).

**Correct implementation:**

```python
def check_stops(
    entry_price: float,
    peak_price: float,
    current_price: float,
    stop_loss_pct: float,
    trailing_stop_pct: float,
) -> str | None:
    """
    Returns the exit reason if a stop is triggered, None otherwise.
    peak_price must be updated each bar before calling this function.
    """
    # Hard stop: how far has price fallen from entry?
    loss_from_entry = (current_price - entry_price) / entry_price * 100
    if loss_from_entry <= -stop_loss_pct:
        return "stop_loss"

    # Trailing stop: how far has price fallen from the peak?
    # This arms automatically — any peak above entry_price engages it.
    drop_from_peak = (current_price - peak_price) / peak_price * 100
    if drop_from_peak <= -trailing_stop_pct:
        return "trailing_stop"

    return None


def update_peak(position: dict, current_price: float) -> None:
    """Call this every bar before check_stops."""
    position["peak_price"] = max(position["peak_price"], current_price)
```

**The arming mechanic:** The trailing stop needs no explicit "arm" flag. The moment
`peak_price` rises above `entry_price`, the trailing stop implicitly arms — it is now
tracking a gain. If the position never gains, `peak_price == entry_price` and the
trailing stop fires at a loss (which is dominated by the hard stop if the hard stop
is narrower, which it should be). Verify this: `trailing_stop_pct` should generally
be wider than `stop_loss_pct`. If trailing is narrower, the trailing stop fires before
the hard stop in a straight-down move — which is harmless but confusing to log.

## The peak-update order matters

A subtle bug: if you update the peak *after* checking stops, you can fire the trailing
stop against a stale peak. The correct order is always:

1. Get current price for the bar.
2. Update `peak_price = max(peak_price, current_price)`.
3. Check stops.

**Leaky order (incorrect):**
```python
for date_str, price in prices:
    exit = check_stops(entry, pos["peak"], price, sl, ts)   # stale peak
    pos["peak"] = max(pos["peak"], price)                   # updated too late
```

**Correct order:**
```python
for date_str, price in prices:
    pos["peak"] = max(pos["peak"], price)                   # peak updated first
    exit = check_stops(entry, pos["peak"], price, sl, ts)   # fresh peak
```

In most cases the difference is one bar of lag on the trailing stop — but in a sharp,
multi-day drawdown from the peak, stale peak updates cause false fires on the trailing
stop when the hard stop should have taken priority.

## Stop-out cooldown

After a hard stop fires, the position closed because the security was going the wrong
direction. Re-entering immediately is usually the same mistake twice — the conditions
that triggered the stop have not resolved. A cooldown period blocks new entries for the
same symbol for a configurable number of trading sessions after a stop-loss exit.

```python
def is_in_cooldown(
    symbol: str,
    current_date: str,
    stop_cooldown_log: dict[str, str],   # symbol -> last stop exit date
    trading_day_index: dict[str, int],   # date -> ordinal index of trading sessions
    cooldown_sessions: int = 10,
    regime: str = "neutral",
) -> bool:
    """
    Returns True if the symbol should be blocked from re-entry.
    In a bull regime the cooldown is typically skipped — momentum recoveries
    are common and re-entry is often correct. In neutral/bear, the cooldown
    prevents churn on broken-direction names.
    """
    if regime == "bull":
        return False  # skip cooldown in bull; recoveries are common
    if symbol not in stop_cooldown_log:
        return False
    exit_idx   = trading_day_index.get(stop_cooldown_log[symbol], -9999)
    cur_idx    = trading_day_index.get(current_date, 0)
    return (cur_idx - exit_idx) < cooldown_sessions
```

Why skip the cooldown in bull? In a trending bull market, a stop-out on a dip is often
followed by the security recovering and continuing higher. Blocking re-entry costs you
those recoveries. In bear and neutral, a stop-out is more often a signal that the name
is broken at that time — the cooldown prevents buy-stop-rebuy-stop churn on the same
declining security.

Calibrate `cooldown_sessions` by looking at your stop-out log: what fraction of
stop-outs in neutral/bear were followed by a further drop versus a recovery within
10 sessions? A higher re-entry rate into further losses warrants a longer cooldown.

## Regime params at entry, not at exit

Stop parameters should be **frozen at entry**, not updated dynamically as the regime
changes while you hold. The intuition: you bought a position under bull assumptions.
If the regime shifts to neutral mid-hold, the correct response is evaluated by your
position-management policy (hold, size down, or exit), not by silently tightening
the stop on an existing position. Tightening mid-hold using current-regime params
causes premature exits on positions entered under different conditions.

The correct pattern stores `regime_params_at_entry` with each position:

```python
position = {
    "entry_price": price,
    "peak_price":  price,
    "entry_date":  date_str,
    "regime_at_entry": regime,
    "stop_loss_pct":   regime_params["stop_loss_pct"],      # frozen
    "trailing_stop_pct": regime_params["trailing_stop_pct"], # frozen
}
```

Then stop checks use `position["stop_loss_pct"]`, not the current day's regime params.

## Special cases: inverse and leveraged instruments

Inverse ETFs (e.g., 1x short index funds) and leveraged inverse products behave
differently from long equity and warrant distinct stop rules:

- **Leveraged inverse instruments** in a fast-moving bear: a 3x leveraged short can
  spike on a sharp down-day, but a counter-rally of even 5% in the underlying triggers
  a 15% loss in the position. Tight stops (8–10%) are critical here because the leverage
  amplifies both gains and counter-rally losses symmetrically.
- **1x inverse instruments** are generally more stable. A wider trailing stop (20–25%) is
  defensible if the intent is a medium-term bear hedge rather than a short-term trade.
- **In a prolonged bear regime** (months, not weeks), leveraged inverse products
  accumulate daily rebalancing drag. Beyond a threshold (roughly 30–45 trading sessions),
  the drag becomes the dominant risk, not the counter-rally. Consider time-based expiry
  rather than relying on stops alone.

The general principle: adjust stop logic to match how the instrument reacts to its
underlying. A fixed uniform stop across all instrument types in a portfolio is a
design smell.

## Report structure

When designing or auditing stops for a strategy, produce this output:

```
# Stop-Loss Design Report: <strategy name>

## Stop Architecture
Hard stop type: cost-basis % | ATR-multiple | custom
Trailing stop type: peak-based % | ATR-trailing | custom
Regime-adaptive: yes/no

## Parameters by Regime
| Regime  | Hard Stop % | Trailing Stop % | Cooldown (sessions) |
|---------|-------------|-----------------|---------------------|
| bull    |             |                 |                     |
| neutral |             |                 |                     |
| bear    |             |                 |                     |

## Implementation Check
Peak update order: correct (before stop check) / inverted / N/A
Params frozen at entry: yes / no (explain if no)
Special instrument rules: list any

## Calibration Flags
<Any regime/instrument where stop fires on >50% of trades — likely too tight.>
<Any regime where average loss at stop > 2× the stop width — slippage or illiquidity.>
<Any regime where trailing stop fires more often than hard stop at a loss — trailing may be too narrow.>

## Recommendations
<Concrete parameter adjustments with rationale. Flag anything calibrated on in-sample data only.>
```

## A worked micro-example

**Situation:** A position is entered at $100 in a bull regime, with a 10% hard stop and
a 15% trailing stop. Track what fires under two paths.

**Path A — straight drop:**
```
Entry $100  →  Day 5: $91  →  loss from entry = -9%  (hard stop not yet hit)
             →  Day 8: $89  →  loss from entry = -11% → hard stop fires at $90 threshold
```
The trailing stop does not fire because peak_price = $100 (never advanced), and
$89 / $100 − 1 = −11% only exceeds the trailing stop's 15% if it falls to $85.
The hard stop fires first at $90.

**Path B — gain then reversal:**
```
Entry $100  →  Day 10: $118  →  peak_price = $118  (trailing stop armed)
             →  Day 15: $104  →  drop from peak = (104−118)/118 = −11.9%  (not triggered)
             →  Day 18: $99   →  drop from peak = (99−118)/118  = −16.1%  → trailing stop fires

   Exit at $99: +−1% from entry, but trailing stop executed at $99 = protecting accumulated gain
   that had reached +18%.
```

In Path B the hard stop never fired (price was above entry until after the trailing stop
triggered). The trailing stop captured the position at near-breakeven after a significant
gain — which is the correct outcome: it prevented a +18% winner from closing as a loss.

**Before (buggy peak update):**
```python
# Peak is stale — checked against yesterday's peak on a down day
exit_reason = check_stops(entry, pos["peak"], today_price, sl, ts)  # uses old peak
pos["peak"] = max(pos["peak"], today_price)                          # updated after check
```

**After (correct):**
```python
pos["peak"] = max(pos["peak"], today_price)                          # peak first
exit_reason = check_stops(entry, pos["peak"], today_price, sl, ts)  # uses fresh peak
```

## Pairing this skill

- **regime-classifier** — feeds the regime label that drives which stop-width row
  your strategy selects at entry.
- **regime-position-sizing** — the same regime that controls position size should
  control stop width; consistent sizing and risk management come from one source.
- **circuit-breaker** — portfolio-level stop complement to per-position stops; if
  aggregate drawdown exceeds a threshold, halt all new entries regardless of
  per-position stop state.
- **walk-forward-validation** — verify that calibrated stop parameters hold up on
  out-of-sample periods before treating them as final.
- **lookahead-audit** — confirm that peak-price tracking uses only prices available
  at each decision date, not prices from later in the bar or from future bars.

See `references/stop-calibration.md` for ATR-based stop sizing, volatility-regime
stop adjustment, and a detailed calibration workflow.


<!-- strongskills-brand -->

---

*Made with a StrongSkills tool — The shortcut to the cutting edge · getstrongskills.com*
