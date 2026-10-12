import json, re, sys, csv
from pathlib import Path
from openpyxl import load_workbook
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

REPO = Path(".")
ROOT = REPO / "ATP TestCase Flows"
OUT = REPO / "reports" / "module_runs" / "full_sheet"
XLSX = Path(r"c:\Users\CA Global\Downloads\Hp new sprocket ATP Sheet.xlsx")

# Index flows by short id from filename (AI_07, FW_01, SE_01, TP_01, CS_02, OSS_03, ON_01, SG_01, AL_01, HM_05, QP_...)
flows_by_id = {}
all_flows = []
for f in ROOT.rglob("*.yaml"):
    if "subflows" in f.parts or "helpers" in f.parts:
        continue
    try:
        # use short path via os to avoid long-path read issues for indexing by name only
        rel = f.relative_to(REPO).as_posix()
    except Exception:
        continue
    all_flows.append(rel)
    stem = f.stem
    # extract leading token like AI_07, AI_43_remove_background, FW_01, SE_01, TP_06A, OSS_03, COX_001, Sp_01, PR_01
    m = re.match(r"^([A-Za-z]+_?\d+[A-Za-z0-9_]*)", stem)
    if m:
        key = m.group(1).upper().replace(" ", "")
        flows_by_id.setdefault(key, rel)
    # also prefix before " - "
    pref = stem.split(" - ")[0].strip().upper().replace(" ", "_")
    flows_by_id.setdefault(pref, rel)

def resolve(*candidates):
    for c in candidates:
        if not c:
            continue
        k = c.upper().replace(" ", "_")
        if k in flows_by_id:
            return flows_by_id[k]
        # try zero-pad variants AI_7 -> AI_07
        m = re.match(r"^([A-Z]+)_?(\d+)([A-Z0-9_]*)$", k)
        if m:
            for width in (2, 3):
                kk = f"{m.group(1)}_{int(m.group(2)):0{width}d}{m.group(3)}"
                if kk in flows_by_id:
                    return flows_by_id[kk]
    return None

# Load Excel IDs
wb = load_workbook(XLSX, data_only=True)
ws = wb["New Sprocket Final ATP"]
def clean(s):
    return ("" if s is None else str(s)).replace("\u2011","-").replace("\u2013","-").strip()

excel_ids = []
for row in ws.iter_rows(min_row=2, max_row=ws.max_row):
    aid = clean(row[0].value)
    if not aid:
        continue
    excel_ids.append({
        "id": aid,
        "module": clean(row[1].value),
        "desc": clean(row[2].value),
    })

# Existing map
old = json.loads((OUT / "excel_flow_map.json").read_text(encoding="utf-8"))
old_map = old.get("map") or {}

HEADER_RE = re.compile(
    r"^(ONBOARDING SPLASH SCREEN|SIGN UP & LOGIN|TILES MODULES|MAIN HOME SCREEN|"
    r"AI TOOLS SDK|HP SPROCKET SENCE 250|PRINT STATE, PRINT QUEUE & PRINT HISTORY|"
    r"BLUETOOTH / HP 600 FIRMWARE UPDATE|CUSTOM SDK|ALERTS?|BLOCKERS?)$",
    re.I,
)

new_map = {}
aliases = {}
still = []
headers = []

