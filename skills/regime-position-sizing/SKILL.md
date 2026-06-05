---
name: regime-position-sizing
description: Design or audit a regime-adaptive position sizing system that maps each market regime (bull / neutral / bear) to its own position-count cap, per-position size limit, hold period, and stop widths — then applies a pipeline-level account cap as the final gate. Use this whenever someone asks "how big should my positions be in a bear market?", "why does my backtest blow up in downtrends?", "how do I size positions differently by regime?", "what's the right number of positions to hold?", "my stop losses keep getting triggered", "how do I wire regime to sizing?", "should I reduce concentration when the market is choppy?", "why does my strategy over-concentrate in bull mode?", or any question about connecting a regime label to concrete sizing rules. Also use after the regime-classifier skill produces regime labels and before wiring those labels into a live execution pipeline.
---

# Regime-Adaptive Position Sizing

A regime classifier produces a label — bull, neutral, or bear. That label is only
useful if it changes *concrete, measurable behavior*: how many positions you hold,
how large each one is, how long you hold it, and how much loss you will absorb
before exiting. Regime-adaptive sizing is the translation layer between a market
signal and a risk-controlled position.

This skill teaches the framework, the parameter structure, the sizing pipeline
with its two-cap hierarchy, and the tradeoffs that arise when you tune the values.
No specific numbers here are "correct" — they are starting points you will
calibrate against your own strategy and risk tolerance. Backtests do not predict
future performance.

## Why regime-gated sizing matters

The core problem with a single, fixed position size is that it applies the same
risk budget to very different environments:

- In a **bull** trend, wide stops are justified — momentum stocks pull back and
  recover; a tight stop exits before the real move unfolds. Concentration in a
  few high-conviction names lets winners compound.
- In a **neutral / choppy** market, wide stops become open-ended losses. Entries
  that look like breakouts reverse. More positions at smaller size means no single
  whipsaw is fatal.
- In a **bear** trend, every dollar at risk faces an adverse macro headwind. The
  surviving edge is selectivity and tiny position size, not diversification across
  names that all fall together.

A single parameter set cannot satisfy all three environments. The regime-adaptive
approach solves this by maintaining a separate parameter block per regime and
switching the active block on each decision date.

## The parameter block

For each regime, define at minimum:

| Parameter | What it controls |
|---|---|
| `max_position_pct` | Maximum share of portfolio equity for a single position |
| `max_positions` | Hard cap on concurrent open positions |
| `hold_days` | Maximum calendar days before a position is forcibly closed |
| `stop_loss_pct` | Fixed stop: exit if entry-price-to-current drops beyond this |
| `trailing_stop_pct` | Trailing stop measured from the position's peak price |

A starting-point illustration (values are illustrative — tune to your strategy):

```python
REGIME_PARAMS = {
    "bull": {
        "max_position_pct": 30.0,   # room for concentration; momentum needs space
        "max_positions": 4,          # fewer, larger; conviction over diversification
        "hold_days": 60,             # trending names need time to develop
        "stop_loss_pct": 10.0,       # wide — pullbacks in uptrends are normal
        "trailing_stop_pct": 15.0,   # protect accumulated gains without killing the ride
    },
    "neutral": {
        "max_position_pct": 20.0,   # smaller; choppy markets punish concentration
        "max_positions": 5,          # more slots, each sized down
        "hold_days": 45,             # rotate faster; trends don't develop as far
        "stop_loss_pct": 8.0,
        "trailing_stop_pct": 12.0,
    },
    "bear": {
        "max_position_pct": 15.0,   # minimal; adverse macro headwind on every long
        "max_positions": 2,          # extreme selectivity — only highest-conviction
        "hold_days": 30,             # shorter windows reduce drawdown exposure
        "stop_loss_pct": 6.0,        # tight — preserve capital above all else
        "trailing_stop_pct": 8.0,
    },
}
```

The ratio between regimes matters more than the absolute values. Bear should be
meaningfully tighter than neutral, which should be meaningfully tighter than bull.
A common mistake is setting them all close together, which defeats the purpose.

## The two-cap hierarchy

Position size is always the minimum of two independent limits:

```
effective_budget = min(regime_position_budget, account_max_budget)
```

The **regime cap** (`max_position_pct × portfolio_value`) is set per-regime as
described above. It scales with the portfolio, so it automatically adjusts as
equity grows or shrinks.

The **account cap** (`account_max_position_pct × portfolio_value`) is a second,
strategy-level ceiling. It prevents a regime change from accidentally producing
positions that exceed an absolute concentration limit you have set at the account
level — for example, if a broker-mandated rule or personal risk budget caps any
single name at 25% of equity regardless of regime.

