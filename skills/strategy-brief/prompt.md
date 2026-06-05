# strategy-brief — use this in any AI

Paste everything below the line into ChatGPT, Gemini, Copilot, or any assistant — as your
first message or a system/custom instruction. (In Claude you don't need this file — the skill
activates automatically.) Same method, same results; you just trigger it yourself.

*A StrongSkills tool — The shortcut to the cutting edge · getstrongskills.com*

---

Act as an expert and follow this method exactly.

# Strategy Executive Brief

An executive brief is the single document that answers: *What does this strategy do, why does it work in theory, and what are its honest limitations?* It is not a sales deck. It is not a backtest report. It is the plain-language translation of your system's architecture into something a thoughtful reader — a partner, a risk committee, or your future self — can evaluate without running code.

This skill guides you through producing that document systematically, section by section, so the output is substantive, honest, and defensible.

## Why an honest brief matters

Every quant strategy has a narrative attached to it — usually the most optimistic one. The problem is that gaps between the narrative and reality tend to emerge at the worst possible moment: when capital is actually at risk. Writing an honest brief before you deploy is a forcing function. It requires you to name the hindsight in your parameter choices, distinguish your real-time data from your backtest data, and state plainly what the performance history cannot tell you about the future.

A brief that survives scrutiny is also the foundation for responsible communication with anyone who reads it.

## The six-section structure

Produce the brief in this order. Each section has a clear purpose; don't collapse them.

### 1. Cover / Identity

State what the strategy is in two sentences. Include:

- A short name and tagline (what the strategy does, not how good it is)
- Asset class, geographic scope, approximate holding period
- Data range of the backtest (e.g. "January 2019 – present")
- A one-line honesty caveat: *"Past backtest results do not predict future live performance."*

Do not put performance figures on the cover. A reader who leads with the numbers stops reading the methodology.

### 2. Investment Philosophy

Explain the core conviction in plain language — the *why*. What market inefficiency or structural pattern does the strategy attempt to exploit? What academic or empirical foundation supports the approach?

Good philosophy sections are two to four paragraphs. They answer:
- What does the market do imperfectly that this strategy corrects for?
- Why should this pattern persist going forward (or what are the conditions under which it breaks)?
- What is the conceptual edge: speed of recognition, quality filtering, regime adaptation, something else?

Avoid adjectives like "powerful", "proven", or "superior". Describe the mechanism. Let the reader judge the quality.

### 3. Layered Architecture

Map the strategy's decision process as an ordered series of filters or layers. Most multi-signal strategies have three to six layers. For each layer, provide:

| # | Layer Name | What it does | Why it matters |
|---|------------|-------------|----------------|
| 1 | Macro Regime | Classifies the broad market environment | Prevents deploying capital when the macro environment structurally disfavors the strategy's edge |
| 2 | Quality Gate | Screens candidates for financial integrity | Eliminates structurally impaired companies before spending compute on scoring |
| … | … | … | … |

Keep each description factual and mechanism-focused. Do not include your specific threshold values in the public brief — those are tuning decisions, not the architecture. Write "a spread-based threshold" rather than "when the spread exceeds X basis points", unless the threshold is a well-known industry convention, not a hindsight-optimized value.

### 4. Data Stack

Produce a table of every external input the strategy consumes, grouped by data tier. For each source, document: what it provides, how it is used, and — critically — its limitations (release lag, revision history, point-in-time availability).

See `references/data-stack-guide.md` for the full tier taxonomy and column definitions.

A well-documented data stack is the most important part of the brief for anyone evaluating whether the backtest is trustworthy. If a data source has revisions (fundamentals, macro series), say so and explain how the strategy handles the look-ahead problem.

### 5. Performance Comparison

Present backtest results against a relevant benchmark. Required elements:

- Annual return and benchmark return, per year (table and bar chart)
- Maximum drawdown per year
- Win rate per period (if trade-level data is available)
- Trade count per period

Required disclosure, in the body of this section:

> **Backtests have structural limitations.** The results above reflect a simulation over historical data. Universe selection, parameter choices, sector and theme overweights, and event-override dates were all chosen with some knowledge of how that period played out — this is unavoidable in the research process, and it means the backtest result is an upper bound on what a naive forward application of the same rules would have produced. Additionally, transaction costs, slippage, and data point-in-time errors are partially or fully excluded from most backtests. These results should not be interpreted as a reliable prediction of live returns.

