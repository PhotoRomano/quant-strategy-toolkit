# Quant Strategy Toolkit

**25 Claude skills for building, backtesting, and stress-testing systematic trading strategies — plus the Excel templates, documentation, and an interactive browser to put them to work.**

This is a *methodology* toolkit. It teaches Claude (in Claude Code, or any agent that reads skills)
to do the unglamorous, rigor-heavy parts of quant research that separate a strategy that survives
live from a backtest that only looks good: auditing for look-ahead bias, gating point-in-time data,
walk-forward validation, honest metrics, and disciplined experiment tracking.

It does **not** ship a money-making bot, your-mileage-may-vary "signals," or tuned parameters. It
ships the *process*. You bring the edge; this makes sure the edge is real.

## What's inside

```
skills/        25 skill folders — drop the ones you want into ~/.claude/skills/
templates/     3 Excel workbooks — experiment planner, training log, metrics dashboard
docs/          3 PDFs — methodology whitepaper, getting started, workflow cheat-sheet
interactive/   toolkit-browser.html — searchable map of all 25 skills (open it first)
scripts/       generators for the Excel/PDF assets (regenerate or customize)
```

### The 25 skills, by lifecycle phase

- **Data Integrity & Foundations** — `lookahead-audit`, `survivorship-check`, `point-in-time-fundamentals`, `data-source-reconciler`
- **Signal & Strategy Construction** — `regime-classifier`, `momentum-scorer`, `quality-gate`, `sentiment-overlay`, `macro-overlay`, `sector-concentration`
- **Risk & Position Management** — `regime-position-sizing`, `stop-loss-designer`, `profit-ladder`, `kelly-sizing`, `circuit-breaker`
- **Backtesting & Validation** — `backtest-harness`, `walk-forward-validation`, `execution-realism`, `performance-attribution`, `metrics-report`
- **Research Discipline & Iteration** — `experiment-design`, `training-log`, `revert-discipline`, `strategy-brief`, `anti-overfit`

## Quick start

1. **Open `interactive/toolkit-browser.html`** in any browser — search and filter the skills, copy trigger phrases.
2. **Install a skill:** copy its folder from `skills/` into `~/.claude/skills/`. See `INSTALL.md`.
3. **Use it:** in Claude Code, just describe your task — the skill triggers itself. Start with `lookahead-audit` on an existing backtest.
4. **Track your work** with the Excel templates in `templates/`.

## Important disclaimer

This toolkit is **educational software**, not financial, investment, or trading advice. It makes
**no representation or guarantee of profitability**. Backtested or simulated results do not predict
future performance, and a strategy that passes every check here can still lose money in live markets.
Nothing in this package executes live trades or stores brokerage credentials; any live deployment is
entirely your own responsibility and risk. Trading and investing carry a substantial risk of loss,
including loss of principal. Consult a licensed financial professional before risking capital. The
author accepts no liability for any losses arising from use of this toolkit. See `LICENSE.txt`.


## Using this in Claude vs. any other AI
- **Claude** — drop the skill folder(s) into your Claude environment; they activate automatically when relevant.
- **ChatGPT / Gemini / Copilot / any assistant** — open a skill's `prompt.md` and paste it in as your first message or system prompt. Same method — you just pick when to use it.