In practice:
- In bull mode, the regime cap is the binding constraint (if bull `max_position_pct`
  is 30% and account max is 25%, the account max wins).
- In bear mode, the regime cap is almost always tighter than the account max.

Implement it as a final clamp on computed budget, not as a conditional:

```python
account_max = portfolio_value * ACCOUNT_MAX_POSITION_PCT / 100.0
regime_max  = portfolio_value * regime_params["max_position_pct"] / 100.0
budget = min(score_adjusted_budget, regime_max, account_max, available_cash)
```

## Conviction scaling within a regime

The regime cap is a ceiling, not a flat rule. Within that ceiling, you can
scale position size by a conviction score — the signal strength for a given entry.
A simple approach:

```python
# conviction ranges 0–1 based on a normalized score
conviction = max(0.0, min(1.0, (score - base_threshold) / score_range))

# scale between 70% and 100% of the regime's max
position_pct = regime_params["max_position_pct"] * (0.70 + 0.30 * conviction)
```

This avoids two failure modes: always entering at max size (which wastes the
regime signal's precision) and always entering at minimum size (which wastes
conviction information). The 70/100 band is illustrative — your strategy may
prefer a tighter or wider range.

## Stop widths and the regime interaction

Stop widths are regime-dependent for the same reason as sizing: what constitutes
a "normal pullback" differs between environments.

- Bull markets tolerate deeper intraday and multi-day pullbacks before resuming.
  A 10% stop that fires in a flat market would be triggered four times a year by
  normal volatility in a trending market.
- Bear markets have a different problem: you need to be right fast. A 6% stop in
  bear mode keeps the loss capped tightly on entries that turn against you, but
  it also means bear-mode entries must be high-conviction (hence the tighter
  `score_threshold_delta` or tighter score gate).

The trailing stop and fixed stop serve different functions:
- The **fixed stop** (from entry price) caps the maximum loss on any single
  position. Set it based on the maximum dollar loss you can accept per trade.
- The **trailing stop** (from peak price) locks in gains once a position moves in
  your favor. In a trending regime, the trailing stop is usually the binding exit
  for winning trades, while the fixed stop catches the losers early.

In bear mode, tightening both is the right discipline. In bull mode, widening the
trailing stop gives momentum positions room to run — but widening it too far
means you give back a large portion of gains on every exit. The tradeoff is
explicit: a 15% trailing stop will exit later and capture more of a sustained run,
but will also give back more on a reversal.

## Hold-period expiry: the third exit

Stop-loss and trailing-stop are price-based exits. `hold_days` is a time-based
exit. All three are needed.

The hold-period exit prevents stale positions from tying up capital in names that
never developed a trend. Without it, a score-based entry that was "correct" but
early can sit in the portfolio indefinitely while the regime has changed around it.

In bear mode, a shorter hold period also forces more frequent re-evaluation. A
position entered in the first week of a bear could be a correct inverse-ETF entry
or a mistimed long; forcing an exit at 30 days resets that judgment rather than
letting a bad entry compound.

In bull mode, a longer hold period is valid — trending names benefit from time.
The same 60-day expiry that would be too long in a choppy market is exactly right
for a sustained momentum move.

## The slot-competition effect: a critical cascade risk

When you cap `max_positions` per regime, you create slot competition: the scoring
engine fills slots with the top-ranked candidates. This means regime changes
that shift timing by even a few days can displace specific positions and produce
cascading downstream effects on which names occupy slots in future periods.

This is not a bug — it is the system working correctly. But it has a non-obvious
consequence for overlay tuning: changing a regime override in month M can
displace positions that would have occupied slots in months M+3 or M+4, with
effects that propagate much further than the original override window. When you
tune a macro override and see an unexpected change in a period far from the
override date, slot competition is likely the cause.

The practical implication: test regime-parameter changes over the full backtest
horizon, not just the regime window you modified. A change that improves a
specific quarter can degrade a different quarter months later through position
displacement. See the references file for a worked example.

## Worked example: a regime change triggers different sizing

Suppose a strategy enters a position on a day when the regime transitions from
neutral to bull.

**Neutral entry (before regime flip):**
```python
# Neutral params
max_position_pct = 20.0
max_positions    = 5
budget = portfolio_value * 0.20   # $2,000 on $10,000 portfolio
```

**Bull entry (same score, day after regime flip):**
```python
# Bull params
max_position_pct = 30.0
max_positions    = 4
budget = portfolio_value * 0.30   # $3,000 on same $10,000 portfolio
```

The entry signal is identical. The regime change alone increases the position
budget by 50% and reduces the slot count from 5 to 4. This means fewer, larger
positions — higher concentration, higher potential return, higher risk per slot.
Whether this is right depends entirely on whether the regime signal is correct.
If the bull classification is accurate, the larger position captures more of the
move. If it was a false positive, the larger loss hits harder. This is the
fundamental tradeoff in regime-adaptive sizing: the regime signal is load-bearing.