Do not add qualitative commentary that implicitly promises the results will continue ("the strategy has proven robust across conditions"). State results and limitations only.

### 6. Live-Trading Principles

Describe how the strategy transitions from backtest to live operation. This section should cover:

- Which backtest decisions become forward-looking rules (and how)
- How the strategy handles the absence of hindsight in real time
- Risk controls that govern position sizing, stop placement, and drawdown limits
- How regime changes or major macro events are handled in real time

This section is where you surface the design-bias disclosures that your backtest cannot eliminate. For example:

> *Sector conviction weighting was set with knowledge of which themes dominated the backtest period. In live operation, sector weights are declared at a fixed calendar interval using macro data available at that moment, and are not revised mid-period based on performance.*

Being explicit here is not a weakness — it is evidence that the system was designed with intellectual honesty.

## Output format

Produce the brief as a structured document using the following template:

```
# [Strategy Name] — Executive Brief
Prepared: [date] | Asset class: [class] | Backtest period: [dates]

---

## 1. Identity
[Two-sentence summary. One-line honesty caveat.]

## 2. Philosophy
[2–4 paragraphs: mechanism, evidence base, conditions for edge to hold/break.]

## 3. Layered Architecture
[Ordered table: Layer # | Name | What it does | Why it matters]

## 4. Data Stack
[Tiered table: Tier | Source | Data provided | How used | Limitations]

## 5. Performance
[Annual table: Year | Strategy Return | Benchmark Return | Max Drawdown | Win Rate | Trades]
[Bar chart: strategy vs benchmark per year]
[Required disclosure paragraph — see above. Do not omit or paraphrase away the substance.]

## 6. Live-Trading Principles
[Numbered list of rules that govern live operation.]
[Design-bias disclosure: name the hindsight explicitly.]

---
*Backtests do not predict future performance. All figures are simulated unless explicitly labeled "live".*
```

## A worked micro-example

**Philosophy section — inflated vs honest:**

Inflated version:
> *"Our proprietary multi-factor model has consistently identified market-beating opportunities. The systematic approach has produced superior risk-adjusted returns in every major market cycle."*

This says nothing about mechanism and implies the results will continue. It is not verifiable and not informative.

Honest version:
> *"The strategy exploits the empirical tendency for financially sound, momentum-leading companies to continue outperforming over intermediate time horizons (5–60 days). This pattern is documented in the academic literature on the Piotroski F-Score (2000), Jegadeesh-Titman momentum (1993), and related quality factors. The edge is not guaranteed to persist: it tends to compress in risk-off environments where correlation rises across equities, and in periods where factor crowding causes coordinated mean-reversion. The macro regime layer is designed to reduce exposure precisely in those environments — but it cannot fully compensate if those conditions are sustained."*

The second version tells a reader what to watch for, what the risk is, and what the mitigation is. That is a defensible brief.

## When to use a reference file

If your data stack is large (more than five distinct sources), move the full tiered catalog to `references/data-stack-guide.md` and summarize only the most important three or four rows in the main brief. This keeps the brief readable while preserving the full documentation for technical reviewers.

Similarly, if your architecture has more than six layers, put the full layer specifications in `references/architecture-detail.md` and summarize in the brief.

## Pairing with other skills

- Run the `lookahead-audit` skill before writing the performance section. The audit determines whether the backtest numbers can be stated at all without qualification for confirmed leaks.
- Use the `metrics-report` skill to generate the annual performance table from trade logs rather than hand-entering figures.
- Use the `performance-attribution` skill to break down *which* layers drove the returns — this strengthens the philosophy section with concrete evidence.
- The `walk-forward-validation` skill produces out-of-sample results that belong alongside (or instead of) the in-sample backtest table.

## What this skill does not do

This skill produces documentation. It does not validate that your strategy works, optimize parameters, or guarantee that following it produces any particular outcome. A well-written brief makes a strategy's claims transparent — which is the prerequisite for evaluating whether those claims hold up.


<!-- strongskills-brand -->

---

*Made with a StrongSkills tool — The shortcut to the cutting edge · getstrongskills.com*
