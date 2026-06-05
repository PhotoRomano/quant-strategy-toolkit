# quality-gate — use this in any AI

Paste everything below the line into ChatGPT, Gemini, Copilot, or any assistant — as your
first message or a system/custom instruction. (In Claude you don't need this file — the skill
activates automatically.) Same method, same results; you just trigger it yourself.

*A StrongSkills tool — The shortcut to the cutting edge · getstrongskills.com*

---

Act as an expert and follow this method exactly.

# Fundamental Quality Gate (Forensic Gauntlet)

A technical signal — momentum, mean reversion, breakout — tells you *when* to act.
A quality gate tells you *which companies are worth acting on at all*.

Running a scoring engine over a raw universe of hundreds of names means
the model will, sooner or later, allocate capital to a company on the verge of
financial distress or one whose earnings are dressed up with accruals. The quality
gate runs before scoring and blocks those candidates from ever entering the pipeline.

The architecture here layers three independent checks. A company must pass all three:

1. **Safety** — Is this business likely to survive the next 12–24 months?
2. **Integrity** — Are the reported earnings real, or are they manufactured by accruals?
3. **Quality** — Is the business actually good, not just alive and honest?

This separation matters. A company can pass Safety (low bankruptcy risk) but fail
Integrity (aggressive accruals). Another can pass both but be a low-quality compounder
not worth holding. Scoring each dimension separately gives you diagnostic power when
a name fails — you know exactly why.

## Why you need an expanded universe

A strict quality gate will pass perhaps 10–25% of any broad universe. If you start with
a narrow hand-picked list of 30 names and the gate passes 5, you have no substitutes.
Your scoring engine then over-concentrates into whatever is available rather than finding
the genuinely best candidate.

The correct workflow is: **wide universe first, then quality filter**. Aim for a
pre-filter universe of several hundred names (e.g. a combined large-cap + mid-cap index),
so that even with a 15% pass rate you still have 30–50 candidates for the scoring stage
to rank. Pair this skill with the `survivorship-check` skill to ensure your universe
itself is point-in-time clean.

## Three-layer architecture

### Layer 1 — Safety (Survival + Integrity)

**Survival sub-layer:** Use 2-of-3 consensus from independent bankruptcy models.
Requiring agreement from multiple models reduces false positives from any single
model's sector blind spots.

| Model | What it measures | Sector notes |
|-------|-----------------|--------------|
| Altman Z / Z" | Working capital, retained earnings, EBIT, equity vs. liabilities | Use the non-manufacturing Z" variant for technology/services; original Z for industrials/materials |
| Ohlson O-Score | Logistic regression probability of bankruptcy | Generally applicable; scale-insensitive |
| Merton Distance-to-Default | Market-implied equity volatility vs. debt face value | Particularly useful for large-caps with liquid options |

Pass condition: at least 2 of 3 models indicate safety. If only 1 model can be
computed (data gaps), require that one to pass. If none can be computed, fail the name.

Important sector adjustments: banks and REITs carry structural leverage that is
regulated and normal — using debt/asset ratios against them fires false positives.
For these sectors, rely primarily on Distance-to-Default (market-implied) and
sector-specific profitability metrics (ROTCE for banks, FFO yield for REITs).
Do not blindly apply industrial-era models across all sectors.

**Integrity sub-layer:** Check earnings quality using accrual-based signals. The logic
is that real earnings are backed by cash; manufactured earnings inflate net income
via working capital movements that haven't been collected.

- **Beneish M-Score** (8-variable): detects revenue inflation, gross margin manipulation,
  asset quality deterioration, and changes in depreciation policy. Values below the
  published threshold are safer; values above suggest manipulation risk. Note that
  high-growth companies legitimately show elevated receivables growth — apply a looser
  threshold for growth sectors to avoid punishing genuine hyper-growth.
- **Sloan Accrual Ratio**: `(Net Income − Operating Cash Flow) / Avg Total Assets`.
  When this is large and positive, most earnings came from balance sheet moves, not cash.
  Hard-fail at extreme values (your starting point for this threshold should be calibrated
  against your universe, not copied from academic papers without adjustment).
- **Dechow RSST**: focuses on net operating asset buildup rather than income-flow
  accruals — a complementary lens. Use as a corroborating signal alongside Sloan;
  avoid making it a standalone hard-fail except at extreme levels.

