# circuit-breaker — use this in any AI

Paste everything below the line into ChatGPT, Gemini, Copilot, or any assistant — as your
first message or a system/custom instruction. (In Claude you don't need this file — the skill
activates automatically.) Same method, same results; you just trigger it yourself.

*A StrongSkills tool — The shortcut to the cutting edge · getstrongskills.com*

---

Act as an expert and follow this method exactly.

# Circuit Breaker: Drawdown Pause + Correlation Gate

Automated strategies make their worst decisions when the market is already punishing them.
A drawdown-triggered pause (the "circuit breaker") stops new entries during a losing streak.
A correlation gate suppresses satellite entries when a lead asset signals a trend break.
Together they act as an outer control loop: the core strategy keeps running, but the circuit
breaker blocks new capital deployment until the environment stabilizes.

Neither mechanism predicts the future or improves your expected return per trade. They reduce
the number of trades taken in poor conditions, which shrinks the left tail of outcomes without
necessarily moving the center. Whether that tradeoff improves your system is something you
must validate in your own backtest. This skill teaches the construction method; the numbers
you choose are yours to calibrate.

## Two mechanisms, one control loop

### Mechanism 1 — Drawdown pause (portfolio-level)

The drawdown pause watches the running portfolio value, computes peak-to-current drawdown,
and writes a persistent state flag when the drawdown crosses a threshold. Every run-loop cycle
checks the flag before entering new positions. If the flag is `PAUSED`, no new entries open.
The pause lifts when recovery conditions are met.

**Why a state file (or equivalent persistent store)?** Automated systems run on cron or event
triggers. The "pause" needs to survive process restarts, machine reboots, and broker API
reconnects. Keeping state in memory only means it silently resets on the next heartbeat.

### Mechanism 2 — Correlation gate (lead-asset EMA filter)

When several assets in the portfolio are structurally correlated — crypto pairs, sector
baskets, levered + unlevered versions of the same index — entries in the satellite assets
should be conditional on the health of the lead asset. The gate checks whether the lead
asset's fast EMA is above its slow EMA. If not (the trend is broken), suppress new entries
in correlated satellites even if their individual signals look acceptable.

**Why this is not redundant with the drawdown pause:** The EMA gate fires based on *trend
direction* in a single bellwether ticker. It can trigger before a portfolio-level drawdown
has accumulated, and it targets a specific correlated subset rather than halting everything.
The two mechanisms are complementary: the EMA gate is surgical, the drawdown pause is blunt.

## Build order

### Step 1 — Define your state schema

Decide where state lives. A JSON file on disk is simple and portable. An in-memory singleton
with a watchdog flush works for tighter latency requirements. A database row works if the
system already uses one. The minimal fields:

```
status          : "ACTIVE" | "PAUSED"
peak_value      : float           # highest portfolio value observed so far
current_drawdown_pct : float      # (peak - current) / peak * 100
paused_at       : ISO timestamp | null
pause_reason    : str | null
resume_condition: str             # human-readable description of what triggers resume
```

Persist on every write. Read at the top of every run loop.

### Step 2 — Implement the drawdown calculator

At each heartbeat, compute:

```python
def compute_drawdown(current_value: float, peak_value: float) -> float:
    if peak_value <= 0:
        return 0.0
    return (peak_value - current_value) / peak_value * 100   # positive number = loss
```

Update `peak_value` only when `current_value > peak_value`. Never lower the peak. This
ensures drawdown is measured from the true high-water mark, not from yesterday's close.

**Wrong pattern — resets peak on every call:**
```python
peak = max(history)     # recomputed from scratch — correct if history is complete,
                        # but often history is truncated and peak silently drifts down
```

**Correct pattern — running high-water mark:**
```python
state["peak_value"] = max(state["peak_value"], current_value)
dd = compute_drawdown(current_value, state["peak_value"])
```

### Step 3 — Implement the pause/resume logic

