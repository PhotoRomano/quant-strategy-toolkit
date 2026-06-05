#!/usr/bin/env python3
"""Generate the Quant Strategy Toolkit Excel templates.

These are human-facing companion workbooks for the skills — the EV planner pairs with
`experiment-design`, the log with `training-log`, the dashboard with `metrics-report`.
They ship with sample rows so a buyer sees how to use them, and live formulas so the
numbers update as they type. Re-run this script any time to regenerate clean copies.

    python3 build_excel.py [output_dir]   # default: ../templates
"""
import sys
from pathlib import Path
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.chart import BarChart, Reference
from openpyxl.utils import get_column_letter

OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent / "templates"
OUT.mkdir(parents=True, exist_ok=True)

INK = "1B2230"; ACC = "5AD6A0"; HEAD = "26304A"; BAND = "F2F5FA"; WARN = "FFF4E0"
thin = Side(style="thin", color="D5DCEA")
BORDER = Border(left=thin, right=thin, top=thin, bottom=thin)

def header(ws, cols, row=1):
    for c, label in enumerate(cols, 1):
        cell = ws.cell(row=row, column=c, value=label)
        cell.font = Font(bold=True, color="FFFFFF", size=11)
        cell.fill = PatternFill("solid", fgColor=HEAD)
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = BORDER
    ws.row_dimensions[row].height = 30

def band(ws, first_data_row, last_row, ncols):
    for r in range(first_data_row, last_row + 1):
        if (r - first_data_row) % 2 == 1:
            for c in range(1, ncols + 1):
                ws.cell(row=r, column=c).fill = PatternFill("solid", fgColor=BAND)
        for c in range(1, ncols + 1):
            ws.cell(row=r, column=c).border = BORDER

def title_block(ws, title, subtitle):
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=8)
    t = ws.cell(row=1, column=1, value=title)
    t.font = Font(bold=True, size=15, color=INK)
    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=8)
    s = ws.cell(row=2, column=1, value=subtitle)
    s.font = Font(italic=True, size=10, color="6B7894")
    ws.row_dimensions[1].height = 22

# ── 1. Experiment Planner ────────────────────────────────────────────────────
def experiment_planner():
    wb = Workbook(); ws = wb.active; ws.title = "EV Planner"
    title_block(ws, "Experiment Planner — Expected Value",
                "Pairs with the experiment-design skill. Rank candidate changes by EV; test the cheapest high-EV idea first.")
    cols = ["Exp ID", "Hypothesis / change", "Category",
            "P(success)", "Upside (pp)", "Downside (pp)", "Expected value (pp)", "Cost to test (1-5)"]
    header(ws, cols, row=4)
    samples = [
        ["T-EX1", "Add release-lag gate to macro overlay", "bias_fix", 0.80, 4.0, 1.5, None, 2],
        ["T-EX2", "Widen bull trailing stop 12%→15%", "param_tune", 0.45, 6.0, 8.0, None, 1],
        ["T-EX3", "Add quality gate to expanded universe", "structural", 0.60, 5.0, 3.0, None, 3],
    ]
    r0 = 5
    for i, row in enumerate(samples):
        r = r0 + i
        for c, v in enumerate(row, 1):
            ws.cell(row=r, column=c, value=v)
        # EV = P*Upside - (1-P)*Downside
        ws.cell(row=r, column=7, value=f"=D{r}*E{r}-(1-D{r})*F{r}")
        ws.cell(row=r, column=4).number_format = "0%"
        for c in (5, 6, 7):
            ws.cell(row=r, column=c).number_format = "0.0"
    band(ws, r0, r0 + 12, len(cols))
    # blank rows for the user
    last = r0 + 12
    widths = [10, 42, 14, 11, 12, 13, 17, 14]
    for c, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(c)].width = w
    # notes
    nr = last + 2
    ws.cell(row=nr, column=1, value="How to use").font = Font(bold=True, color=INK)
    for j, line in enumerate([
        "1. State one hypothesis per row — a single change with a clear mechanism.",
        "2. Estimate P(success) honestly. If you can't name the mechanism, P is lower than you think.",
        "3. Upside/Downside in percentage POINTS of annual return vs. your current baseline.",
        "4. EV computes automatically. Sort by EV, then run the lowest Cost-to-test idea first.",
        "5. Record the actual result in the training-log workbook — predicted vs. realized is where learning lives.",
    ], 1):
        ws.cell(row=nr + j, column=1, value=line).font = Font(size=10, color="44506B")
        ws.merge_cells(start_row=nr + j, start_column=1, end_row=nr + j, end_column=8)
    ws.freeze_panes = "A5"
    wb.save(OUT / "experiment-planner.xlsx")

