import json, re, csv, sys
from pathlib import Path
from openpyxl import load_workbook
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

REPO = Path(".")
ROOT = REPO / "ATP TestCase Flows"
OUT = REPO / "reports" / "module_runs" / "full_sheet"
XLSX = Path(r"c:\Users\CA Global\Downloads\Hp new sprocket ATP Sheet.xlsx")

def clean(s):
    return ("" if s is None else str(s)).replace("\u2011","-").replace("\u2013","-").strip()

def norm_id(s):
    s = clean(s)
    s = s.replace("\u00a0", " ")
    return re.sub(r"\s+", " ", s).strip()

# ---- index all flow files by relative path existence ----
def _exists(path: Path) -> bool:
    try:
        if path.is_file():
            return True
    except OSError:
        pass
    try:
        import os
        return os.path.isfile("\\\\?\\" + str(path.resolve()))
    except OSError:
        return False


def resolve_flow(rel):
    if not rel:
        return None
    rel = rel.replace("\\", "/").lstrip("./")
    # mapping csv often has module-relative paths like ai/AI_02...
    candidates = [
        REPO / rel,
        ROOT / rel,
        REPO / "ATP TestCase Flows" / rel,
    ]
    # if path already includes ATP TestCase Flows
    for c in candidates:
        if _exists(c):
            return c.relative_to(REPO).as_posix()
    # try by filename only
    name = Path(rel).name
    hits = list(ROOT.rglob(name))
    hits = [h for h in hits if "subflows" not in h.parts]
    if len(hits) == 1:
        return hits[0].relative_to(REPO).as_posix()
    # try by short id prefix when long names were shortened
    m = re.match(r"^([A-Za-z]+_?\d+[A-Za-z0-9_]*)", name)
    if m:
        pref = m.group(1)
        hits = [h for h in ROOT.rglob(f"{pref}*.yaml") if "subflows" not in h.parts]
        if len(hits) == 1:
            return hits[0].relative_to(REPO).as_posix()
        # prefer exact AI_07 - *.yaml over AI_07a
        exact = [h for h in hits if h.stem.upper().startswith(pref.upper() + " -") or h.stem.upper() == pref.upper()]
        if exact:
            return exact[0].relative_to(REPO).as_posix()
    return None