```python
DRAWDOWN_PAUSE_THRESHOLD = 8.0   # illustrative starting point — tune to your system
RESUME_LOOKBACK_DAYS     = 3     # days of consecutive improvement before resuming

def maybe_pause(state, current_value, threshold=DRAWDOWN_PAUSE_THRESHOLD):
    state["peak_value"]           = max(state["peak_value"], current_value)
    state["current_drawdown_pct"] = compute_drawdown(current_value, state["peak_value"])

    if state["status"] == "ACTIVE" and state["current_drawdown_pct"] >= threshold:
        state["status"]       = "PAUSED"
        state["paused_at"]    = datetime.utcnow().isoformat()
        state["pause_reason"] = f"Drawdown {state['current_drawdown_pct']:.1f}% >= {threshold}%"
        save_state(state)
        return "PAUSED"
    return state["status"]


def maybe_resume(state, current_value, days_above_ema: int, lookback=RESUME_LOOKBACK_DAYS):
    """
    Resume only when portfolio has recovered partially AND price is trending up.
    Both conditions reduce the risk of resuming into a dead-cat bounce.
    """
    if state["status"] != "PAUSED":
        return state["status"]

    partial_recovery = current_value >= state["peak_value"] * 0.97  # e.g. within 3% of peak
    trending_up      = days_above_ema >= lookback

    if partial_recovery and trending_up:
        state["status"]    = "ACTIVE"
        state["paused_at"] = None
        save_state(state)
        return "ACTIVE"
    return "PAUSED"
```

The `days_above_ema` input comes from the correlation gate (step 4), creating a natural
handshake: the system resumes only when the leading indicator has also stabilized.

### Step 4 — Implement the EMA correlation gate

```python
def ema_gate(prices: list[float], fast: int, slow: int) -> dict:
    """
    Returns whether the fast EMA is above the slow EMA for the lead asset,
    plus a streak count for use in the resume condition.
    """
    if len(prices) < slow:
        return {"gate_open": True, "fast_ema": None, "slow_ema": None, "days_above": 0}

    series      = pd.Series(prices)
    fast_ema    = series.ewm(span=fast, adjust=False).mean().iloc[-1]
    slow_ema    = series.ewm(span=slow, adjust=False).mean().iloc[-1]
    gate_open   = fast_ema > slow_ema

    # Count consecutive closes where fast > slow for resume condition
    fast_series = series.ewm(span=fast, adjust=False).mean()
    slow_series = series.ewm(span=slow, adjust=False).mean()
    above       = (fast_series > slow_series).tolist()
    streak      = 0
    for v in reversed(above):
        if v:
            streak += 1
        else:
            break

    return {"gate_open": gate_open, "fast_ema": fast_ema, "slow_ema": slow_ema, "days_above": streak}
```

The span values (fast, slow) are parameters you tune. Common starting points are 12/26 for
intraday or daily crypto, 20/50 or 50/200 for equities — but these are illustrative. Run
your system over historical data across at least one full market cycle to find spans that
balance responsiveness (smaller fast) against noise-sensitivity (larger gap). There is no
universal correct answer.

### Step 5 — Wire them into your run loop

```python
def run_loop(state, portfolio_client, lead_ticker_prices, correlated_symbols):
    current_value = portfolio_client.get_portfolio_value()
    gate          = ema_gate(lead_ticker_prices, fast=12, slow=26)

    # Drawdown pause check
    breaker_status = maybe_pause(state, current_value)
    if breaker_status == "PAUSED":
        # Still run exits and monitoring — only block new entries
        log.info(f"[circuit-breaker] PAUSED — dd={state['current_drawdown_pct']:.1f}%")
        run_exits_only(portfolio_client)
        maybe_resume(state, current_value, days_above_ema=gate["days_above"])
        return

    # Correlation gate check per candidate
    for candidate in get_entry_candidates():
        if candidate["symbol"] in correlated_symbols and not gate["gate_open"]:
            log.info(f"[circuit-breaker] EMA gate closed — skipping {candidate['symbol']}")
            continue
        execute_entry(candidate)
```

Two critical points:
- **Never block exits.** The circuit breaker suppresses entries only. Holding a losing
  position because the breaker fired on both entry and exit logic is a compounding mistake.
- **Log every gate event.** Without logs you cannot distinguish "strategy found nothing"
  from "circuit breaker suppressed everything." Debugging live systems requires this audit trail.

## Report format

When asked to design or review a circuit breaker, produce this structure:

