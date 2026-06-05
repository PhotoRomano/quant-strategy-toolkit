---
name: sector-concentration
description: Design and tune deliberate sector or theme concentration in a quantitative momentum strategy — using score boosts, universe filtering, or position caps to tilt holdings toward a dominant macro theme rather than letting a wide universe dilute winner returns. Use this whenever someone says "my backtest misses the obvious winners", "my scores rank the best stocks too low when the universe is wide", "I know tech/AI/energy is dominating but my strategy won't concentrate there", "how do I tilt toward a sector without hard-coding trades", "my rankings are too flat across sectors", or "adding more stocks dilutes my best positions". Also use when a strategy's momentum scorer is working but the portfolio keeps filling with medium-quality off-theme names that crowd out dominant-theme leaders.
---

# Sector Concentration

A momentum strategy scores every stock in the universe and picks the top-N. When the universe
is wide and a single macro theme is dominating the market (AI in 2023, energy in 2022, EV in
2020), the scorer often *knows* which stocks are winning — but the score differences are too
small for those winners to reliably take all the top slots. Off-theme stocks with decent
momentum fill positions that should belong to the theme leaders.

The fix is not to tweak the scoring formula. It is to add a **concentration forcing function**:
a mechanism that deliberately pushes the target sector's score above the ambient noise of
competing candidates. This keeps the methodology systematic while expressing a deliberate
directional bet.

This skill explains when concentration helps, which mechanism to use, how to size the boost
calibration, and what to watch for when the approach fails. Backtests don't predict the future;
a concentration tilt that worked historically reflects a view you are explicitly taking — not a
guarantee it repeats.

---

## When concentration solves the right problem

Before adding any tilt, confirm the actual failure mode. Concentration is the right tool when:

1. **The target sector's leaders rank too low in a wide universe.** The score formula is
   working correctly — the theme leaders show genuine momentum — but so do dozens of off-theme
   names, and there aren't enough position slots for all of them. The boosted stocks are being
   crowded out by volume, not by weakness.

2. **You have a forward-looking view on a structural theme.** Concentration is a *view*, not
   a signal. You believe a particular sector will continue to dominate because of identifiable
   catalysts (capex cycles, policy, technological adoption curves). That view deserves to be
   expressed explicitly rather than hoped-for through scoring alone.

