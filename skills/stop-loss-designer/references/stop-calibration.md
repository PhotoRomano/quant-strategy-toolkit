# Stop Calibration Reference

Detailed calibration methods for cost-basis and trailing stops. Read this after
designing the initial stop architecture in SKILL.md — this file covers how to
derive stop widths from data rather than guessing.

## Table of contents

1. ATR-based stop sizing
2. Volatility-regime adjustment
3. Calibration workflow (walk-forward method)
4. Common failure modes and diagnostics

---

## 1. ATR-based stop sizing

A fixed-percent stop (e.g., 10%) applies the same dollar tolerance to a volatile
biotech and a stable consumer staple. A better approach is to size stops as a
multiple of the instrument's Average True Range (ATR) — this makes the stop
proportional to how much the security normally moves.

**True Range** for one bar:
```
True Range = max(
    high - low,
    abs(high - prev_close),
    abs(low  - prev_close)
)
```

**ATR(n):** rolling mean of True Range over n bars. A 14-bar ATR is a common default.

**Stop width as ATR multiple:**
```python
def atr_stop(entry_price: float, atr: float, multiple: float) -> float:
    """Returns the absolute stop price below entry."""
    return entry_price - (multiple * atr)

# Example: entry at $100, ATR(14) = $3.20, multiple = 2.5
# stop_price = $100 - (2.5 × $3.20) = $100 - $8.00 = $92.00
# effective stop_pct = 8%
```

The multiple controls how far outside normal price action the stop sits. Common
starting ranges:
- Tight / mean-reversion: 1.5–2.0× ATR
- Trend-following (medium-term): 2.5–3.0× ATR
- Wide / position trade: 3.5–4.0× ATR

**Converting ATR stops to percent:** After computing the ATR stop price, you can
also express it as a percent of entry for comparison with your REGIME_PARAMS table:
```
stop_pct = (entry_price - stop_price) / entry_price * 100
```

Use this to check whether your fixed-percent stops are wider or narrower than an
ATR-based stop would suggest. If your fixed 8% stop fires frequently on instruments
with 5%+ daily ATR, the stop is inside normal noise — widen it or switch to ATR-based.

**ATR for trailing stops:** Apply the same logic to trailing stops. Set the trailing
stop at `peak_price - (multiple × ATR_at_entry)`. Note: use ATR computed at entry
and freeze it, rather than updating ATR dynamically throughout the hold — dynamic ATR
trailing stops can widen unexpectedly during high-volatility periods, which is the
opposite of protective behavior.

---

## 2. Volatility-regime adjustment

ATR adapts to the specific instrument, but both ATR-based and fixed-percent stops
benefit from a broader market volatility overlay. When implied or realized market
volatility spikes, individual securities become more volatile too — a stop calibrated
in a calm market is effectively too tight in a high-volatility environment.

A practical approach: bin realized volatility into regimes and apply a multiplier.

```python
def volatility_adjusted_stop_pct(
    base_stop_pct: float,
    realized_vol_annualized: float,  # e.g. SPY rolling 20-day annualized
) -> float:
    """
    Scales base stop width by a volatility multiplier.
    These breakpoints and multipliers are illustrative — calibrate to your data.
    """
    if realized_vol_annualized < 15:
        multiplier = 0.9    # calm markets: tighten slightly
    elif realized_vol_annualized < 25:
        multiplier = 1.0    # normal: no adjustment
    elif realized_vol_annualized < 40:
        multiplier = 1.3    # elevated vol: wider stops needed
    else:
        multiplier = 1.6    # crisis vol: significantly wider or flat-out hold cash

    return base_stop_pct * multiplier
```

**Important:** Do not use realized volatility computed from the full history as a
live vol proxy. That introduces look-ahead bias. Use only trailing realized vol
computed over data up to the decision date (`series.loc[:D].rolling(n).std()`).

---

## 3. Calibration workflow (walk-forward method)

Never calibrate stop widths on the same data you will backtest against. The
in-sample data will suggest a stop width that fits the specific price history
you optimized on — it will appear to avoid every major drawdown by a small margin.
That appearance is selection bias.

**Step 1: Define a calibration period and a validation period.**
Split your historical data into an earlier calibration window and a later validation
window. The validation window should contain regimes not well-represented in
calibration — ideally at least one bull cycle and one bear or neutral phase.

**Step 2: On the calibration window, run a parameter sweep.**
For each candidate stop pair `(stop_loss_pct, trailing_stop_pct)`:
- Run the backtest with only that stop pair.
- Compute: average loss at stop (should be close to the stop width, not larger),
  stop-out rate (what fraction of trades exit via stop), and return contribution
  from stopped positions vs. non-stopped positions.