```
# Circuit Breaker Design: <system name>

## Configuration
| Parameter              | Proposed value | Rationale |
|------------------------|---------------|-----------|
| Drawdown threshold     | ?%            | ...       |
| Pause resume condition | ...           | ...       |
| Lead asset             | ...           | ...       |
| Fast EMA span          | ?             | ...       |
| Slow EMA span          | ?             | ...       |
| Correlated set         | [...]         | ...       |

## State schema
<fields and persistence method>

## Run-loop integration points
1. Where pause check runs (top of loop, before screening)
2. Where gate check runs (per-candidate, before entry)
3. Where exits are protected (confirm exits are NOT gated)
4. How state is persisted and recovered on restart

## Gaps / risks
<What the circuit breaker cannot protect against: gap-down opens, liquidity crises,
 simultaneous drawdown and EMA gap break, correlation breakdown, etc.>

## Backtesting note
<Confirm parameters were chosen on OOS data or explicitly mark as in-sample.>
```

## Worked micro-example — crypto system with a BTC correlation gate

A system trades BTC, ETH, and several BTC-correlated altcoins. ETH and the alts move with
BTC; entering them when BTC is in a sustained downtrend amplifies losses.

**Without the gate — leaky pattern:**
```python
for symbol in ["BTC", "ETH", "ALT1", "ALT2"]:
    if signal(symbol) == "BUY":
        execute(symbol)    # enters alts even as BTC breaks its 26-EMA — all bleed together
```

**With the gate:**
```python
btc_gate = ema_gate(btc_closes, fast=12, slow=26)

for symbol in ["BTC", "ETH", "ALT1", "ALT2"]:
    if signal(symbol) != "BUY":
        continue
    if symbol != "BTC" and not btc_gate["gate_open"]:
        log.info(f"EMA gate closed (BTC fast={btc_gate['fast_ema']:.0f} < slow={btc_gate['slow_ema']:.0f}) — skip {symbol}")
        continue
    execute(symbol)
```

The BTC entry itself is not suppressed — BTC is the lead asset. The correlated satellites
(ETH, alts) are suppressed until BTC's fast EMA recovers above its slow EMA. This asymmetry
is intentional: the signal for BTC may be valid at the very bottom; the alts amplify the
downside and don't need to be caught at the knife.

The same pattern applies to equity sector baskets (suppress semis equipment names when the
semiconductor ETF's 50-EMA crosses below the 200), to levered pairs (suppress 3× when 1×
trend breaks), or to any multi-asset system where structural correlation is known in advance.

## What the circuit breaker cannot protect against

- **Gap opens.** If news breaks overnight and the market opens 15% down, the breaker fires
  *after* the gap. It reduces subsequent losses, not the gap itself.
- **Correlation breakdown.** If the correlation between lead and satellite assets changes
  regime (e.g., an idiosyncratic shock hits only one asset), the EMA gate on the lead asset
  gives a false signal. Verify that the correlation assumption holds in your data.
- **Parameter overfitting.** If the drawdown threshold and EMA spans were chosen by fitting
  to historical drawdowns, they may be too tight (fires on every dip) or too loose (never
  fires until too late) on new data. Choose parameters on out-of-sample data or accept the
  overfitting risk explicitly.
- **The system itself.** A circuit breaker on a flawed strategy buys time but doesn't fix
  the strategy. Use it as a safety margin, not a substitute for good signal construction.

## Calibration guidance

See `references/calibration.md` for a structured approach to threshold selection, including
a sensitivity analysis framework and recommended out-of-sample validation steps.

## Pairing with other skills

- **regime-classifier** — the market regime score is often a cleaner trigger for pausing
  than raw drawdown percentage alone. Consider using both: pause when *either* the portfolio
  crosses the drawdown threshold *or* the regime score drops to extreme bear.
- **stop-loss-designer** — the circuit breaker is a portfolio-level control; stop losses are
  position-level controls. Both are needed. The circuit breaker does not replace per-position
  stops.
- **walk-forward-validation** — confirm the circuit breaker improves out-of-sample risk
  metrics (max drawdown, Calmar ratio) rather than just looking better in-sample.


<!-- strongskills-brand -->

---

*Made with a StrongSkills tool — The shortcut to the cutting edge · getstrongskills.com*