Concentration is the *wrong* tool when:
- The theme leaders genuinely score low (momentum hasn't materialized). Boosting a name that
  scores poorly on the underlying formula forces a bad trade rather than captures a good one.
- You are fitting a boost to make historical results look better. This is a design-bias form
  of overfitting (see the [lookahead-audit skill](#) and [anti-overfit skill](#)).

---

## The dilution mechanism: why wide universes suppress theme leaders

Suppose your scoring formula assigns scores in the range 50–100. In a universe of 20 stocks
during a strong sector rally, the theme leaders score 90–95 and easily take all available
position slots. Expand to 80 stocks: the theme leaders still score 90–95, but 15 off-theme
names now score 80–88 from sector-independent momentum (e.g. defensives, value names with
earnings strength). If you have 4 position slots, the 4 slots might now go to the top-4 scores
— which include 1–2 off-theme names pushing out a theme leader.

The score gap between theme leaders and high-quality off-theme stocks is real but narrow. A
small additive boost applied only to the target theme's stocks closes this gap explicitly,
restoring the concentration that was present naturally in the smaller universe.

---

## Mechanism 1: Score boost (additive)

The simplest and most transparent method. When scoring each symbol, add a fixed bonus to every
symbol in the target sector list before the sort:

```python
# Without concentration:
score = compute_momentum_score(symbol, prices, as_of_date)

# With sector concentration:
SECTOR_TILT = {"AAPL", "MSFT", "NVDA"}   # illustrative — user defines these
BOOST_AMOUNT = 10.0                        # illustrative starting point; user must calibrate

score = compute_momentum_score(symbol, prices, as_of_date)
if symbol in SECTOR_TILT:
    score += BOOST_AMOUNT
```

The boost does not change the *relative* order within the sector — it only raises the floor
for every member. Symbols that score poorly on fundamentals remain poor; the boost helps
strong sector members beat similarly-strong off-theme members in the sort.

**Calibrating the boost amount:**
The boost must be large enough to reliably shift the target symbols above competing off-theme
candidates, but not so large that it overrides the scoring entirely and forces entries into
genuinely weak stocks.

A useful calibration process:
1. Record the score distribution on several representative dates during the target theme period.
2. Find the score of the highest-ranked off-theme symbol *not* selected (i.e., just below the
   cut-off). Call this the "competition score."
3. Compute the average gap between the target sector's best stocks and the competition score.
4. Set the boost to roughly 1.5–2x that gap. This gives reliable crowding-out without
   overwhelming the signal entirely.

Start conservatively. A boost that is too small has no effect; a boost that is too large locks
in the theme regardless of what the momentum scores say, which is not systematic investing.

---

## Mechanism 2: Universe filtering (hard inclusion/exclusion)

For a more aggressive tilt, restrict the candidate universe itself to only include the target
sector during a theme period. This is the blunt version: if a symbol is not in the sector
list, it cannot enter.

```python
# Period-aware universe restriction
def get_candidates(as_of_date, full_universe, theme_periods):
    for start, end, sector_symbols in theme_periods:
        if start <= as_of_date < end:
            return [s for s in full_universe if s in sector_symbols]
    return full_universe
```

Hard exclusion is appropriate when the theme is so dominant that broad diversification is
actively harmful — the off-theme names act as return drag rather than risk reduction. It is
also more interpretable: the strategy either trades the theme or does not.

The downside is brittleness. If the theme ends mid-period, the strategy has no fallback and
may sit heavily in weakening names until the period boundary passes.

---

## Mechanism 3: Position caps per sector (diversity constraint)

The inverse of concentration: prevent *over*-concentration by capping the number of positions
any single sector can hold simultaneously. This is useful when you want some concentration but
not a monolithic single-sector portfolio.

```python
MAX_POSITIONS_PER_SECTOR = 2

sector_counts = {}
selected = []
for symbol, score in scored_candidates:
    sec = get_sector(symbol)
    if sector_counts.get(sec, 0) < MAX_POSITIONS_PER_SECTOR:
        selected.append(symbol)
        sector_counts[sec] = sector_counts.get(sec, 0) + 1
    if len(selected) >= max_positions:
        break
```

Use this in combination with a boost (mechanisms 1 and 2) to guarantee both that the target
sector is represented *and* that no single sector fully dominates when the theme is weaker.

---

## The slot competition problem

**This is the most important failure mode.** When you add a concentration tilt, you are not
just changing which stocks enter — you are changing *which slots are occupied*, and that
changes which stocks can enter in all future rebalance windows.

Consider a portfolio capped at 4 positions. If the boost causes symbol A to enter on week 3
instead of symbol B, and symbol A holds its position for 8 weeks, then all the rebalances
during those 8 weeks see only 3 open slots. The composition of competitors for those 3 slots
is now different from the no-boost baseline. Downstream entries that would have filled the
freed-up fourth slot in the baseline now never happen — replaced by whichever candidates ranked
highest when the slot eventually opens.

Consequences to watch for:
- Adding a *fifth* boosted symbol to compete for 4 slots guarantees one theme member is always
  displaced by another theme member. This can be net negative if the displaced symbol was better.
- Cascading effects can propagate months forward: a regime change or stop-loss exit in one
  quarter changes who enters in the next, which changes slot availability in the quarter after.
- Reverting a tilt can cause a regression not because the tilt was good, but because the
  natural alternatives that would have entered without it are worse than you expected.

Before finalizing a boost: run the backtest with and without the boost and examine *which
symbols entered* in each version, not just the aggregate return. Understand the substitution.

---

## Boost size and max-positions interaction

The boost amount is not independent of your max-positions setting. In a 4-position portfolio:

| Boost size | Effect |
|------------|--------|
| Too small  | Theme leaders still crowded out by off-theme candidates |
| Calibrated | Theme leaders reliably take 2–3 of the 4 slots; off-theme fills the rest |
| Too large  | All 4 slots go to theme regardless of individual momentum; no off-theme diversification |
| Extreme    | The boost overrides the scoring entirely — you're no longer doing systematic selection |

A practical rule: if increasing the boost by 50% has no additional effect on slot composition,
the boost is already at its effective ceiling and further increases only increase the risk of
forcing entries in genuinely weak theme members.

---

## Time-bounding the tilt

Sector dominance is transient. A tilt must have an explicit start and end, not an indefinite
"the AI theme is always in effect." Define the window based on identifiable catalysts:

```python
THEME_WINDOWS = [
    # (start_date, end_date, sector_symbols, boost_amount)
    # Dates and symbols below are ILLUSTRATIVE only — user must define from their own research
    ("2023-01-15", "2024-12-31", {"AAPL", "MSFT", "NVDA", "GOOGL"}, 15.0),
]
```

When the window closes, the strategy falls back to its baseline scorer. This prevents the tilt
from staying active indefinitely into a market environment where it no longer applies. It also
makes the design choice auditable: each window has an explicit rationale.

**Design-bias warning:** The start and end dates of a theme window are almost always chosen
with knowledge of when the theme was historically strong. This is a form of hindsight
selection, even when the code is perfectly time-gated. A clean look-ahead audit does not
remove this. Disclose it; it matters for live performance expectations.

---

## Worked micro-example: the crowding-out failure

**Setup:** 80-stock universe, 4 bull-regime slots, momentum scorer range 50–100.

On a given date in an AI-dominated market:
- Theme leader A scores 88
- Theme leader B scores 86
- Off-theme stock C scores 85 (energy sector, strong earnings momentum)
- Off-theme stock D scores 84 (consumer, solid 60-day trend)
- Off-theme stock E scores 83
- Theme leader F scores 82

**Without boost:** Top 4 = A, B, C, D. Theme leaders A and B enter; off-theme C and D take the
remaining 2 slots. Theme leader F (and any other theme stock) is crowded out.

**With boost of 10:** Effective scores: A=98, B=96, C=85, D=84, E=83, F=92. Top 4 = A, B, F,
C. Three theme leaders enter; only one off-theme slot remains. The strategy now captures more
of the theme's upside when the theme is genuinely leading.

**Failure case with boost of 40:** Effective scores: A=128, B=126, F=122, and three other theme
members score 105–115, all above any off-theme stock. All 4 slots go to theme stocks regardless
of individual momentum. If the theme reverses mid-period, the portfolio has no defensive
diversification — every position drawdowns together.

---

## Report structure

When diagnosing or designing a concentration tilt, produce a structured review:

```
# Sector Concentration Review: <strategy name>

## Diagnosis
<Is the problem genuine crowding-out, or are theme leaders scoring weakly?>

## Proposed Tilt
Theme: <sector or theme name>
Mechanism: score_boost | universe_filter | position_cap
Boost amount: <value and rationale>
Time window: <start> to <end>
Affected symbols: <count; do not list unless directly relevant>

## Slot Competition Analysis
<How does adding the tilt change which symbols enter, and when?>
<What is the substitution — what did the new entries replace?>

## Calibration Check
Score distribution at cut-off (representative dates): <p25/p50/p75 of threshold scores>
Theme leader scores before boost: <range>
Gap to competition: <avg>
Boost = ~1.5–2x gap: <calculation>

## Design-Bias Disclosures
<Window dates chosen with hindsight? Symbol selection based on known outcomes?>

## Recommendation
<Boost amount, window, mechanism — plus what to re-run to verify.>
```

---

## Pairing with other skills

- **momentum-scorer** — The boost is additive on top of the base momentum score. Make sure the
  base scorer is sound before adding concentration; a broken scorer amplified by a boost is worse.
- **anti-overfit** — Concentration tilts are a major source of design bias. Use the anti-overfit
  skill to test whether the boost generalizes or only fits the specific historical window.
- **lookahead-audit** — Ensure the sector list and time windows are not themselves contaminated
  by future data (e.g., a universe filtered using today's sector classifications that have been
  revised since the backtest period).
- **revert-discipline** — When a concentration change causes an unexpected regression, use the
  revert-discipline skill before chasing the regression with a compensating adjustment. Slot
  competition effects often make the regression look fixable when it is structural.
- **macro-overlay** — Concentration tilts and macro-event overrides interact through slot
  competition. Coordinate changes to both at the same time and examine downstream effects
  together, not in isolation.


<!-- strongskills-brand -->

---

*Made with a StrongSkills tool — The shortcut to the cutting edge · getstrongskills.com*
