"""Update ATP Excel Quick Print / Print Action rows from Maestro summary."""
import json
import re
from pathlib import Path

import openpyxl
from openpyxl.styles import Font, PatternFill

repo = Path(r"d:\Projects-Meastro\New Sprocket Android")
summary = json.loads(
    (repo / "reports/module_runs/quick-print_summary.json").read_text(encoding="utf-8")
)
status_by_id = {}
for r in summary["rows"]:
    m = re.match(r"^(QP_\d+[a-e]?)", r["flow"], re.I)
    if m:
        status_by_id[m.group(1).upper()] = r["status"]

# Excel case id (normalized) -> Maestro flow id
EXCEL_TO_MAESTRO = {
    "QUICK PRINT _001": "QP_001",
    "QUICK PRINT _002": "QP_002",
    "QUICK PRINT_003 (A)": "QP_003A",
    "QUICK PRINT_003 (B)": "QP_003B",
    "QUICK PRINT_003 (C)": "QP_003C",
    "QUICK PRINT_003 (D)": "QP_003D",
    "QUICK PRINT_004": "QP_004",
    "QUICK PRINT_005 (A)": "QP_005A",
    "QUICK PRINT_005 (B)": "QP_005B",
    "QUICK PRINT_006 (A)": "QP_006A",
    "QUICK PRINT_006 (B)": "QP_006B",
    "QUICK PRINT_006 (C)": "QP_006C",
    "QUICK PRINT_006 (D)": "QP_006D",
    "QUICK PRINT_006 (E)": "QP_006E",
    "QUICK PRINT_07": "QP_007",
    "QUICK PRINT_07 (A)": "QP_007A",
    "QUICK PRINT_07 (B)": "QP_007B",
    "QUICK PRINT_08": "QP_008",
    "QUICK PRINT_08 (A)": "QP_008A",
    "QUICK PRINT_08 (B)": "QP_008B",
    "QUICK PRINT_08 (C)": "QP_008C",
    "QUICK PRINT_09": "QP_009",
    "QUICK PRINT_10": "QP_010",
    "QUICK PRINT_11": "QP_011",
    "QUICK PRINT_12": "QP_012",
    "QUICK PRINT_13 (A)": "QP_013A",
    "QUICK PRINT_13 (B)": "QP_013B",
    "QUICK PRINT_13 (C)": "QP_013C",
    "QUICK PRINT_13 (D)": "QP_013D",
    "QUICK PRINT_14": "QP_014",
    "QUICK PRINT_15": "QP_015",
}

wall = summary.get("total_wall_clock", "")
device = summary.get("device", "ZA222RFQ75")
pf = PatternFill("solid", fgColor="C6EFCE")
ff = PatternFill("solid", fgColor="FFC7CE")

src = Path(r"C:\Users\HP\Downloads\Hp new sprocket ATP Sheet_QuickPrint_Maestro.xlsx")
if not src.exists():
    src = Path(r"C:\Users\HP\Downloads\Hp new sprocket ATP Sheet (1).xlsx")
wb = openpyxl.load_workbook(src)
ws = wb["New Sprocket Final ATP"]

updated = 0
for row in ws.iter_rows(min_row=2, max_row=ws.max_row):
    aid = str(row[0].value or "").strip()
    if not aid:
        continue
    key = re.sub(r"\s+", " ", aid).upper()
    # normalize spaces around underscore variants
    mapped = None
    for excel_key, mid in EXCEL_TO_MAESTRO.items():
        if key == excel_key.upper() or key.replace(" ", "") == excel_key.upper().replace(" ", ""):
            mapped = mid
            break
    if not mapped:
        continue
    st = status_by_id.get(mapped)
    if not st:
        continue
    row[6].value = f"Maestro {st} ({mapped}) on {device}; wall {wall}"
    row[7].value = "Pass" if st == "PASS" else "Fail"
    row[8].value = f"Covered by {mapped}"
    row[9].value = "Maestro"
    updated += 1

# Refresh Quick Print Maestro sheet header timing if present
if "Quick Print Maestro" in wb.sheetnames:
    rs = wb["Quick Print Maestro"]
    rs["A1"] = "Quick Print Maestro execution results"
    rs["A1"].font = Font(bold=True, size=14)

out1 = repo / "reports/module_runs/Hp_Sprocket_ATP_with_QuickPrint_Maestro.xlsx"
out2 = Path(r"C:\Users\HP\Downloads\Hp new sprocket ATP Sheet_QuickPrint_Maestro.xlsx")
wb.save(out1)
wb.save(out2)
print("updated_rows", updated)
print("saved", out1)
print("saved", out2)
