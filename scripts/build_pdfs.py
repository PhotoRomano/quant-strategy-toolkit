#!/usr/bin/env python3
"""Generate the Quant Strategy Toolkit PDF documentation (human-facing).

Three documents:
  - methodology-whitepaper.pdf : the philosophy and the honesty discipline
  - getting-started.pdf        : install + first-hour walkthrough
  - workflow-cheatsheet.pdf    : one-page printable lifecycle map

Honest by design: no performance claims, disclaimer on every doc. Re-run anytime.

    python3 build_pdfs.py [output_dir]   # default: ../docs
"""
import sys
from pathlib import Path
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
                                HRFlowable, PageBreak, ListFlowable, ListItem)
from reportlab.lib.enums import TA_CENTER

OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent / "docs"
OUT.mkdir(parents=True, exist_ok=True)

INK = colors.HexColor("#1B2230"); ACC = colors.HexColor("#1f9d6b")
MUT = colors.HexColor("#5b6b86"); LINE = colors.HexColor("#c9d3e6")

ss = getSampleStyleSheet()
H1 = ParagraphStyle("H1", parent=ss["Title"], textColor=INK, fontSize=24, leading=28, spaceAfter=6)
EY = ParagraphStyle("EY", parent=ss["Normal"], textColor=ACC, fontSize=10, leading=12,
                    spaceAfter=2, fontName="Helvetica-Bold")
H2 = ParagraphStyle("H2", parent=ss["Heading2"], textColor=INK, fontSize=14, leading=18,
                    spaceBefore=14, spaceAfter=4)
BODY = ParagraphStyle("BODY", parent=ss["Normal"], textColor=INK, fontSize=10.5, leading=15, spaceAfter=6)
SMALL = ParagraphStyle("SMALL", parent=ss["Normal"], textColor=MUT, fontSize=8.5, leading=11)
CODE = ParagraphStyle("CODE", parent=ss["Code"], fontSize=9, leading=12, textColor=INK,
                      backColor=colors.HexColor("#eef2f9"), borderPadding=6, spaceAfter=6)
CENTER = ParagraphStyle("CENTER", parent=BODY, alignment=TA_CENTER)

DISCLAIMER = ("<b>Disclaimer.</b> Educational software only — not financial, investment, or trading "
              "advice. No guarantee of profitability. Backtested results do not predict future "
              "performance; a strategy that passes every check here can still lose money live. No live "
              "trades are placed and no credentials are stored. Trading carries substantial risk of loss. "
              "Consult a licensed professional before risking capital. See LICENSE.txt.")

def disclaimer_table(doc_width):
    p = Paragraph(DISCLAIMER, SMALL)
    t = Table([[p]], colWidths=[doc_width])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#fff7ea")),
        ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#e3c486")),
        ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING", (0, 0), (-1, -1), 10), ("RIGHTPADDING", (0, 0), (-1, -1), 10),
    ]))
    return t

def doc(path, title):
    d = SimpleDocTemplate(str(path), pagesize=letter,
                          topMargin=0.8 * inch, bottomMargin=0.7 * inch,
                          leftMargin=0.85 * inch, rightMargin=0.85 * inch, title=title)
    return d, d.width

def bullets(items):
    return ListFlowable([ListItem(Paragraph(t, BODY), leftIndent=8) for t in items],
                        bulletType="bullet", start="•", leftIndent=14)