**Step 3: Select the Pareto-efficient pair.**
The goal is not to minimize stop-outs (narrow stops) or maximize hold time (wide
stops) — it is to find the pair where:
- Average loss at hard stop ≈ hard stop width (no excess slippage signal)
- Stop-out rate in bear is high enough to show the stop is doing protective work
- Trailing stop fires primarily on positions that had already advanced

Avoid selecting the pair with the best-looking backtest total return — that is
overfitting to the calibration period's specific path.

**Step 4: Validate on the held-out window.**
Run the validated pair on the validation window with no further tuning. The key
metrics to check:
- Do average stop losses stay close to the stop width? (Slippage check)
- Does the stop-out rate in bear regimes remain elevated? (Protective function intact)
- Is the trailing stop still firing primarily on advanced positions?

If behavior on the validation window diverges significantly from calibration, the
parameters are overfit. Widen the stop to something more conservative and re-validate.

**Step 5: Log the calibration lineage.**
Keep a record of what period was used for calibration, what the selected values are,
and what the stop-out statistics looked like in calibration vs. validation. When you
run the next experiment (see training-log skill), note whether the stops were
re-calibrated or carried forward from the previous run.

---

## 4. Common failure modes and diagnostics

### Failure: Hard stop fires far past the intended level

**Symptom:** average loss at stop is substantially larger than `stop_loss_pct` (e.g.,
you set 8% but average loss at stop is 12%).

**Causes:**
1. Gap opens: the security gapped down through the stop price overnight. The fill
   occurred at the open, which was below the stop trigger. This is normal in
   equity backtests and almost universal in live trading; model it with realistic
   fill assumptions.
2. Illiquid instrument: the security has low volume and the bid/ask spread is wide.
   The executed price is well below the trigger.
3. Stop checked only at close: if your backtest evaluates stops once per bar (close
   price), you miss intra-bar breaches. Intra-day stops require intra-day data.

**Diagnostic:** compute `stop_fill_excess = avg_loss_at_stop - stop_loss_pct`. Values
above 1–2% indicate systematic gap or liquidity problems that should be modeled.

### Failure: Trailing stop fires on positions that never advanced

**Symptom:** many trailing-stop exits with negative PnL — the trailing stop fired
before the hard stop.

**Cause:** `trailing_stop_pct` is narrower than `stop_loss_pct`. A position that moves
directly against you after entry will trigger the trailing stop (peak == entry,
drop_from_peak = loss) before the hard stop fires.

**Fix:** ensure `trailing_stop_pct >= stop_loss_pct + some_buffer`. The trailing stop
should only dominate in positions that gained first.

**Diagnostic:** filter stop exits for those where `peak_price <= entry_price * 1.02`
(peak barely above entry). If trailing fires frequently here, it is acting as a second
hard stop rather than a gain-protection mechanism.

### Failure: Stop-out churn in a downtrend

**Symptom:** in bear or neutral regime, the same symbol stops out multiple times
across a backtest run — buy, stop, buy (same name), stop, repeat.

**Cause:** no stop-out cooldown, or the cooldown period is too short relative to how
long the downtrend persists.

**Fix:** implement a cooldown (see SKILL.md) and extend it in bear/neutral. In bear
regime the correct behavior is to stop out a broken name and not re-enter it for at
least 15–20 trading sessions. Review the cooldown log to find the median sessions
between stop-out and the next entry attempt for the same symbol.

### Failure: Bull trailing stop too wide, winners erode before exit

**Symptom:** in bull regime, positions regularly advance to +20% or more, then exit
via trailing stop at +2–5% net gain. The trailing stop is so wide it gives back most
of the gain before triggering.

**Fix:** reduce `trailing_stop_pct` in bull. The common intuition says "let winners
run" but a 15% trailing stop in a bull market already allows substantial room. Beyond
that level, you are holding through corrections that a reasonable exit would have
captured at a higher level. The right trailing width is not the widest you can defend
intellectually — it is the one that captures an acceptable fraction of the average run.

**Diagnostic:** compute `peak_to_exit_ratio = exit_price / peak_price` for all
trailing-stop exits. If this is consistently below 0.85 (exiting at less than 85% of
peak), your trailing stop is too wide for the typical run length in that regime.

### Failure: Stop parameters look right in-sample, fail out-of-sample

**Symptom:** stops calibrated on the calibration window produce clearly different
stop-out rates and average loss distributions on the validation window.

**Cause:** this is regime-distribution mismatch. If the calibration window contained
mostly bull markets and the validation window contains a prolonged bear, the bear
stop parameters were not well-calibrated to begin with.

**Fix:** ensure calibration windows include representative samples of all three regime
states. If your history is too short to contain all three, acknowledge the gap and
use more conservative (wider) stops as a default until you have seen all regimes.