# ── 2. Training Log ──────────────────────────────────────────────────────────
def training_log():
    wb = Workbook(); ws = wb.active; ws.title = "Training Log"
    title_block(ws, "Training Log — Experiment Journal",
                "Pairs with the training-log skill. One row per experiment run. The predicted-vs-realized gap calibrates your judgment.")
    cols = ["Date", "Exp ID", "Change", "Predicted P", "Reasoning",
            "Result Δ (pp)", "Verdict", "Notes / next"]
    header(ws, cols, row=4)
    samples = [
        ["2026-05-20", "T8", "bull max_position_pct 300%→100%", 0.55, "Overcorrected COVID leverage", -3.0, "REVERT", "Cost more in recovery upside than it saved"],
        ["2026-05-24", "T38", "2023 AI sector_boost +10→+20", 0.75, "Restore concentration in dominant theme", 22.5, "KEEP", "Root cause was list incompleteness"],
    ]
    r0 = 5
    for i, row in enumerate(samples):
        r = r0 + i
        for c, v in enumerate(row, 1):
            ws.cell(row=r, column=c, value=v)
        ws.cell(row=r, column=4).number_format = "0%"
        ws.cell(row=r, column=6).number_format = "+0.0;-0.0"
    band(ws, r0, r0 + 20, len(cols))
    widths = [12, 9, 34, 12, 34, 13, 11, 34]
    for c, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(c)].width = w
    # data validation for Verdict
    from openpyxl.worksheet.datavalidation import DataValidation
    dv = DataValidation(type="list", formula1='"KEEP,REVERT,INCONCLUSIVE"', allow_blank=True)
    ws.add_data_validation(dv); dv.add(f"G{r0}:G{r0+20}")
    ws.freeze_panes = "A5"
    wb.save(OUT / "training-log.xlsx")

# ── 3. Backtest Metrics Dashboard ────────────────────────────────────────────
def metrics_dashboard():
    wb = Workbook(); ws = wb.active; ws.title = "Metrics"
    title_block(ws, "Backtest Metrics Dashboard",
                "Pairs with the metrics-report skill. Enter per-year results; summary stats and the chart update automatically. Numbers below are ILLUSTRATIVE placeholders — replace with your own.")
    cols = ["Year", "Strategy return %", "Benchmark return %", "Max drawdown %", "Trades", "Win rate %"]
    header(ws, cols, row=4)
    # ILLUSTRATIVE placeholder data — clearly not a performance claim
    data = [
        [2019, 12.0, 28.9, -9.0, 30, 60.0],
        [2020, 18.0, 16.3, -12.0, 32, 58.0],
        [2021, 14.0, 26.9, -11.0, 34, 55.0],
        [2022, -6.0, -19.4, -14.0, 38, 45.0],
        [2023, 21.0, 24.2, -10.0, 31, 62.0],
        [2024, 17.0, 23.3, -13.0, 40, 53.0],
    ]
    r0 = 5
    for i, row in enumerate(data):
        for c, v in enumerate(row, 1):
            cell = ws.cell(row=r0 + i, column=c, value=v)
            if c in (2, 3, 4, 6):
                cell.number_format = "0.0"
    nrows = len(data); last = r0 + nrows - 1
    band(ws, r0, last, len(cols))
    # summary block
    sr = last + 2
    ws.cell(row=sr, column=1, value="Summary").font = Font(bold=True, color=INK)
    summ = [
        ("Avg strategy return %", f"=AVERAGE(B{r0}:B{last})", "0.0"),
        ("Avg benchmark return %", f"=AVERAGE(C{r0}:C{last})", "0.0"),
        ("Worst drawdown %", f"=MIN(D{r0}:D{last})", "0.0"),
        ("Avg win rate %", f"=AVERAGE(F{r0}:F{last})", "0.0"),
        ("Years beating benchmark", f"=SUMPRODUCT(--(B{r0}:B{last}>C{r0}:C{last}))", "0"),
    ]
    for j, (label, formula, fmt) in enumerate(summ, 1):
        ws.cell(row=sr + j, column=1, value=label).font = Font(size=10, color="44506B")
        v = ws.cell(row=sr + j, column=2, value=formula); v.number_format = fmt; v.font = Font(bold=True)
    # chart: strategy vs benchmark
    chart = BarChart(); chart.title = "Strategy vs Benchmark (annual return %)"
    chart.type = "col"; chart.style = 10; chart.height = 8; chart.width = 16
    cats = Reference(ws, min_col=1, min_row=r0, max_row=last)
    vals = Reference(ws, min_col=2, max_col=3, min_row=4, max_row=last)
    chart.add_data(vals, titles_from_data=True); chart.set_categories(cats)
    ws.add_chart(chart, f"H4")
    widths = [8, 17, 18, 16, 9, 12]
    for c, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(c)].width = w
    ws.freeze_panes = "A5"
    wb.save(OUT / "backtest-metrics-dashboard.xlsx")

if __name__ == "__main__":
    experiment_planner(); training_log(); metrics_dashboard()
    print("Wrote:")
    for f in sorted(OUT.glob("*.xlsx")):
        print(" ", f.relative_to(OUT.parent), f"({f.stat().st_size} bytes)")