# ── 1. Methodology Whitepaper ────────────────────────────────────────────────
def whitepaper():
    d, W = doc(OUT / "methodology-whitepaper.pdf", "Quant Strategy Toolkit — Methodology")
    s = []
    s += [Paragraph("QUANT STRATEGY TOOLKIT", EY),
          Paragraph("The Methodology", H1),
          Paragraph("Why most backtests lie, and the discipline that keeps yours honest.", BODY),
          HRFlowable(width="100%", color=LINE, spaceBefore=6, spaceAfter=10)]
    s += [Paragraph("The core problem", H2),
          Paragraph("Most trading backtests are wrong in the same direction: they look better than "
                    "reality. Two forces cause it. First, <b>look-ahead bias</b> — the code uses "
                    "information that wasn't available at the moment of the decision. Second, "
                    "<b>design bias</b> — the human chose the universe, parameters, and rules already "
                    "knowing how history turned out. The first is a bug you can fix; the second is a "
                    "trap you can only disclose. This toolkit is built around taking both seriously.", BODY)]
    s += [Paragraph("The five phases", H2),
          Paragraph("The 25 skills map to the lifecycle of a serious quant research process. Each phase "
                    "exists to catch a specific way strategies fool their builders.", BODY)]
    phases = [
        ["Phase", "What it protects against"],
        ["Data Integrity & Foundations", "Future-data leakage, survivorship, restated fundamentals, feed mismatch"],
        ["Signal & Strategy Construction", "Signals that look predictive only because of leakage or hindsight"],
        ["Risk & Position Management", "Sizing and stops that flatter returns but blow up live"],
        ["Backtesting & Validation", "In-sample fantasy, unrealistic fills, returns you can't explain"],
        ["Research Discipline & Iteration", "Curve-fitting, p-hacking, and forgetting what you already tried"],
    ]
    t = Table(phases, colWidths=[2.2 * inch, W - 2.2 * inch])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), INK), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("FONTSIZE", (0, 0), (-1, -1), 9.5),
        ("GRID", (0, 0), (-1, -1), 0.5, LINE), ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f2f5fa")]),
        ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
    ]))
    s += [t, Spacer(1, 10)]
    s += [Paragraph("The honesty principle", H2),
          Paragraph("This toolkit deliberately refuses to sell a number. There is no \"this returns X%\" "
                    "anywhere in it, because such a number would be a hindsight artifact, not a forecast. "
                    "Instead it sells <i>rigor</i>: the ability to know whether a result is real. The two "
                    "flagship skills — <b>lookahead-audit</b> and <b>anti-overfit</b> — exist precisely to "
                    "tell you the uncomfortable truth before the market does.", BODY),
          Paragraph("A clean audit is not a profit guarantee. It only means your backtest didn't cheat. "
                    "That is a far more valuable thing to own than a pretty equity curve.", BODY)]
    s += [Paragraph("How the pieces fit", H2),
          bullets([
              "<b>Skills</b> (markdown) teach Claude each task — install them into <font face='Courier'>~/.claude/skills/</font>.",
              "<b>Excel templates</b> turn three skills into living worksheets: the EV planner, the training log, the metrics dashboard.",
              "<b>This documentation</b> and the interactive browser orient you and anyone you share the work with.",
          ])]
    s += [Spacer(1, 14), disclaimer_table(W)]
    d.build(s)

# ── 2. Getting Started ───────────────────────────────────────────────────────
def getting_started():
    d, W = doc(OUT / "getting-started.pdf", "Quant Strategy Toolkit — Getting Started")
    s = []
    s += [Paragraph("QUANT STRATEGY TOOLKIT", EY), Paragraph("Getting Started", H1),
          Paragraph("From zip to your first honest audit in under an hour.", BODY),
          HRFlowable(width="100%", color=LINE, spaceBefore=6, spaceAfter=10)]
    s += [Paragraph("1 · Look around", H2),
          Paragraph("Open <font face='Courier'>interactive/toolkit-browser.html</font> in any browser. "
                    "It's a searchable map of all 25 skills, grouped by phase, with a \"use when\" line and "
                    "a copy-trigger button for each. This is the fastest way to learn what's in the box.", BODY)]
    s += [Paragraph("2 · Install a skill", H2),
          Paragraph("Skills are just folders with a SKILL.md. Copy the ones you want into your Claude "
                    "skills directory:", BODY),
          Paragraph("cp -R skills/lookahead-audit ~/.claude/skills/<br/>"
                    "# or the whole stack:<br/>cp -R skills/* ~/.claude/skills/", CODE),
          Paragraph("Restart Claude Code. Tip: install only what your current project needs — skills use a "
                    "little context just by being available.", BODY)]
    s += [Paragraph("3 · Run your first audit", H2),
          Paragraph("The best first move is to point <b>lookahead-audit</b> at a backtest you already have:", BODY),
          Paragraph("\"Use the lookahead-audit skill on my backtest in backtest.py — "
                    "is it leaking future data?\"", CODE),
          Paragraph("You'll get a structured report: a data inventory, any confirmed leaks with fixes, and "
                    "— importantly — a separate section for design-bias choices that a code audit can't fix "
                    "but you should disclose.", BODY)]
    s += [Paragraph("4 · Build the habit", H2),
          bullets([
              "Before each strategy change, fill a row in <font face='Courier'>templates/experiment-planner.xlsx</font> (pairs with the <b>experiment-design</b> skill).",
              "After each run, log predicted-vs-actual in <font face='Courier'>templates/training-log.xlsx</font> (pairs with <b>training-log</b>).",
              "Summarize honestly with <font face='Courier'>templates/backtest-metrics-dashboard.xlsx</font> (pairs with <b>metrics-report</b>).",
              "When results look too good, run <b>anti-overfit</b> before you celebrate.",
          ])]
    s += [Paragraph("5 · Suggested learning path", H2),
          Paragraph("lookahead-audit → backtest-harness → regime-classifier → quality-gate → "
                    "regime-position-sizing → walk-forward-validation → anti-overfit. Add the rest as your "
                    "strategy grows.", BODY)]
    s += [Spacer(1, 14), disclaimer_table(W)]
    d.build(s)