# ---- 1) CSV mappings ----
excel_to_flow = {}
csv_hits = 0
for csv_path in ROOT.rglob("atp_*_mapping.csv"):
    try:
        with csv_path.open(encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                eid = norm_id(row.get("ExcelID") or row.get("Excel Id") or row.get("excel_id") or "")
                flow = row.get("FlowFile") or row.get("Flow") or row.get("flow") or ""
                if not eid or not flow:
                    continue
                # relative to module folder often
                mod_dir = csv_path.parent
                # FlowFile like ai/AI_02... or just AI_02...
                resolved = resolve_flow(flow)
                if not resolved:
                    resolved = resolve_flow(str((mod_dir / Path(flow).name).relative_to(REPO)).replace("\\","/")) if (mod_dir / Path(flow).name).is_file() else None
                if not resolved and (mod_dir / Path(flow).name).is_file():
                    resolved = (mod_dir / Path(flow).name).relative_to(REPO).as_posix()
                if resolved:
                    excel_to_flow[eid] = resolved
                    csv_hits += 1
    except Exception as e:
        print("CSV err", csv_path, e)

print(f"CSV mappings loaded: {csv_hits} rows, unique excel ids: {len(excel_to_flow)}")

# ---- 2) Excel tags in yaml (read first 8 lines only via binary to avoid long path issues) ----
tag_hits = 0
for f in ROOT.rglob("*.yaml"):
    if "subflows" in f.parts or "helpers" in f.parts:
        continue
    try:
        # Windows long path prefix
        p = str(f)
        if not p.startswith("\\\\?\\"):
            p = "\\\\?\\" + str(f.resolve())
        with open(p, "r", encoding="utf-8", errors="replace") as fh:
            head = "".join([fh.readline() for _ in range(12)])
    except Exception:
        continue
    for m in re.finditer(r"(?im)^\s*#\s*Excel:\s*([^|\n]+)", head):
        eid = norm_id(m.group(1))
        if eid and eid not in excel_to_flow:
            excel_to_flow[eid] = f.relative_to(REPO).as_posix()
            tag_hits += 1
        elif eid and eid in excel_to_flow:
            pass
print(f"New from Excel tags: {tag_hits}")

# ---- 3) Index flows by short id ----
flows_by_id = {}
all_rels = []
for f in ROOT.rglob("*.yaml"):
    if "subflows" in f.parts or "helpers" in f.parts:
        continue
    rel = f.relative_to(REPO).as_posix()
    all_rels.append(rel)
    pref = f.stem.split(" - ")[0].strip().upper().replace(" ", "_")
    flows_by_id.setdefault(pref, rel)
    m = re.match(r"^([A-Za-z]+_?\d+[A-Za-z0-9_]*)", f.stem)
    if m:
        flows_by_id.setdefault(m.group(1).upper(), rel)

def resolve_id(*cands):
    for c in cands:
        if not c:
            continue
        k = str(c).upper().replace(" ", "_")
        if k in flows_by_id:
            return flows_by_id[k]
        m = re.match(r"^([A-Z]+)_?(\d+)([A-Z0-9_]*)$", k)
        if m:
            for w in (2, 3):
                kk = f"{m.group(1)}_{int(m.group(2)):0{w}d}{m.group(3)}"
                if kk in flows_by_id:
                    return flows_by_id[kk]
            # also without underscore AI07
            kk2 = f"{m.group(1)}{int(m.group(2)):02d}{m.group(3)}"
            if kk2 in flows_by_id:
                return flows_by_id[kk2]
    return None

# ---- 4) Recover from running summary (560 map) ----
summary = json.loads((OUT / "full_sheet_summary.json").read_text(encoding="utf-8"))
for row in summary.get("rows") or []:
    eid = norm_id(row.get("excel_id"))
    flow = row.get("flow")
    if eid and flow and Path(flow).name:
        resolved = resolve_flow(flow)
        if resolved:
            excel_to_flow[eid] = resolved

# Also from logs directory names - skip

# ---- 5) Load all Excel IDs ----
wb = load_workbook(XLSX, data_only=True)
ws = wb["New Sprocket Final ATP"]
excel_rows = []
for row in ws.iter_rows(min_row=2, max_row=ws.max_row):
    aid = norm_id(row[0].value)
    if not aid:
        continue
    excel_rows.append({"id": aid, "module": clean(row[1].value), "desc": clean(row[2].value)})

HEADER_RE = re.compile(
    r"^(ONBOARDING SPLASH SCREEN|SIGN UP & LOGIN|TILES MODULES|MAIN HOME SCREEN|"
    r"AI TOOLS SDK|HP SPROCKET SENCE 250|PRINT STATE, PRINT QUEUE & PRINT HISTORY|"
    r"BLUETOOTH / HP 600 FIRMWARE UPDATE|CUSTOM SDK|QUICK PRINT|COLLAGE|PRECUT|"
    r"VIDEO FRAMES|PRINT PREVIEW|PHOTOBOOTH|PHOTO ID|HP600 connection flow|"
    r"Stopper error|Blockers|"
    r"HUMBURGER MENU.*)$",
    re.I,
)

# Explicit Excel ID → flow id overrides for naming mismatches
EXPLICIT_ALIASES = {
    "Quick print_005(c)": "QP_005b",
    "QUICK PRINT_16": "VD_01",
    "Print Preview_25": "PQ_20",
    "Print_State_28": "PS_27",
    "Video Frame 12": "VD_12",
    "Video frame 12": "VD_12",
}

def alias_flow(aid):
    if aid in EXPLICIT_ALIASES:
        return resolve_id(EXPLICIT_ALIASES[aid])

    # Hamburger Menu_06 (1) (A) / Hambiurger Menu_06 (1) ( E) (Excel typos)
    m = re.match(
        r"(?i)^Hamb\w*rger Menu_(\d+)\s*\(\s*(\d+)\s*\)\s*\(\s*([A-Za-z])\s*\)$",
        aid,
    )
    if m:
        n, letter = int(m.group(1)), m.group(3).upper()
        if n == 6:
            letter_map = {"A": "SE_53", "B": "SE_54", "C": "SE_55", "D": "SE_56", "E": "SE_57"}
            return resolve_id(letter_map.get(letter), "SE_09")

    # AI Tools 07 / AI Tools 05 (a)
    m = re.match(r"(?i)^AI Tools?\s+(\d+)\s*(?:\(([a-z])\))?$", aid)
    if m:
        n, suf = int(m.group(1)), (m.group(2) or "").lower()
        key = f"AI_{n:02d}{suf}" if suf else f"AI_{n:02d}"
        # Prefer exact AI_NN over AI_NN_remove_object when no suffix
        hit = resolve_id(key, f"AI_{n}{suf}", f"AI_{n:02d}_{suf}" if suf else None)
        if hit:
            return hit
        # fallback: any AI_NN_* variant
        for k, v in flows_by_id.items():
            if re.match(rf"^AI_{n:02d}(_|$)", k) or re.match(rf"^AI_{n}(_|$)", k):
                return v
        return None

    m = re.match(r"(?i)^Sp[_\s-]?(\d+)$", aid)
    if m:
        n = int(m.group(1))
        sp = {1:"SP_01",2:"SP_02",3:"ON_01",4:"ON_02",5:"ON_03",6:"ON_04",7:"OSS_08",8:"ON_05"}
        return resolve_id(sp.get(n), f"SP_{n:02d}")

    m = re.match(r"(?i)^SU\s*(\d+)$", aid)
    if m:
        n = int(m.group(1))
        su = {1:"OSS_03",2:"OSS_03",3:"OSS_04",4:"OSS_04",5:"SG_04",6:"SG_02",7:"SG_03",
              8:"OSS_05",9:"OSS_06",10:"OSS_07",11:"OSS_08",12:"OSS_09",13:"OSS_10",14:"OSS_11",
              15:"OSS_12",16:"OSS_13",17:"OSS_14",18:"LO_06",19:"OSS_15",20:"OSS_16",21:"OSS_17",
              22:"OSS_18",23:"OSS_19",24:"OSS_20",25:"LO_01",26:"LO_09",27:"SL_01"}
        return resolve_id(su.get(n), f"OSS_{n:02d}", f"SG_{n:02d}")

    m = re.match(r"(?i)^FW\s*(\d+)$", aid)
    if m:
        return resolve_id(f"FW_{int(m.group(1)):02d}")

    m = re.match(r"(?i)^(Blocker|Stopper)\s*(\d+)$", aid)
    if m:
        return resolve_id(f"AL_{int(m.group(2)):02d}")

    m = re.match(r"(?i)^Hamburger Menu_(\d+)(?:\s*\((\d+)\))?(?:\s*([a-zA-Z]))?$", aid)
    if m:
        n = int(m.group(1)); sub = int(m.group(2)) if m.group(2) else 0
        if n == 4 and sub:
            return resolve_id(f"SE_{35+sub:02d}")
        if n == 5 and sub:
            return resolve_id(f"SE_{15+sub:02d}", f"SE_08")
        hm = {1:"SE_01",2:"SE_04",3:"SE_03",4:"SE_07",5:"SE_08",6:"SE_09",7:"SE_10",8:"SE_11",
              9:"SE_12",10:"SE_06",11:"SE_13",12:"SE_14",13:"SE_15",14:"SE_16",15:"SE_18",
              16:"SE_17",17:"SE_25",18:"SE_27",19:"SE_28",20:"SE_29",21:"SE_30",22:"SE_31",
              23:"SE_32",24:"SE_44",25:"SE_47",26:"SE_48",27:"SE_49",28:"SE_50",29:"SE_51"}
        return resolve_id(hm.get(n), f"SE_{n:02d}")

    # Hamburger Menu_11(A) style
    m = re.match(r"(?i)^Hamb\w*rger Menu_(\d+)\s*\(\s*([A-Za-z])\s*\)$", aid)
    if m:
        n = int(m.group(1)); letter = m.group(2).upper()
        # map A-E to SE help items
        if n == 11:
            letter_map = {"A":"SE_53","B":"SE_54","C":"SE_55","D":"SE_56","E":"SE_57"}
            return resolve_id(letter_map.get(letter), f"SE_09")
        if n == 6:
            letter_map = {"A":"SE_18","B":"SE_19","C":"SE_20","D":"SE_21","E":"SE_22"}
            return resolve_id(letter_map.get(letter))

    m = re.match(r"(?i)^Tiles modules?\s*(\d+)$", aid)
    if m:
        return resolve_id(f"TP_{int(m.group(1)):02d}", f"TP_{int(m.group(1)):02d}A", f"TP_{int(m.group(1)):02d}B")

    m = re.match(r"(?i)^Custom SDK\s*(\d+)$", aid)
    if m:
        return resolve_id(f"CS_{int(m.group(1)):02d}")

    m = re.match(r"(?i)^HOME SCREEN_(\d+)$", aid)
    if m:
        n = int(m.group(1))
        return resolve_id(f"HM_{n:02d}", "HM_05" if n == 6 else None)

    m = re.match(r"(?i)^Print Preview_(\d+)$", aid)
    if m:
        return resolve_id(f"PR_{int(m.group(1)):02d}")

    m = re.match(r"(?i)^Print_State_(\d+)$", aid)
    if m:
        return resolve_id(f"PS_{int(m.group(1)):02d}")

    m = re.match(r"(?i)^Print_Queue(\d+)$", aid)
    if m:
        return resolve_id(f"PQ_{int(m.group(1)):02d}", f"PHQ_{int(m.group(1)):02d}")

    m = re.match(r"(?i)^Print_History(\d+)$", aid)
    if m:
        return resolve_id(f"PH_{int(m.group(1)):02d}")

    m = re.match(r"(?i)^PrintState_Tips_(\d+)$", aid)
    if m:
        return resolve_id(f"PS_{int(m.group(1)):02d}")

    m = re.match(r"(?i)^PS-(\d+)$", aid)
    if m:
        # printer settings - may be COX or SE
        return resolve_id(f"PRSET_{int(m.group(1)):03d}", f"SE_{int(m.group(1)):02d}")

    # Quick print
    m = re.match(r"(?i)^QUICK PRINT[_ ]+(\d+)\s*(?:\(([a-z])\))?$", aid)
    if m:
        n, suf = int(m.group(1)), (m.group(2) or "").lower()
        return resolve_id(f"QP_{n:03d}{suf}", f"QP_{n:03d}", f"QP_{n}{suf}", f"QP_{n:02d}{suf}")
    m = re.match(r"(?i)^Quick print_(\d+)\(([a-z])\)$", aid)
    if m:
        n, suf = int(m.group(1)), m.group(2).lower()
        return resolve_id(f"QP_{n:03d}{suf}", f"QP_{n:03d}")

    # Collage
    m = re.match(r"(?i)^Collage_(\d+)\s*(?:\(([a-z])\))?$", aid)
    if m:
        n, suf = int(m.group(1)), (m.group(2) or "").lower()
        return resolve_id(f"COL_{n:02d}{suf}", f"COL_{n:02d}", f"COL_{n}{suf}")

    # Precut
    m = re.match(r"(?i)^Precut_(\d+)\s*(?:\(([a-z])\))?$", aid)
    if m:
        n, suf = int(m.group(1)), (m.group(2) or "").lower()
        return resolve_id(f"PC_{n:02d}{suf}", f"PC_{n:02d}")

    # Video
    m = re.match(r"(?i)^Video [Ff]rame\s*(\d+)$", aid)
    if m:
        return resolve_id(f"VD_{int(m.group(1)):02d}")

    # Photobooth
    m = re.match(r"(?i)^Photobooth\s*(\d+)$", aid)
    if m:
        return resolve_id(f"PB_{int(m.group(1)):02d}")

    # Photo ID
    m = re.match(r"(?i)^Photo\s*ID_(\d+)\s*(?:\(([a-z])\))?$", aid)
    if m:
        n, suf = int(m.group(1)), (m.group(2) or "").lower()
        return resolve_id(f"PID_{n:02d}{suf}", f"PID_{n:02d}", f"PhotoID_{n:02d}")

    # PCF-* and PCF_HP*
    m = re.match(r"(?i)^PCF-(\d+)$", aid)
    if m:
        return resolve_id(f"COX_{int(m.group(1)):03d}", f"CO_{int(m.group(1)):03d}")
    m = re.match(r"(?i)^General_PCF-(\d+)$", aid)
    if m:
        return resolve_id(f"GN_{int(m.group(1)):02d}", f"COX_{int(m.group(1)):03d}")

    # PCF with excel tag already in map via tags - also try matching by reading
    if aid.upper().startswith("PCF_"):
        # already in excel_to_flow via tags ideally
        # Sense variants
        if re.search(r"(?i)sence|sense", aid):
            m = re.search(r"_(\d+)$", aid)
            n = int(m.group(1)) if m else 1
            # Prefer Select mirror steps (Sense UI similar to Select onboarding)
            # Look for files whose Excel tag contains Select same number
            for eid2, fl in list(excel_to_flow.items()):
                if re.match(rf"(?i)PCF_HPSelect_{n:03d}$", eid2):
                    return fl
            return resolve_id(f"COX_{n:03d}")
        # try exact already
        return excel_to_flow.get(aid)

    # HP600
    m = re.match(r"(?i)^HP600_CONN_TC(\d+)$", aid)
    if m:
        return resolve_id(f"HP600_{int(m.group(1)):03d}", f"COX_{200+int(m.group(1)):03d}")

    return None

# Build final map
final = {}
aliases = {}
headers = []
still = []

for item in excel_rows:
    aid = item["id"]
    if HEADER_RE.match(aid):
        headers.append(aid)
        continue
    # exact
    if aid in excel_to_flow:
        final[aid] = excel_to_flow[aid]
        continue
    # case-insensitive exact
    hit = None
    for k,v in excel_to_flow.items():
        if k.lower() == aid.lower():
            hit = v; break
    if hit:
        final[aid] = hit
        continue
    # alias
    fl = alias_flow(aid)
    if fl:
        final[aid] = fl
        aliases[aid] = fl
    else:
        still.append(aid)

# Also add excel_to_flow keys that match excel rows even if weird spacing
print(f"Mapped: {len(final)} | Headers: {len(headers)} | Still: {len(still)}")
print("Still (first 80):")
for s in still[:80]:
    print(" ", s)
if len(still) > 80:
    print(f"  ... +{len(still)-80}")

# Verify flows exist (Windows long-path aware)
missing_files = [k for k, v in final.items() if not _exists(REPO / v)]
# Auto-heal broken long AI paths by short-id resolve
healed = 0
for k in list(missing_files):
    m = re.match(r"(?i)^AI Tools?\s+(\d+)\s*(?:\(([a-z])\))?$", k)
    if not m:
        continue
    n, suf = int(m.group(1)), (m.group(2) or "").lower()
    fl = resolve_id(f"AI_{n:02d}{suf}" if suf else f"AI_{n:02d}")
    if fl and _exists(REPO / fl):
        final[k] = fl
        healed += 1
missing_files = [k for k, v in final.items() if not _exists(REPO / v)]
print(f"Healed long paths: {healed}")
print(f"Broken paths: {len(missing_files)}")
if missing_files[:10]:
    print(missing_files[:10])

# Preserve Excel sheet order for the runner
matched_list = []
seen = set()
for item in excel_rows:
    aid = item["id"]
    if aid in final and aid not in seen:
        matched_list.append({"excel_id": aid, "flow": final[aid]})
        seen.add(aid)

payload = {
    "generated": "rebuild_from_csv_tags_aliases",
    "matched_count": len(final),
    "unmatched_count": len(still),
    "header_count": len(headers),
    "map": final,
    "matched": matched_list,
    "unmatched": still,
    "headers": headers,
    "aliases_added": aliases,
}
(OUT / "excel_flow_map.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
(OUT / "still_unmatched.json").write_text(json.dumps(still, indent=2), encoding="utf-8")
print(f"Wrote excel_flow_map.json (matched list {len(matched_list)})")
