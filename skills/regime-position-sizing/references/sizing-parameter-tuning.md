# Regime Sizing — Parameter Tuning Reference

This file provides deeper guidance on tradeoffs, a slot-competition worked
example, and a calibration checklist. Read it after the main SKILL.md when you
are ready to tune specific parameter values or diagnose unexpected backtest
behavior after a regime-parameter change.

---

## Tradeoff catalog

### `max_position_pct`

Increasing this increases both upside capture and per-position loss exposure.
The interaction with `max_positions` determines total deployed capital.

| Change | Effect |
|--------|--------|
| Bull: raise from 25% → 35% | Winners compound larger; a single loss also hits harder |
| Bear: lower from 20% → 10% | Fewer dollars at risk; also fewer dollars recovered if right |
| Neutral: raise to match bull | Eliminates the regime differentiation — defeats the purpose |

A useful sanity check: `max_position_pct × max_positions` should not exceed ~100%
in any regime (it should be lower, to leave cash for unexpected opportunities and
to avoid edge cases where the position loop tries to open slots it cannot fund).
Typical deployed capital targets:
- Bull: 80–120% (modest leverage or nearly full deployment across 4 slots)
- Neutral: 60–80% (hold some cash; let choppy entries breathe)
- Bear: 20–40% (mostly cash or inverse exposure; protect capital)

### `max_positions`

The position count cap is the primary driver of concentration. Fewer slots mean:
- Higher per-slot conviction required (the score gate becomes the qualifying bar)
- Larger average position size (given the same `max_position_pct`)
- More sensitivity to any one trade's outcome

Counter-intuitively, reducing `max_positions` in bear can improve outcomes: a
strategy with 2 bear slots that are highly selective makes fewer entries and takes
fewer losses than one with 5 smaller slots. The math of loss avoidance usually
dominates the math of diversification in adverse regimes.

Testing pattern: vary max_positions over ±1 and measure the change in bear-regime
win rate and average loss magnitude separately. The joint effect on total return
can mask opposite movements in these two components.

### `hold_days`

Hold period interacts with `max_positions` through slot turnover. A shorter hold
period means slots open up more frequently, which means more entries per year.
More entries per year means more chances to be wrong, but also more chances to
catch regime transitions that produce good entries late in a period.

In bear mode, a short hold period (20–30 days) keeps capital moving and resets
judgment. But it also means bear-regime entries cycle out before long bearish
trends fully develop. If your primary bear-regime vehicle is inverse ETFs, short
hold periods are usually correct — leveraged instruments decay over time even
when directionally correct.

In bull mode, a long hold period (45–75 days) allows trends to develop. But
holding too long (>90 days) means a bull entry made before a regime shift stays
on the books into a neutral or bear regime, at the entry-regime (bull) stop
widths. This is usually the intended behavior — see "common mistakes" in SKILL.md
about not re-applying current-regime params to held positions.

### `stop_loss_pct` vs `trailing_stop_pct`

These two exits have different purposes and should be set independently:

- `stop_loss_pct` is your maximum acceptable loss on a single entry. Set it based
  on what dollar loss you can absorb per position given your account size and
  position sizing. Example: if `max_position_pct = 20%` on a $10,000 portfolio,
  the position is $2,000. A 10% stop means max loss is $200 on this entry.
- `trailing_stop_pct` protects profits after a position moves in your favor. It
  should be wide enough to let a winner run past normal volatility, but tight
  enough to exit before a peak-to-trough reversal destroys gains.

A common tuning problem: setting the trailing stop equal to or narrower than
the fixed stop. This creates a situation where on a flat or barely positive
entry, the trailing stop fires before the position has had any meaningful gain
to protect. The trailing stop should always be at least as wide as the fixed
stop, and usually wider in bull mode.

Another common problem: setting the trailing stop so wide in bull mode (e.g.,
25%) that the average winning trade gives back 20% of its peak value before
exiting. If your average winner peaks at +30% and the trailing stop is 25%,
your average exit is around +5%. A trailing stop of 12–18% in bull mode
captures more of the trend while still allowing for the normal volatility a
momentum position experiences.

---

## Slot-competition cascade: worked example