# ── 3. Workflow Cheat-Sheet (one page) ───────────────────────────────────────
def cheatsheet():
    d, W = doc(OUT / "workflow-cheatsheet.pdf", "Quant Strategy Toolkit — Cheat Sheet")
    s = []
    s += [Paragraph("QUANT STRATEGY TOOLKIT — WORKFLOW CHEAT SHEET", EY), Spacer(1, 4),
          HRFlowable(width="100%", color=LINE, spaceAfter=8)]
    groups = [
        ("A · Data Integrity & Foundations", "#1f9d6b",
         ["lookahead-audit", "survivorship-check", "point-in-time-fundamentals", "data-source-reconciler"]),
        ("B · Signal & Strategy Construction", "#2f6fd0",
         ["regime-classifier", "momentum-scorer", "quality-gate", "sentiment-overlay", "macro-overlay", "sector-concentration"]),
        ("C · Risk & Position Management", "#c98a2a",
         ["regime-position-sizing", "stop-loss-designer", "profit-ladder", "kelly-sizing", "circuit-breaker"]),
        ("D · Backtesting & Validation", "#8a4fd0",
         ["backtest-harness", "walk-forward-validation", "execution-realism", "performance-attribution", "metrics-report"]),
        ("E · Research Discipline & Iteration", "#d0506a",
         ["experiment-design", "training-log", "revert-discipline", "strategy-brief", "anti-overfit"]),
    ]
    rows = []
    for title, hexc, skills in groups:
        rows.append([Paragraph(f"<b>{title}</b>", ParagraphStyle("g", parent=BODY, textColor=colors.HexColor(hexc), fontSize=11))])
        rows.append([Paragraph("  •  " + "   •  ".join(skills), BODY)])
    t = Table(rows, colWidths=[W])
    t.setStyle(TableStyle([
        ("LINEBELOW", (0, 1), (-1, 1), 0.4, LINE), ("LINEBELOW", (0, 3), (-1, 3), 0.4, LINE),
        ("LINEBELOW", (0, 5), (-1, 5), 0.4, LINE), ("LINEBELOW", (0, 7), (-1, 7), 0.4, LINE),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("LEFTPADDING", (0, 0), (-1, -1), 2),
    ]))
    s += [t, Spacer(1, 8)]
    s += [Paragraph("The loop", H2),
          Paragraph("1. <b>Audit data</b> (A) → 2. <b>Build signal &amp; risk</b> (B, C) → "
                    "3. <b>Backtest &amp; validate</b> (D) → 4. <b>Plan the next experiment, log it, "
                    "guard against overfit</b> (E) → repeat. Never trust a result you haven't audited (A) "
                    "and stress-tested for overfit (anti-overfit).", BODY)]
    s += [Paragraph("Golden rules", H2),
          bullets([
              "At every decision date, use only data knowable on that date.",
              "If you can't name the mechanism, your P(success) is lower than you think.",
              "A clean backtest is necessary, never sufficient — design bias survives audits.",
              "Sell rigor, not returns. Never trust (or publish) a number from a leaky backtest.",
          ])]
    s += [Spacer(1, 10), disclaimer_table(W)]
    d.build(s)

if __name__ == "__main__":
    whitepaper(); getting_started(); cheatsheet()
    print("Wrote:")
    for f in sorted(OUT.glob("*.pdf")):
        print(" ", f.relative_to(OUT.parent), f"({f.stat().st_size} bytes)")
