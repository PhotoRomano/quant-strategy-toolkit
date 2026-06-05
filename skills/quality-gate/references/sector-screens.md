---
title: Sector-Specific Quality Screens
skill: quality-gate
---

# Sector-Specific Quality Screens Reference

This document provides the Layer 3 sector screen logic and the Scalability Sieve scoring
approach referenced from SKILL.md. Use this when you need the detailed mechanics for a
specific sector, not the overview.

## Why sector screens exist

Piotroski and ROIC were calibrated on industrial-era manufacturing companies. Applying
them uniformly across all sectors produces two types of errors:

- **False negatives**: structurally healthy companies penalized for normal sector
  characteristics (e.g., a REIT with high debt/asset ratios that is regulated, not
  distressed; a bank with 1% ROA that is operating normally)
- **False positives**: companies that look healthy on generic metrics but are actually
  deteriorating by the economics that matter for their sector

Layer 3 applies a context-appropriate final check that uses each sector's native
profitability language.

---

## Growth companies: Rule of 40

**Universe target:** Software, SaaS, technology platforms with negative or minimal
dividend yield and high revenue growth.

**Metric:** Revenue growth rate (%) + FCF margin (%)

```
FCF = Operating Cash Flow - |Capital Expenditure|
FCF margin = FCF / Revenue × 100
Rule of 40 score = revenue_growth_pct + fcf_margin_pct
```

**Why this works:** Growth companies often sacrifice margin for growth and vice versa.
The Rule of 40 acknowledges this trade-off by summing the two rates. A company
growing 50% with a -10% FCF margin scores 40 — considered healthy. A company growing
10% with a 30% FCF margin also scores 40.

**Calibration note:** 40 is the commonly cited threshold. On a large-cap-heavy universe
with many mature software companies, the threshold may need raising (e.g. 45–50) to
distinguish genuinely high-quality from merely adequate. On a mid-cap universe, 40 may
already be restrictive. Measure the distribution in your universe first.

**Supplement with Mohanram G-Score** for growth-sector companies. The G-Score tests:
- Positive ROA above a quality floor
- Cash generation quality (CFO/Assets)
- Improving ROA year-over-year
- Cash-backed earnings (CFO > Net Income)
- Growing R&D intensity (innovation reinvestment)
- Growing capex intensity (capacity expansion)
- Positive revenue growth
- Gross margin expansion

A passing G-Score (commonly ≥ 5 out of 8) alongside Rule of 40 > threshold provides
a more complete quality signal for growth companies than either metric alone.

---

## Dividend companies: Chowder Rule

**Universe target:** Utilities, REITs, Consumer Staples, regulated infrastructure — any
company where the return thesis depends significantly on dividend compounding.

**Metric:** Forward dividend yield + 5-year dividend CAGR

```
chowder = dividend_yield_pct + dividend_5yr_cagr_pct
```

**Why this works:** A company with a high yield but shrinking dividend is a value trap.
A company with a low yield but rapid dividend growth will eventually deliver strong
income. The Chowder Rule normalizes across the yield/growth spectrum.

**Calibration note:** The commonly cited threshold is 12 for most dividend companies
and 8 for utilities (which have structurally lower growth). These are starting points;
calibrate against your universe by checking where the distribution separates between
companies that maintained vs. cut their dividend in the following three years.

**Watch for:** Dividend payout ratio above ~80% signals the dividend may not be
sustainable even if current Chowder score looks fine. Consider adding a payout ratio
check as a supplemental condition.

---

## Banks and Financial Services

**Why generic metrics fail:** Banks are leveraged by design. A leverage ratio that
triggers Altman Z distress flags for an industrial company is normal and regulated for
a bank. Piotroski ROA norms (~5–10%) reflect industrial economics; a well-run bank
typically has 0.5–1.5% ROA.

**Layer 3 screen:**

```
ROTCE = Net Income / Tangible Common Equity × 100
Tangible Common Equity = Total Equity - Goodwill - Intangible Assets
(floor TCE at 50% of book equity to avoid divide-by-tiny edge cases)

Revenue growth = (Revenue_current - Revenue_prior) / Revenue_prior × 100
```

Pass condition: ROTCE above a meaningful floor (10% is a common starting point) AND
revenue growth positive (indicating loan book expansion or fee income growth).

**Layer 1 override:** Skip Altman Z and Ohlson O-Score for banks; use only Merton
Distance-to-Default (which is market-implied and not distorted by structural leverage).
Federal and central bank capital requirements substitute for the structural health check.

**Layer 2 override:** For banks with F-Score = 4 (one criterion short), check
whether the interest rate environment is the cause. In a rising-rate environment,
NIM (Net Interest Margin) expands and bank profitability typically improves even as
near-term metrics look compressed. In a falling-rate environment, apply the gate
strictly.

---

## Manufacturers and Industrials

**Why generic metrics may mislead:** Asset-heavy businesses have naturally lower asset
turnover and gross margins than software. High capex is normal, not a warning sign.
The question is not "how big is capex" but "does the model generate real cash after
capex."

**Layer 3 screen:**

