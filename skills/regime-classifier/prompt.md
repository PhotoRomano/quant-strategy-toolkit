# regime-classifier — use this in any AI

Paste everything below the line into ChatGPT, Gemini, Copilot, or any assistant — as your
first message or a system/custom instruction. (In Claude you don't need this file — the skill
activates automatically.) Same method, same results; you just trigger it yourself.

*A StrongSkills tool — The shortcut to the cutting edge · getstrongskills.com*

---

Act as an expert and follow this method exactly.

# Regime Classifier

A regime classifier answers one question at every decision date: is the market in
a trending bull, a ranging neutral, or a declining bear environment? The answer
gates everything downstream — position sizing, asset selection, entry thresholds,
stop widths. Getting the label right (and, critically, getting it in a temporally
honest way) is the difference between a backtest that reflects reality and one
that doesn't.

This skill covers the method, the signals, the scoring logic, the time-gating
requirement, and the macro-override pattern. Backtests do not predict future
returns — a clean regime classifier improves strategy coherence but guarantees
nothing forward.

## Why price-only signals?

The temptation is to pull in real-time volatility (VIX), credit spreads, or macro
releases. Those inputs have a specific problem in backtesting: realized-volatility
proxies (rolling SPY std-dev) lag actual fear by weeks, and macro releases have
publication lags that are easy to violate. A realized-vol proxy computed over a
20-day window will still reflect last month's crash at the exact moment the market
has already bottomed and reversed — producing inverse-ETF entries at the worst
possible time.

Moving averages and price-relative momentum are lag-free and split-adjusted
correctly by any standard data provider. They respond to the same structural price
information that drives MA-based market breadth but without the data-availability
problems. The cost is that sudden discontinuities (policy shocks, pandemics) reach
MA signals only after a delay. The macro-override layer (described below) fills
that gap explicitly and honestly.

## Core signals

All signals are computed strictly from data up to and including the decision date.
See the worked example below for the exact gating pattern.

**MA structure (three binary flags):**
- `above_ma200`: current price > 200-day simple moving average. The MA200 is the
  most widely watched long-run trend level; price above it is a necessary (not
  sufficient) condition for bull posture.
- `above_ma50`: current price > 50-day SMA. Adds a medium-term confirmation layer.
- `golden_cross`: MA50 > MA200. The cross itself lags price action by days or
  weeks, but once established it signals broad structural alignment.

**Multi-timeframe momentum (two lookbacks):**
- `mom20`: (price / price_21_bars_ago - 1) * 100. Twenty-day momentum captures
  the most recent swing. It is the primary substitute for VIX: sharp negative
  momentum replaces the "fear spike" signal without the data-lag problem.
- `mom60`: (price / price_61_bars_ago - 1) * 100. Sixty-day momentum confirms
  whether the 20-day move is part of a broader trend or a brief deviation.

## Scoring and thresholds

Combine the signals into a scalar score on [0, 100] centered at 50 (no signal).
Add points for bullish structure, subtract for bearish. Map the score to a label
using two thresholds. The thresholds and weights below are illustrative starting
points — you must calibrate them on your own data:

```
score = 50   # neutral baseline

# MA structure — these weights are illustrative starting points
if above_ma200:   score += 20
if above_ma50:    score += 15
if golden_cross:  score += 10

# 20-day momentum — calibrate the bands to your instrument
if mom20 > 5:    score += 10
elif mom20 > 2:  score +=  8
elif mom20 > 0:  score +=  4
if mom20 < -10:  score -= 20   # sharp drop = primary bear signal
elif mom20 < -5: score -= 12
elif mom20 < -2: score -=  5

# 60-day trend confirmation — tighten or loosen based on regime length
if mom60 > 10:    score +=  5
elif mom60 < -15: score -= 10

score = max(0, min(100, score))

# Threshold mapping — tune these on out-of-sample data, not the full history
if score >= 65:   regime = "bull"
elif score <= 35: regime = "bear"
else:             regime = "neutral"
```

Why this structure? The MA flags give slow, stable signals that prevent whipsawing
during sideways markets. Momentum adds responsiveness — especially on the downside,
where steep drops punish the score quickly even if the 200-day MA has not yet
turned. The two-threshold design creates a neutral dead-zone that keeps the
classifier from toggling on every noise event.

The specific weight values and thresholds must be treated as illustrative starting
points. You should tune them on a held-out validation window, not the same dates
you optimized on — see `references/calibration-and-override.md` for the full
calibration process.

## Time-gating requirement

This is the critical correctness constraint. Every computation must use only data
available on the decision date. A single wrong index pulls the future into the past
and silently inflates backtest quality.

**Leaky version — do not use:**
```python
ma200 = spy["close"].rolling(200).mean().iloc[-1]  # last row of the WHOLE frame
price = spy["close"].iloc[-1]                       # not the row at D — "today"
regime = "bull" if price > ma200 else "bear"
```
`iloc[-1]` on an unsliced frame reads the most recent row in the dataset, not the
row at the decision date. Every past bar is computed using the present.

**Correctly gated version:**
```python
def compute_regime(spy_full: pd.Series, decision_date: str) -> dict:
    spy = spy_full.loc[:decision_date].dropna()   # ONLY data up to D
    if len(spy) < 5:
        return {"regime": "neutral", "score": 50}

    price  = float(spy.iloc[-1])                  # iloc[-1] is now "as of D"
    ma50   = float(spy.rolling(50).mean().iloc[-1])  if len(spy) >= 50  else float(spy.mean())
    ma200  = float(spy.rolling(200).mean().iloc[-1]) if len(spy) >= 200 else float(spy.mean())
    mom20  = (price / float(spy.iloc[-21]) - 1) * 100 if len(spy) >= 21 else 0.0
    mom60  = (price / float(spy.iloc[-61]) - 1) * 100 if len(spy) >= 61 else 0.0
    # ... rest of scoring logic ...
```