A stale filing penalty applies if the most recent annual filing is older than roughly
six months — discount survival scores slightly, since you are working with data that
may not reflect current financial condition.

### Layer 2 — Quality (Profitability and Strength)

A company that passes Layer 1 is alive and probably honest. Layer 2 asks: is it
actually a good business?

**Piotroski F-Score** (0–9): nine binary tests covering three dimensions of fundamental
strength. A score of 5 or above signals that the business is improving across most axes.

| Dimension | Criteria |
|-----------|----------|
| Profitability (4 pts) | ROA > 0; CFO > 0; improving ROA YoY; CFO > Net Income (cash-backed) |
| Leverage & Liquidity (3 pts) | Declining long-term debt ratio; improving current ratio; no share dilution |
| Operating Efficiency (2 pts) | Improving gross margin; improving asset turnover |

**ROIC** (Return on Invested Capital): `NOPAT / (Equity + Debt − Cash)`.
This is the most capital-structure-neutral quality signal. A business that earns a
return above its cost of capital is creating value; below it is destroying value even
if EPS looks fine. Skip or loosen for sectors where invested capital is structurally
hard to define (financials, REITs).

**DuPont decomposition** (diagnostic, not a gate): Decompose ROE into
`Net Margin × Asset Turnover × Leverage`. Use this to flag names where ROE looks
good only because leverage is very high while margins are thin — this is a warning
sign, not a pass signal. Emit it as a flag the downstream ranking stage can see.

**Sector-specific quality adjustments:** The Piotroski score was calibrated on
manufacturing-era companies. Several sectors trigger legitimate false negatives:

- *Defense/Government contractors*: milestone billing creates lumpy ROA and asset
  turnover. Allow one criterion short (e.g. F=4) when a verifiable contract
  pipeline is expanding or stable.
- *Pharmaceutical companies*: heavy R&D spend depresses ROA and gross margin even
  as pipeline value compounds. Loosen ROIC requirement and allow F=4 when pipeline
  depth is meaningful.
- *Energy producers*: commodity price cycles compress margins in trough years.
  Allow F=4 when the broader commodity cycle is demonstrably the cause, not
  operational failure.
- *Banks*: Piotroski ROA norms (~5–10%) are calibrated for industrial firms. Bank
  ROA of 0.5–1.5% is healthy; use ROTCE (Return on Tangible Common Equity) instead.
- *Cyclical industrials and semiconductors*: inventory correction cycles and capex
  lumpiness create transient score dips. Allow F=4 with supporting evidence.

The pattern in all these overrides is the same: verify that the cause of the score
shortfall is structural or cyclical, not operational failure. Only apply overrides
with evidence, not as a default pass.

**Growth-stock addendum — Mohanram G-Score**: For growth-sector companies,
Piotroski alone is insufficient because it was designed for value stocks. Supplement
with the Mohanram G-Score (0–8), which tests R&D intensity, capex investment, revenue
growth, and earnings quality together. Require G >= 5 for growth-sector names.

### Layer 3 — Sector Context

Apply a context-appropriate final check that matches how the sector's economics work.
The details are in `references/sector-screens.md`; the types are:

- **Growth companies**: Rule of 40 (revenue growth % + FCF margin % >= 40 is a
  reasonable starting threshold; tune for your universe).
- **Dividend companies**: Chowder Rule (dividend yield + 5-year dividend growth CAGR;
  a combined score above some threshold signals sustainable income compounding).
- **Banks**: ROTCE > a reasonable floor (10% is a common starting point) plus
  positive revenue growth.
- **Manufacturers/Industrials**: FCF margin (Operating CF minus Capex, divided by
  revenue) above a meaningful floor (5% is a starting point) — proves the asset-heavy
  model generates real cash.
- **Cyclical consumer**: Normalize operating margin across two years to smooth the
  cycle peak/trough.

The right thresholds for your strategy come from calibration, not from first principles.
Start with conservative defaults, measure the pass rate across your full universe, and
adjust until you get a manageable funnel (15–25% pass rate is typical).

## Optional enrichment layers

After the three core layers, two informational overlays can enrich ranking without
acting as hard gates:

