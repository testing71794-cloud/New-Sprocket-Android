import json
import re
from pathlib import Path

repo = Path(r"d:\Projects-Meastro\New Sprocket Android")
s = json.loads(
    (repo / "reports/module_runs/quick-print_summary.json").read_text(encoding="utf-8")
)
status = {}
for r in s["rows"]:
    m = re.match(r"^(QP_\d+[a-e]?)", r["flow"], re.I)
    if m:
        status[m.group(1).upper()] = r["status"]

excel_path = repo / "ATP TestCase Flows/quick-print/CHECKLIST_EXCEL.md"
old = excel_path.read_text(encoding="utf-8")
out = [
    "# Quick Print — Excel ATP (31 cases)\n",
    f"## Execution summary ({s.get('device')})",
    f"- **Result:** {s['passed']}/{s['total']} PASS ({s['pass_percent']}%)",
    f"- **Full suite time:** {s.get('full_suite_execution_time_sec')} s",
    f"- **Retry failed time:** {s.get('retry_failed_execution_time_sec')} s",
    f"- **Total wall clock:** **{s.get('total_wall_clock')}** ({s.get('total_wall_clock_sec')} s)",
    "- **Report:** `reports/module_runs/quick-print_execution_report.xlsx`",
    "",
]
for line in old.splitlines():
    m = re.match(r"- \[[ x]\] (QP_\d+[a-e]?)\s*$", line, re.I)
    if not m:
        continue
    qid = m.group(1).upper()
    st = status.get(qid, "UNKNOWN")
    mark = "x" if st == "PASS" else " "
    out.append(f"- [{mark}] {qid} | **{st}**")

fails = [r for r in s["rows"] if r["status"] != "PASS"]
out.append("\n## Failures after retry\n")
for r in fails:
    out.append(f"- `{r['flow']}`: {(r.get('failure_reason') or '')[:240]}")
excel_path.write_text("\n".join(out) + "\n", encoding="utf-8")
print("wrote", excel_path)