## VIX as a fine-tuning layer

After the regime parameters produce a base budget, a volatility signal can apply
a final multiplier. The VIX (or a realized-volatility proxy for backtests) tiers
the budget up or down based on current fear:

```python
def vix_mult(vix: float) -> float:
    if vix > 30:   return 0.70   # fear regime — reduce size aggressively
    if vix > 25:   return 0.85   # elevated — modest reduction
    if vix >= 15:  return 1.00   # normal — no change
    return 1.10                  # complacency — slight expansion
```

This layer is applied after the regime cap and the account cap, as a final
multiplier. It is a refinement, not a replacement for the regime system. In
particular, do not use realized volatility (rolling SPY std-dev) as a primary
regime signal — it lags actual market stress by weeks and will misclassify
recoveries as bear regimes. Use it only as a fine-tune on an already
regime-determined budget.

## Entry threshold and regime

Position sizing only applies to positions that pass an entry threshold. In bear
mode, tightening the entry threshold (requiring a higher score to open a new
position) is as important as reducing the size. If you size down but still enter
anything above a low threshold, you take many small losses instead of one.

The two levers work together:
- Raise the entry threshold in bear → fewer entries, only the highest conviction
- Reduce `max_position_pct` in bear → each entry is sized conservatively

In neutral, the score threshold returns to the baseline. In bull, you can
afford a slightly lower threshold (admit more candidates) because the regime
tailwind improves the base rate of entries.

## Output: what a regime-sizing report should show

When auditing or designing a regime-position-sizing layer, produce:

```
# Regime Sizing Audit: <strategy name>

## Parameter Table
| Regime  | max_pos_pct | max_positions | hold_days | stop_loss | trailing_stop |
|---------|------------|---------------|-----------|-----------|---------------|
| bull    | ...        | ...           | ...       | ...       | ...           |
| neutral | ...        | ...           | ...       | ...       | ...           |
| bear    | ...        | ...           | ...       | ...       | ...           |

## Pipeline Cap
account_max_position_pct: <value>  (binding in: bull / neutral / bear / none)

## Sizing Logic Walkthrough
<Describe how a position budget is computed from regime + score + caps.
 Confirm the two-cap hierarchy is applied correctly.>

## Stop Logic Review
<For each regime: confirm stop_loss_pct and trailing_stop_pct are used at entry-
 time params, not live-updated if regime changes during the hold period.>

## Hold-Period Expiry
<Confirm a time-based exit exists and is gated on entry-regime params, not
 current-regime params.>

## Slot-Competition Risk
<Note any macro overrides that shift regime timing and flag the need to test
 downstream period effects, not just the override window itself.>

## Findings
<List any parameter mismatches, missing caps, stop widths inconsistent with
 regime sizing philosophy, or coupling errors (live-regime params used for held
 positions instead of entry-regime params).>
```

## Common mistakes

**Using live-regime params for exits on held positions.** When the regime shifts
from bull to neutral during a hold, the position should still be managed with the
stop widths and hold period that were active at entry. Applying the new (tighter)
regime's params to open positions causes premature exits — the position was sized
and risk-budgeted for the bull regime; changing the stop mid-hold violates that
contract. Store entry-regime params on the position object at open time.

**Setting max_positions the same across regimes.** If you reduce `max_position_pct`
in bear but leave `max_positions` at 5, you still open 5 positions — just smaller
ones. This spreads exposure across more names that all decline together. In bear,
fewer positions at higher selectivity outperforms more positions at smaller size.

**Ignoring the interaction between stop width and position size.** A 15% stop on
a 30% position risks 4.5% of portfolio per trade. A 6% stop on a 15% bear
position risks 0.9% of portfolio per trade. The product (size × stop) determines
portfolio-level risk exposure per trade — keep it in mind when tuning regimes
independently.

## Related skills

- Pair with the **regime-classifier** skill to design the upstream signal that
  feeds regime labels into this sizing layer.
- Pair with the **stop-loss-designer** skill when you need to reason more deeply
  about fixed vs. trailing stop structures and volatility-adjusted stop widths.
- Pair with the **macro-overlay** skill when adding FRED credit-spread or
  yield-curve signals as secondary modifiers to the regime cap.
- Pair with the **walk-forward-validation** skill to confirm regime-parameter
  tuning is not overfit to specific historical windows.
- See `references/sizing-parameter-tuning.md` for a detailed tradeoff catalog,
  the slot-competition cascade worked example, and a calibration checklist.


<!-- strongskills-brand -->

---

*Made with a StrongSkills tool — The shortcut to the cutting edge · getstrongskills.com*