```
FCF Margin = (Operating Cash Flow - |Capital Expenditure|) / Revenue × 100
```

Pass condition: FCF margin above a meaningful floor (5% is a common starting point
for diversified industrials; capital-light industrial services may set a higher bar).

**Altman Z:** Use the original 1968 five-factor Z (not Z") for manufacturing and
industrials, since it was calibrated on manufacturing balance sheets.

**Layer 2 override pattern:** Defense and government contractors with contract-driven
billing cycles may show lumpy F-Score results even with healthy operations. Allow
F = 4 when there is verifiable evidence of stable or expanding contract pipeline.
The override requires a concrete signal, not a general sector excuse.

---

## Consumer Cyclicals

**Why the cycle matters:** Automotive, homebuilders, discretionary retail, and similar
businesses swing widely on consumer demand cycles. Evaluating margins at cycle peak
overstates normalized quality; at trough it understates it.

**Layer 3 screen:**

```
Mid-cycle EBIT margin = Average of (EBIT/Revenue) over current and prior year × 100
```

Pass condition: Mid-cycle margin above a floor (8% is a starting point for most
consumer cyclicals; adjust by sub-sector).

**Note:** Two years is a minimal smoothing window. For highly cyclical businesses
(homebuilders, autos), a three- or four-year average is more representative. If your
data source provides this depth, prefer the longer window.

---

## REITs

**Why generic metrics fail:** GAAP depreciation on buildings suppresses reported net
income and ROA even as property values appreciate. Debt/asset ratios are high by
design (REITs are required to distribute 90%+ of taxable income, which forces external
financing). Standard ROE and Piotroski criteria systematically misprice REITs.

**Layer 3 screen:** Prefer FFO Yield (Funds From Operations / Market Cap) and
Net Debt / EBITDA as the primary quality signals. ROTCE (see Banks) also applies
where tangible book equity is defined.

**Layer 2 override:** Allow F = 4 for non-office REITs where GAAP depreciation is
the structural cause of the score shortfall. Office REITs face a secular demand
headwind (remote work) that is operational, not cyclical — do not extend the override.

---

## Pharmaceutical and Biotech

**Why generic metrics fail:** Heavy R&D spend (often 15–25% of revenue for specialty
pharma) appears on the income statement as an expense, suppressing ROA, gross margin,
and net income. But R&D creates pipeline value that GAAP does not capitalize. A pharma
company with 20% R&D/revenue burning through cash to fill a Phase 3 pipeline may be
creating more value than a peer with 5% R&D and stable margins.

**Layer 3:** Use pipeline depth (number of Phase 3 candidates, near-term approval
probability) as the context check, not a financial ratio. This requires a data source
beyond standard financial statements.

**Layer 2 override:** Allow F = 4 and loosen ROIC requirement when R&D intensity is
demonstrably the cause and pipeline depth is meaningful. This requires evidence — a
company with 20% R&D spend but an empty or Phase 1-heavy pipeline does not qualify.

---

## Semiconductor companies

**The inventory cycle:** Memory chip manufacturers (DRAM, NAND) and equipment suppliers
experience demand cycles driven by end-market capex. In a correction year, gross margins
can compress 15–20 percentage points and inventory turnover drops sharply — both of
which fire Piotroski false negatives.

**Layer 2 override:** Allow F = 4 for confirmed memory/equipment companies when a
sector-level inventory correction is the cause. The supporting signal should be
verifiable (e.g., aggregate industry inventory data, sector index cycle signal)
rather than company-specific.

Do not apply the override to fabless design companies, which generally have more
stable margins and are less affected by inventory cycles.

---

## Scalability Sieve

The Scalability Sieve is an optional enrichment layer (not a hard gate) that identifies
businesses with asset-light, high-margin economics — "digital toll booths" that collect
a slice of transactions without proportionally growing their cost base.

**Four pillars:**

| Metric | Formula | Why it matters |
|--------|---------|----------------|
| Gross margin | Gross Profit / Revenue | High margin = pricing power + low COGS per unit |
| Capex intensity | |Capex| / Revenue | Low capex = growth without physical infrastructure |
| Incremental margin | ΔGross Profit / ΔRevenue | Each new revenue dollar: how much becomes profit? |
| Operating leverage | EBIT margin change YoY | Does margin expand as revenue scales? |

**Composite scoring approach:** Weight gross margin most heavily (it is the single most
reliable signal for asset-lightness), then capex intensity, then incremental margin,
then operating leverage. Define "Digital Toll Booth" as businesses scoring above a
composite threshold AND passing gross margin and capex absolute floors.

Example floor values as starting points (tune to your universe):
- Gross margin floor: 55% (below this, the business sells "stuff" more than "access")
- Capex floor: less than 10% of revenue
- Composite score floor: calibrate so that top-quartile asset-light businesses pass

Use Scalability Sieve scores as a ranking bonus in the scoring stage downstream, not
as a binary quality gate — low scalability does not mean low quality (a manufacturer
with 35% gross margins and strong Piotroski is a quality company; it is just not
an asset-light one).