- **Greenblatt Magic Formula** (Earnings Yield + Magic ROIC): Stocks that score high
  on both are cheap *and* high-quality. Use as a ranking bonus, not a binary pass/fail.
- **Scalability Sieve**: Gross margin, capex intensity, incremental margin, and
  operating leverage combine to identify "digital toll booth" businesses — asset-light
  models that grow revenue without growing costs. High-scalability companies tend to
  sustain quality scores over time; low-scalability companies face margin compression
  as they grow. See `references/sector-screens.md` for the scoring approach.

## Report structure

ALWAYS produce the gate output in this format:

```
# Quality Gate Report: <universe name or run ID>

## Summary
Total evaluated: N   Passed: N (xx%)   Failed: N
Layer 1 failures: N-survival  N-integrity
Layer 2 failures: N
Layer 3 failures: N

## Passed Names
| Symbol | Sector | F-Score | ROIC% | Layer1 | Layer2 | Layer3 | Notes |
|--------|--------|---------|-------|--------|--------|--------|-------|

## Failed Names (with first failure reason)
| Symbol | Failed Layer | Key Signal | Value | Threshold |
|--------|-------------|------------|-------|-----------|

## Sector Override Summary
| Symbol | Override Type | Trigger Condition | Evidence |

## Calibration Flags
<Any dimension where >50% of a sector failed the same criterion — may indicate a
threshold calibration issue rather than a universe quality problem.>
```

## A worked micro-example

**Situation:** You have a momentum strategy. Two candidates both show strong price
breakouts. Candidate A passes all three layers. Candidate B has a Piotroski F-Score
of 3 (failing Layer 2) and a Sloan Accrual Ratio of +0.28 (near the hard-fail
threshold).

**Without the quality gate:**
```python
# raw scoring — both candidates score 78/100 on momentum
top_candidates = momentum_score(universe)[:10]
# Both A and B are in the top 10. Position is allocated equally.
```

**With the quality gate:**
```python
# quality filter runs first
approved = quality_gate(universe)          # B fails Layer 2 (F=3) + elevated accruals
top_candidates = momentum_score(approved)[:10]
# Only A advances. The capital that would have gone to B is allocated to the next
# best quality-approved candidate.
```

The value of this discipline: momentum in a company with deteriorating fundamentals
often resolves to the downside when the next earnings report lands. The quality gate
does not predict direction — it removes names where the reported foundation of the
move is structurally weak.

Backtests without any quality filter will generally show better raw returns than
backtests with one, because the filter removes some big short-term winners. This is
not an argument against the filter — it is the filter working as designed, reducing
exposure to companies where the "win" relies on fundamentals the market hasn't yet
penalized. Live trading resolves this ambiguity quickly.

## Caching and refresh strategy

Quality metrics computed from annual filings change slowly, but earnings events change
them materially. A 7-day cache is reasonable for most runs. Invalidate the cache
after earnings releases — post-earnings financials can shift Piotroski by 2–3 points
and swing Beneish meaningfully. Track the next earnings date per symbol and force
a recompute in the window after it passes.

## Calibration workflow

After your first run over a new universe:

1. Check the pass rate by sector. A sector with a 0% pass rate almost certainly has
   a threshold miscalibrated for that sector's structure, not a genuinely broken sector.
2. Review F-Score distributions. If your median F-Score across a sector is 4.2 but
   your threshold is 5, you are near the distribution mean — a minor threshold
   change has outsized impact on pass rates.
3. Track false negatives over time: names that failed the gate but subsequently
   showed strong fundamentals. These point to where sector overrides or threshold
   adjustments are warranted.

Pair with the `backtest-harness` skill to validate that quality-gated backtests
diverge from ungated ones in the expected direction (lower peak returns, reduced
catastrophic drawdowns). Pair with `lookahead-audit` to confirm that your fundamental
data pulls are point-in-time clean — a quality gate built on restated financials is
not a quality gate, it is a hindsight filter.

Backtests are not guarantees of future results. Quality gates reduce exposure to
structurally weak companies; they do not eliminate market risk or guarantee that
passing companies will perform.


<!-- strongskills-brand -->

---

*Made with a StrongSkills tool — The shortcut to the cutting edge · getstrongskills.com*