The one-line fix `spy_full.loc[:decision_date]` is the entire gating pattern. In
the lookahead-audit skill, this is listed as a High-severity leak when missing. If
your walk-forward loop calls this function inside the loop, the slice is re-applied
correctly on every iteration automatically.

## Macro-override layer

The computed regime is honest but slow. A 200-day MA takes months to respond to a
sudden policy shock, pandemic, or financial crisis. The gap between the signal a
strategy needs ("we are now in a bear") and what MAs can provide lags by weeks.

The macro-override pattern solves this explicitly: maintain a sorted list of dated
override entries. At each decision date, look up the most-recent entry on or before
that date and, if it contains a regime override, use it in place of the computed
result. When the shock is absorbed, add a `None` entry to resume computed signals.

```python
MACRO_EVENTS = {
    "2020-02-20": {"regime_override": "bear"},   # explicit bear entry
    "2020-03-23": {"regime_override": "bull"},   # bottom confirmed
    "2020-11-01": {"regime_override": None},     # resume computed regime
    # add entries for your own strategy's hard transitions
}

def get_regime(spy_full, decision_date):
    result = compute_regime(spy_full, decision_date)  # from above

    # Walk events up to decision_date and apply the last applicable override
    active_override = None
    for ev_date in sorted(MACRO_EVENTS):
        if ev_date <= decision_date:
            ev = MACRO_EVENTS[ev_date]
            if ev.get("regime_override") is None:
                active_override = None          # explicit clear
            else:
                active_override = ev["regime_override"]
        else:
            break

    if active_override is not None:
        result["regime"] = active_override
        result["override_active"] = True
    return result
```

**The design-bias trap:** Every override date you add is a decision made with
hindsight. The override table is a form of hand-labeling the training set. This
does not make the backtest temporally dishonest — the data reads are still
time-gated — but it is selection bias at the strategy-design level. You must
disclose that override dates were chosen after seeing the historical data, and you
should test the strategy on a walk-forward window that contains none of the
override dates. The lookahead-audit skill covers how to distinguish code-level
leakage from design-level bias.

## Output schema

Every call to the regime function should return a consistent dict that the rest of
the strategy can depend on:

```
{
  "regime":         "bull" | "neutral" | "bear",
  "score":          int,          # 0–100
  "spy_price":      float,
  "ma50":           float,
  "ma200":          float,
  "above_ma50":     bool,
  "above_ma200":    bool,
  "golden_cross":   bool,
  "momentum_20d":   float,        # percent
  "momentum_60d":   float,        # percent
  "override_active": bool         # True if a macro event overrode the computed label
}
```

Returning the component signals alongside the label is important: it lets you
audit why a specific date was classified as bull rather than neutral, and it feeds
richer logging when you are tuning thresholds.

## Regime audit report format

When auditing an existing classifier, produce this structure:

```
# Regime Classifier Audit: <strategy name>

## Signal Inventory
| Signal       | Gated to decision date? | Notes                         |
|--------------|------------------------|-------------------------------|
| MA200        |                        |                               |
| MA50         |                        |                               |
| Mom20        |                        |                               |
| Mom60        |                        |                               |
| Override table |                      |                               |

## Time-Gating Check
<Pass / Fail — one finding per signal with file:line>

## Threshold Calibration
<What thresholds were used, how they were chosen, whether held-out validation was done>

## Override Disclosure
<List of all override entries and the reasoning. Note which were added with hindsight.>

## Verdict
<CLEAN / ISSUES FOUND — one-sentence summary>
```

## Worked micro-example

Suppose a strategy backtests 2019–2023. On **2020-03-01** (one week into the
COVID selloff), the classifier should label the date as bear. Here is what happens
with correct gating:

```
spy.loc[:"2020-03-01"] → last row is March 1 close
price  = 300.35
ma50   = 321.42   →  above_ma50  = False
ma200  = 310.12   →  above_ma200 = False, golden_cross = False
mom20  = -8.3%    →  score penalty: -12
mom60  = -4.7%    →  no extra penalty (< -15 threshold not hit)

score = 50 + 0 + 0 + 0 + (-12) = 38  →  regime = "neutral"
```

The computed signal returns "neutral" on March 1 because the selloff is only 9
days old and the 60-day momentum has not fully turned. This is the limitation:
MAs and medium-term momentum take time. The macro-override entry for 2020-02-20
("bear") is applied after the computed step, correctly labeling March 1 as bear
without any look-ahead. The override was set at a date-the-crash-began, not at
the eventual bottom — the override date itself must be defensible in real-time
terms, not chosen because you know when the bottom was.

## Pairing this skill

- **regime-position-sizing** — wire the regime label to position size, slot count,
  and hold-period parameters.
- **macro-overlay** — incorporate FRED macro series (CAPE, HY spreads, yield curve)
  as additional soft inputs to the regime score, with correct release-lag gating.
- **lookahead-audit** — verify your regime function's time-gating before trusting
  backtest numbers.
- **walk-forward-validation** — confirm regime thresholds generalize to periods not
  used during calibration.

See `references/calibration-and-override.md` for threshold tuning, walk-forward
split recommendations, and the override-audit checklist.


<!-- strongskills-brand -->

---

*Made with a StrongSkills tool — The shortcut to the cutting edge · getstrongskills.com*