for item in excel_ids:
    aid = item["id"]
    if HEADER_RE.match(aid) or (not re.search(r"\d", aid) and len(aid) > 20 and not aid.startswith("PCF")):
        # keep as header skip unless already mapped
        if aid in old_map:
            new_map[aid] = old_map[aid]
        else:
            headers.append(aid)
        continue

    if aid in old_map:
        new_map[aid] = old_map[aid]
        continue

    flow = None
    reason = None

    # AI Tools 07 / AI Tools 07a -> AI_07
    m = re.match(r"(?i)^AI Tools?\s+(\d+[a-z]?)$", aid)
    if m:
        num = m.group(1)
        flow = resolve(f"AI_{num}", f"AI_{num.upper()}")
        # also try AI_07_remove_background style - prefer exact number match files
        if not flow:
            for k,v in flows_by_id.items():
                if re.match(rf"^AI_{num.upper()}(_|$)", k) or re.match(rf"^AI_0*{int(re.match(r'(\d+)', num).group(1))}(_|$)", k) if re.match(r'^\d+$', num) else False:
                    flow = v; break
        reason = "alias AI Tools N -> AI_N"

    # Sp_03 -> ON_01 (Sp_03 welcome = ON_01), Sp_04=ON_02, Sp_05=ON_03, Sp_06=ON_04-ish, Sp_07 privacy, Sp_08 swipe
    m = re.match(r"(?i)^Sp[_\s-]?(\d+)$", aid)
    if m and not flow:
        n = int(m.group(1))
        sp_map = {1:"SP_01", 2:"SP_02", 3:"ON_01", 4:"ON_02", 5:"ON_03", 6:"ON_04", 7:"OSS_08", 8:"ON_05"}
        flow = resolve(sp_map.get(n, f"SP_{n:02d}"), f"SP_{n:02d}", f"ON_{n:02d}")
        reason = "alias Sp_N -> splash/onboarding"

    # SU 01.. -> OSS / SG / LO
    m = re.match(r"(?i)^SU\s*(\d+)$", aid)
    if m and not flow:
        n = int(m.group(1))
        su_map = {
            1: "OSS_03", 2: "OSS_03", 3: "OSS_04", 4: "OSS_04",
            5: "SG_04", 6: "SG_02", 7: "SG_03", 8: "OSS_05",
            9: "OSS_06", 10: "OSS_07", 11: "OSS_08", 12: "OSS_09",
            13: "OSS_10", 14: "OSS_11", 15: "OSS_12", 16: "OSS_13",
            17: "OSS_14", 18: "LO_06", 19: "OSS_15", 20: "OSS_16",
            21: "OSS_17", 22: "OSS_18", 23: "OSS_19", 24: "OSS_20",
            25: "LO_01", 26: "LO_09", 27: "SL_01",
        }
        flow = resolve(su_map.get(n), f"OSS_{n:02d}", f"SG_{n:02d}", f"LO_{n:02d}")
        reason = "alias SU N -> OSS/SG/LO"

    # FW 01 -> FW_01
    m = re.match(r"(?i)^FW\s*(\d+)$", aid)
    if m and not flow:
        flow = resolve(f"FW_{int(m.group(1)):02d}")
        reason = "alias FW N -> FW_NN"

    # Blocker 01 / Stopper 01 -> AL_01
    m = re.match(r"(?i)^(Blocker|Stopper)\s*(\d+)$", aid)
    if m and not flow:
        n = int(m.group(2))
        flow = resolve(f"AL_{n:02d}", f"PS_{n:02d}")
        reason = "alias Blocker/Stopper -> AL"

    # Hamburger Menu_01 / Hamburger Menu_04 (1)
    m = re.match(r"(?i)^Hamburger Menu_(\d+)(?:\s*\((\d+)\))?$", aid)
    if m and not flow:
        n = int(m.group(1))
        sub = int(m.group(2)) if m.group(2) else 0
        # Menu_04 (1)/(2)/(3) are app settings variants -> SE_36/SE_37/SE_38
        if n == 4 and sub:
            flow = resolve(f"SE_{35+sub:02d}", f"SE_{n:02d}")
        else:
            # Hamburger Menu_01 = SE_01, _02 login = SE_04, etc.
            hm = {
                1:"SE_01", 2:"SE_04", 3:"SE_03", 4:"SE_07", 5:"SE_08",
                6:"SE_09", 7:"SE_10", 8:"SE_11", 9:"SE_12", 10:"SE_06",
                11:"SE_13", 12:"SE_14", 13:"SE_15", 14:"SE_16", 15:"SE_18",
                16:"SE_17", 17:"SE_25", 18:"SE_27", 19:"SE_28", 20:"SE_29",
                21:"SE_30", 22:"SE_31", 23:"SE_32", 24:"SE_44", 25:"SE_47",
                26:"SE_48", 27:"SE_49", 28:"SE_50", 29:"SE_51",
            }
            flow = resolve(hm.get(n), f"SE_{n:02d}")
        reason = "alias Hamburger Menu -> SE"

    # Tiles modules 01 -> TP_01
    m = re.match(r"(?i)^Tiles modules?\s*(\d+)$", aid)
    if m and not flow:
        n = int(m.group(1))
        flow = resolve(f"TP_{n:02d}", f"TP_{n:02d}A", f"TP_{n:02d}B")
        reason = "alias Tiles modules -> TP"

    # Custom SDK 02 -> CS_02
    m = re.match(r"(?i)^Custom SDK\s*(\d+)$", aid)
    if m and not flow:
        n = int(m.group(1))
        flow = resolve(f"CS_{n:02d}")
        reason = "alias Custom SDK -> CS"

    # HOME SCREEN_006 -> HM_05 (logged in)
    m = re.match(r"(?i)^HOME SCREEN_(\d+)$", aid)
    if m and not flow:
        n = int(m.group(1))
        flow = resolve(f"HM_{n:02d}", f"HM_05" if n==6 else None)
        reason = "alias HOME SCREEN -> HM"

    # Print Preview_25
    m = re.match(r"(?i)^Print Preview_(\d+)$", aid)
    if m and not flow:
        n = int(m.group(1))
        flow = resolve(f"PR_{n:02d}", f"PP_{n:02d}")
        reason = "alias Print Preview -> PR"

    # Quick print variants
    m = re.match(r"(?i)^QUICK PRINT[_ ]+(\d+[a-z]?)(?:\s*\(([a-z])\))?$", aid)
    if m and not flow:
        n = m.group(1)
        flow = resolve(f"QP_{n}", f"QP_{n.upper()}", f"QP_0{n}" if len(n)<3 else None)
        reason = "alias QUICK PRINT -> QP"
    m = re.match(r"(?i)^Quick print_(\d+)\(([a-z])\)$", aid)
    if m and not flow:
        flow = resolve(f"QP_{m.group(1)}{m.group(2)}", f"QP_00{m.group(1)}{m.group(2)}", f"QP_{int(m.group(1)):03d}{m.group(2)}")
        reason = "alias Quick print -> QP"

    # Video Frame
    m = re.match(r"(?i)^Video [Ff]rame\s*(\d+)$", aid)
    if m and not flow:
        n = int(m.group(1))
        flow = resolve(f"VD_{n:02d}", f"VF_{n:02d}")
        reason = "alias Video Frame -> VD"

    # Precut
    m = re.match(r"(?i)^Precut_(\d+)$", aid)
    if m and not flow:
        flow = resolve(f"PC_{int(m.group(1)):02d}")
        reason = "alias Precut -> PC"

    # PrintState_Tips
    m = re.match(r"(?i)^PrintState_Tips_(\d+)$", aid)
    if m and not flow:
        flow = resolve(f"PS_{int(m.group(1)):02d}", "PS_04")
        reason = "alias PrintState_Tips -> PS"

    # PCF Sense 250 - map to nearest Sense/Select connection flows by suffix number
    if not flow and re.search(r"(?i)sence|sense", aid) and aid.upper().startswith("PCF"):
        m = re.search(r"_(\d+)$", aid)
        n = int(m.group(1)) if m else 0
        # Prefer existing Sense COX if any; else Select equivalents by step number
        sense_flows = [v for k,v in flows_by_id.items() if "SENSE" in k or "SENCE" in k]
        # Map step to Select PCF flows which mirror Sense setup
        # Look for Excel-tagged Sense flows via COX that mention Sense
        candidates = []
        for rel in all_flows:
            low = rel.lower()
            if "sense" in low or "sence" in low:
                candidates.append(rel)
        if candidates:
            # pick by index
            flow = candidates[min(n-1, len(candidates)-1)] if n else candidates[0]
        if not flow:
            # fall back to Select PCF by number: PCF_HPSelect_00N
            flow = None
            for rel in all_flows:
                if f"PCF_HPSelect_{n:03d}" in Path(rel).read_text(encoding="utf-8", errors="replace") if False else False:
                    pass
            # use COX files that have Excel PCF_HPSelect_00N
            sel = resolve(f"COX_{n:03d}")
            # better: scan excel tags in connection folder by reading first 5 lines via shell later
            flow = sel
        reason = "alias PCF Sense -> connection/Sense"

    if flow:
        new_map[aid] = flow
        aliases[aid] = {"flow": flow, "reason": reason}
    else:
        still.append(aid)

print(f"Previously mapped: {len(old_map)}")
print(f"Newly aliased: {len(aliases)}")
print(f"Total mapped now: {len(new_map)}")
print(f"Headers skipped: {len(headers)}")
print(f"Still unmatched: {len(still)}")
print("\nStill list:")
for s in still:
    print(f"  {s}")

# Write updated map
payload = {
    "generated": "alias rematch",
    "matched_count": len(new_map),
    "unmatched_count": len(still),
    "header_count": len(headers),
    "map": new_map,
    "unmatched": still,
    "headers": headers,
    "aliases_added": aliases,
}
(OUT / "excel_flow_map.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
(OUT / "alias_remap_report.json").write_text(json.dumps({"aliases": aliases, "still": still, "headers": headers}, indent=2), encoding="utf-8")
print(f"\nWrote map with {len(new_map)} matched / {len(still)} unmatched")