This illustrates how a regime override in month M can produce unexpected results
in month M+5 through position displacement.

**Scenario:** A backtest has a bull regime through months 1–3. In month 4, a
neutral override is applied. The strategy has `max_positions = 4` in bull and
`max_positions = 5` in neutral.

**What happens:**
- During the bull period, 4 high-scoring positions fill all slots.
- At the neutral override in month 4, those positions may still be open (if
  within their hold period) — the regime change does not close them.
- New entries in neutral have 5 slots available, but some are occupied by
  carry-over bull positions.
- The scoring engine fills remaining open slots with neutral-regime candidates.
  These may be different names than would have entered without the override.
- Those neutral-regime entries will have their own hold periods, which extend
  into months 5–6.
- In month 6, when the bull regime resumes (or a new bull override fires), the
  slots may be occupied by the neutral-period entries rather than the high-
  conviction bull candidates the regime would naturally select.

**The cascade:** The override in month 4 displaced candidates in months 5–6
by changing which names occupied slots at the transition point. The effect
is visible months after the override window.

**Diagnosis pattern:** When a regime change produces unexpected results in a
period well after the change, inspect the position log for that later period
and identify which positions were open and when they entered. If they entered
during the override window, the cascade is confirmed.

**Mitigation:** Test every regime-parameter or overlay change against the full
backtest horizon. An improvement in the target quarter paired with a regression
in a distant quarter is a sign of slot-competition cascade, not a genuine
improvement in the override logic.

---

## Bear-regime special cases: inverse ETFs

If your universe includes inverse ETFs (1x or leveraged), bear mode requires
two additional design decisions:

**1. Duration-aware leveraged exclusion.** Leveraged inverse ETFs (e.g., 3x)
profit from sharp, fast crashes but decay and get crushed by counter-rallies
in prolonged bear markets. A rule-of-thumb gate: if the bear regime has been
active for more than approximately 30 trading days (roughly 6 weeks), exclude
leveraged inverse ETFs from new entries. Continue holding existing positions
through their normal exit conditions (stop, trailing stop, or hold-period
expiry). 1x inverse ETFs are generally safer to hold throughout a prolonged
bear, though they still experience counter-rally losses.

**2. Sentiment signal inversion.** If you use news sentiment as a signal
component for long entries, invert it for inverse ETF entries in bear mode:
negative news for the market is bullish for a short position. Failing to
invert produces the wrong sign on the sentiment contribution and can prevent
inverse ETF entries exactly when market conditions are most bearish.

**3. Stop widths for inverse ETFs.** Inverse ETFs experience amplified counter-
rally moves. A 3x inverse ETF loses 9% on a 3% SPY bounce. In a bear regime,
applying the normal bear stop widths (e.g., 6%) to an inverse ETF will fire
on the first counter-rally, before the primary trend resumes. Two options:
- Use a wider stop for inverse ETFs specifically (20%+ in bear mode)
- Remove the fixed stop entirely and rely on hold-period expiry and trailing stop

---

## Calibration checklist

Use this when setting initial regime parameters or reviewing an existing setup:

- [ ] Each regime has distinct `max_position_pct` values. Bear < Neutral < Bull.
- [ ] `max_position_pct × max_positions` does not exceed ~120% in any regime.
- [ ] `trailing_stop_pct >= stop_loss_pct` in every regime.
- [ ] `hold_days` is shortest in bear (typically 20–45) and longest in bull
      (typically 45–75). Neutral sits between them.
- [ ] Account-level cap (`account_max_position_pct`) is applied as a final clamp,
      not a conditional — it is always min(regime budget, account budget).
- [ ] Entry-regime params are stored on each position at open time and used for
      stop and hold-period management throughout the position's life.
- [ ] Bear regime has a tighter score entry threshold, not just smaller size.
- [ ] If inverse ETFs are in the universe, duration-aware exclusion is implemented
      for leveraged versions.
- [ ] After any regime-parameter change, the full backtest period is re-run (not
      just the period containing the change) to detect cascade effects.
- [ ] Stop widths have been cross-checked against the product (size × stop) to
      confirm portfolio-level risk per trade is within acceptable bounds.
