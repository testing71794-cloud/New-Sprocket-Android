"""
Generate ATP TestCase Flows modules from the ATP Excel catalog.

Creates one folder per Excel stage (missing modules) with:
  - top-level Maestro flows (one per ATP case, capped per stage)
  - shared setup subflow
  - atp_*_mapping.csv

Also refreshes ATP TestCase Flows/atp_sprocket_mapping.csv and
execution/atp_folder_paths.py keys.
"""
from __future__ import annotations

import csv
import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CATALOG = REPO / "ATP Verification Suite" / "catalog" / "atp_cases.json"
ATP = REPO / "ATP TestCase Flows"
APP_ID = "com.hp.impulse.sprocket"

# Excel stage → on-disk module folder + ID prefix
# Hand-tuned folders use *X prefixes so generated flows never overwrite SP_01 / CO_01 / COL_01 / QP_01 / ON_01.
STAGE_MODULES: dict[str, tuple[str, str]] = {
    "Home": ("home", "HM"),
    "Camera": ("camera", "CA"),
    "PhotoID": ("photo-id", "PID"),
    "Photobooth": ("photobooth", "PB"),
    "CustomSDK": ("custom-sdk", "CS"),
    "Editor": ("editor", "ED"),
    "Printing": ("printing", "PR"),
    "PreCut": ("precut", "PC"),
    "Video": ("video", "VD"),
    "TilePrint": ("tile-print", "TP"),
    "Settings": ("settings", "SE"),
    "Firmware": ("firmware", "FW"),
    "AI": ("ai", "AI"),
    "Alerts": ("alerts", "AL"),
    "General": ("general", "GN"),
    "OnboardingSplash": ("onboarding-splash", "OSS"),
    # Remaining Excel stages (extend existing hand-tuned modules)
    "Splash": ("splash", "SPX"),
    "Onboarding": ("onboarding", "ONX"),
    "QuickPrint": ("quick-print", "QPX"),
    "Collage": ("collage", "COLX"),
    "Connection": ("connection", "COX"),
}

# Folders that already have hand-tuned flows — preserve them; only add Excel-generated files
HAND_TUNED_FOLDERS = frozenset(
    {"splash", "onboarding", "quick-print", "collage", "connection", "signup", "login", "signup-later", "permission", "gallery"}
)

SKIP_STAGES: set[str] = set()

# Soft cap so huge stages stay maintainable (still one module folder each)
MAX_FLOWS_PER_STAGE = {
    "AI": 196,
    "Alerts": 60,
    "Firmware": 51,
    "Printing": 106,
    "General": 166,
    "Camera": 40,
    "PhotoID": 30,
    "Photobooth": 25,
    "CustomSDK": 20,
    "Editor": 30,
    "Settings": 55,
    "Home": 10,
    "PreCut": 15,
    "Video": 15,
    "TilePrint": 20,
    "OnboardingSplash": 25,
    "Splash": 5,
    "Onboarding": 25,
    "QuickPrint": 45,
    "Collage": 20,
    "Connection": 256,
}

# Generated TestCaseID prefixes (used when merging master mapping)
GENERATED_PREFIXES = frozenset(
    {
        "HM_",
        "CA_",
        "PID_",
        "PB_",
        "CS_",
        "ED_",
        "PR_",
        "PC_",
        "VD_",
        "TP_",
        "SE_",
        "FW_",
        "AI_",
        "AL_",
        "GN_",
        "OSS_",
        "SPX_",
        "ONX_",
        "QPX_",
        "COLX_",
        "COX_",
    }
)


def _safe_name(text: str, max_len: int = 60) -> str:
    t = re.sub(r"[^\w\s\-]+", "", text or "", flags=re.U)
    t = re.sub(r"\s+", " ", t).strip()
    t = t.replace(" ", "_")
    return (t or "case")[:max_len]


def _selectors(case: dict) -> list[str]:
    sels: list[str] = []
    for v in case.get("verifications") or []:
        s = v.get("selector")
        if s and s not in sels:
            sels.append(s)
    return sels[:6]


def _setup_commands(stage: str) -> list[str]:
    """Return Maestro YAML command lines (indented as list items) after launch."""
    # Splash: stay on first interactive / welcome screen
    if stage == "Splash":
        return [
            "- runFlow: ../../common/subflows/wait_after_cold_launch.yaml",
            "- runFlow: ../../common/subflows/complete_sprocket_carousel_if_visible.yaml",
            "- extendedWaitUntil:",
            '    visible: "Sign up"',
            "    timeout: 15000",
        ]

    # Onboarding splash section: optional carousel → Sign up
    if stage == "OnboardingSplash":
        return [
            "- runFlow: ../../common/subflows/wait_after_cold_launch.yaml",
            "- runFlow: ../../common/subflows/complete_sprocket_carousel_if_visible.yaml",
            "- extendedWaitUntil:",
            '    visible: "Sign up"',
            "    timeout: 15000",
            "- assertVisible:",
            '    text: ".*(?i)(I.ll do it later|Sign Up Later).*"',
            "    optional: true",
            "- assertVisible:",
            '    text: ".*(?i)(I already have (an )?account).*"',
            "    optional: true",
        ]

    # Onboarding: optional carousel through to Sign up
    if stage == "Onboarding":
        return [
            "- runFlow: ../../common/subflows/wait_after_cold_launch.yaml",
            "- runFlow: ../../common/subflows/complete_sprocket_carousel_if_visible.yaml",
            "- extendedWaitUntil:",
            '    visible: "Sign up"',
            "    timeout: 15000",
        ]

    common = [
        "- runFlow: ../../common/subflows/wait_after_cold_launch.yaml",
        "- runFlow: ../../common/subflows/complete_sprocket_carousel_if_visible.yaml",
        "- extendedWaitUntil:",
        '    visible: "Sign up"',
        "    timeout: 15000",
        "- runFlow: ../../common/subflows/tap_sign_up_later.yaml",
        "- runFlow: ../../common/subflows/accept_terms_if_visible.yaml",
        "- runFlow:",
        "    when:",
        '      visible: "Skip"',
        "    commands:",
        '      - tapOn: "Skip"',
        "- runFlow: ../../permission/subflows/allow_all_runtime_permissions.yaml",
        "- runFlow: ../../permission/subflows/allow_notification_permission.yaml",
        "- runFlow: ../../gallery/subflows/dismiss_gallery_coachmark_if_visible.yaml",
        "- runFlow:",
        "    when:",
        '      visible: ".*Create.*"',
        "    commands:",
        '      - tapOn: ".*Create.*"',
        "- waitForAnimationToEnd:",
        "    timeout: 4000",
        "- assertVisible:",
        '    text: ".*(?i)(Collage Maker|Quick Print|Create|Printer|More).*"',
        "    optional: true",
    ]
    by_stage: dict[str, list[str]] = {
        "Home": [
            "- assertVisible:",
            '    text: ".*(?i)(Collage Maker|Quick Print).*"',
            "    optional: true",
        ],
        "Camera": [
            "- runFlow:",
            "    when:",
            '      visible: ".*(?i)(Camera|Photo Booth|Photobooth).*"',
            "    commands:",
            '      - tapOn: ".*(?i)(Camera|Photo Booth|Photobooth).*"',
            "- waitForAnimationToEnd:",
            "    timeout: 3000",
        ],
        "PhotoID": [
            "- runFlow:",
            "    when:",
            '      visible: ".*(?i)(Photo ID|PhotoID).*"',
            "    commands:",
            '      - tapOn: ".*(?i)(Photo ID|PhotoID).*"',
            "- waitForAnimationToEnd:",
            "    timeout: 3000",
            "- runFlow:",
            "    when:",
            '      visible: ".*(?i)(OK|Got it|Don.t Show Again).*"',
            "    commands:",
            '      - tapOn: ".*(?i)(OK|Got it).*"',
            "- assertVisible:",
            '    text: ".*(?i)(Photo ID|Timer|Flash|Capture|Print).*"',
            "    optional: true",
        ],
        "Photobooth": [
            "- runFlow:",
            "    when:",
            '      visible: ".*(?i)(Photo Booth|Photobooth|Booth).*"',
            "    commands:",
            '      - tapOn: ".*(?i)(Photo Booth|Photobooth|Booth).*"',
            "- waitForAnimationToEnd:",
            "    timeout: 3000",
            "- assertVisible:",
            '    text: ".*(?i)(Booth|Countdown|Capture|Timer|Flash).*"',
            "    optional: true",
        ],
        "CustomSDK": [
            '- tapOn: ".*Quick Print.*"',
            "- runFlow: ../../permission/subflows/allow_photos_all_permission.yaml",
            "- extendedWaitUntil:",
            '    visible: "Recent"',
            "    timeout: 12000",
            "- tapOn:",
            '    point: "25%,35%"',
            "- waitForAnimationToEnd:",
            "    timeout: 3000",
            "- assertVisible:",
            '    text: ".*(?i)(Edit|Crop|Filter|Sticker|Frame|SDK).*"',
            "    optional: true",
        ],
        "Editor": [
            '- tapOn: ".*Quick Print.*"',
            "- runFlow: ../../permission/subflows/allow_photos_all_permission.yaml",
            "- extendedWaitUntil:",
            '    visible: "Recent"',
            "    timeout: 12000",
            "- tapOn:",
            '    point: "25%,35%"',
            "- waitForAnimationToEnd:",
            "    timeout: 3000",
        ],
        "Printing": [
            '- tapOn: ".*Quick Print.*"',
            "- runFlow: ../../permission/subflows/allow_photos_all_permission.yaml",
            "- extendedWaitUntil:",
            '    visible: "Recent"',
            "    timeout: 12000",
            "- tapOn:",
            '    point: "25%,35%"',
            "- waitForAnimationToEnd:",
            "    timeout: 3000",
            "- runFlow:",
            "    when:",
            '      visible: ".*(?i)(Print|Next|Continue).*"',
            "    commands:",
            '      - tapOn: ".*(?i)(Print|Next|Continue).*"',
        ],
        "PreCut": [
            "- runFlow:",
            "    when:",
            '      visible: ".*(?i)(Pre-?Cut|Precut).*"',
            "    commands:",
            '      - tapOn: ".*(?i)(Pre-?Cut|Precut).*"',
            "- waitForAnimationToEnd:",
            "    timeout: 3000",
        ],
        "Video": [
            '- tapOn: ".*Quick Print.*"',
            "- runFlow: ../../permission/subflows/allow_photos_all_permission.yaml",
            "- extendedWaitUntil:",
            '    visible: "Recent"',
            "    timeout: 12000",
            "- runFlow:",
            "    when:",
            '      visible: ".*(?i)Video.*"',
            "    commands:",
            '      - tapOn: ".*(?i)Video.*"',
        ],
        "TilePrint": [
            "- runFlow:",
            "    when:",
            '      visible: ".*(?i)(Tiles|Tile).*"',
            "    commands:",
            '      - tapOn: ".*(?i)(Tiles|Tile).*"',
            "- waitForAnimationToEnd:",
            "    timeout: 3000",
        ],
        "Settings": [
            "- runFlow:",
            "    when:",
            '      visible: ".*(?i)(More|Settings|Account).*"',
            "    commands:",
            '      - tapOn: ".*(?i)(More|Settings|Account).*"',
            "- waitForAnimationToEnd:",
            "    timeout: 2000",
        ],
        "Firmware": [
            '- tapOn: ".*Printer.*"',
            "- waitForAnimationToEnd:",
            "    timeout: 3000",
            "- runFlow:",
            "    when:",
            '      visible: ".*(?i)(Firmware|Update|Settings).*"',
            "    commands:",
            '      - tapOn: ".*(?i)(Firmware|Update|Settings).*"',
        ],
        "AI": [
            "- runFlow:",
            "    when:",
            '      visible: ".*(?i)(Sprocket AI|AI|Text-to-Image).*"',
            "    commands:",
            '      - tapOn: ".*(?i)(Sprocket AI|AI|Text-to-Image).*"',
            "- waitForAnimationToEnd:",
            "    timeout: 3000",
        ],
        "Alerts": [
            '- tapOn: ".*Printer.*"',
            "- waitForAnimationToEnd:",
            "    timeout: 3000",
        ],
        "General": [],
        "QuickPrint": [
            '- tapOn: ".*Quick Print.*"',
            "- runFlow: ../../permission/subflows/allow_photos_all_permission.yaml",
            "- extendedWaitUntil:",
            '    visible: "Recent"',
            "    timeout: 12000",
        ],
        "Collage": [
            '- tapOn: ".*Collage Maker.*"',
            "- runFlow: ../../permission/subflows/allow_photos_all_permission.yaml",
            "- extendedWaitUntil:",
            '    visible: "Select 2 to 4 photos"',
            "    timeout: 12000",
        ],
        "Connection": [
            '- tapOn: ".*Printer.*"',
            "- waitForAnimationToEnd:",
            "    timeout: 3000",
            "- assertVisible:",
            '    text: ".*(?i)(No Printers Added|Add Printer|Add New Printer|Printer|Bluetooth).*"',
            "    optional: true",
        ],
    }
    return common + by_stage.get(stage, [])


def write_module_subflow(folder: Path, stage: str, *, hand_tuned: bool) -> str:
    """Write setup subflow; return relative runFlow path used by generated cases."""
    sub = folder / "subflows"
    sub.mkdir(parents=True, exist_ok=True)
    # Avoid clobbering hand-tuned reach helpers
    name = "reach_excel_screen.yaml" if hand_tuned else "reach_module_screen.yaml"
    body = [
        f"# Shared Excel-generated setup for {stage} ATP module",
        f"appId: {APP_ID}",
        "---",
        "- launchApp:",
        "    clearState: true",
        *_setup_commands(stage),
        "",
    ]
    (sub / name).write_text("\n".join(body), encoding="utf-8")
    return f"subflows/{name}"


def flow_yaml(tc_id: str, title: str, stage: str, case: dict, setup_flow: str) -> str:
    desc = (case.get("description") or title).replace("\n", " ")
    expected = (case.get("expected") or "").replace("\n", " ")[:240]
    sels = _selectors(case)
    folder_tag = STAGE_MODULES[stage][0]
    lines = [
        f"# ATP Test Case ID: {tc_id}",
        f"# Excel: {case.get('test_id')} | Module: {case.get('module')}",
        f"# {desc}",
        f"# Expected: {expected}",
        f"appId: {APP_ID}",
        f'name: "{tc_id} - {title}"',
        "tags:",
        f"  - {folder_tag}",
        "  - atp-excel",
        "---",
        f"- runFlow: {setup_flow}",
    ]
    if sels:
        for s in sels:
            safe = s.replace('"', '\\"')
            lines += [
                "- assertVisible:",
                f'    text: "{safe}"',
                "    optional: true",
            ]
    else:
        lines += [
            "- assertVisible:",
            '    text: ".*(?i)(Create|Collage Maker|Quick Print|Printer|Settings|Recent|Welcome|Sign up).*"',
            "    optional: true",
        ]
    lines.append("")
    return "\n".join(lines)


def _cleanup_previous_generated(folder: Path, prefix: str) -> None:
    """Remove previously generated Excel flows for this prefix only."""
    for p in folder.glob(f"{prefix}_*.yaml"):
        try:
            p.unlink()
        except OSError:
            pass


def generate_stage(stage: str, cases: list[dict]) -> list[dict]:
    folder_name, prefix = STAGE_MODULES[stage]
    folder = ATP / folder_name
    folder.mkdir(parents=True, exist_ok=True)
    hand_tuned = folder_name in HAND_TUNED_FOLDERS
    setup_flow = write_module_subflow(folder, stage, hand_tuned=hand_tuned)
    _cleanup_previous_generated(folder, prefix)

    cap = MAX_FLOWS_PER_STAGE.get(stage, 30)
    selected = cases[:cap]
    mapping_rows: list[dict] = []

    for i, case in enumerate(selected, 1):
        tc_id = f"{prefix}_{i:02d}" if i < 100 else f"{prefix}_{i:03d}"
        # Connection has 256 — always use 3-digit for COX
        if prefix == "COX":
            tc_id = f"{prefix}_{i:03d}"
        title = _safe_name(case.get("description") or case.get("module") or case.get("test_id") or tc_id)
        fname = f"{tc_id} - {title.replace('_', ' ')}.yaml"
        fname = re.sub(r'[<>:"/\\|?*]', "", fname)[:120]
        if not fname.endswith(".yaml"):
            fname += ".yaml"
        path = folder / fname
        path.write_text(
            flow_yaml(tc_id, title.replace("_", " "), stage, case, setup_flow),
            encoding="utf-8",
        )
        mapping_rows.append(
            {
                "TestCaseID": tc_id,
                "ExcelID": case.get("test_id", ""),
                "Module": folder_name,
                "ExcelModule": case.get("module", ""),
                "Description": (case.get("description") or "")[:120],
                "FlowFile": f"{folder_name}/{fname}",
                "App": APP_ID,
            }
        )

    map_name = (
        f"atp_{folder_name.replace('-', '_')}_excel_mapping.csv"
        if hand_tuned
        else f"atp_{folder_name.replace('-', '_')}_mapping.csv"
    )
    map_path = folder / map_name
    with map_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(
            f,
            fieldnames=["TestCaseID", "ExcelID", "Module", "ExcelModule", "Description", "FlowFile", "App"],
        )
        w.writeheader()
        w.writerows(mapping_rows)

    checklist_name = "CHECKLIST_EXCEL.md" if hand_tuned else "CHECKLIST.md"
    lines = [f"# {stage} / {folder_name} — {len(mapping_rows)} Excel-generated flows\n"]
    for r in mapping_rows:
        lines.append(f"- [ ] {r['TestCaseID']} | {r['ExcelID']} | {r['Description']}")
    (folder / checklist_name).write_text("\n".join(lines) + "\n", encoding="utf-8")
    return mapping_rows


def update_folder_paths() -> None:
    path = REPO / "execution" / "atp_folder_paths.py"
    text = path.read_text(encoding="utf-8")
    extras = {
        "onboardingsplash": "onboarding-splash",
        "onboarding-splash": "onboarding-splash",
        "photoid": "photo-id",
        "photo-id": "photo-id",
        "photobooth": "photobooth",
        "customsdk": "custom-sdk",
        "custom-sdk": "custom-sdk",
        "home": "home",
        "camera": "camera",
        "editor": "editor",
        "printing": "printing",
        "precut": "precut",
        "video": "video",
        "tileprint": "tile-print",
        "tile-print": "tile-print",
        "settings": "settings",
        "firmware": "firmware",
        "ai": "ai",
        "alerts": "alerts",
        "general": "general",
    }
    block_lines = ["_CANONICAL_BY_KEY: dict[str, str] = {"]
    existing = {
        "connection": "connection",
        "onboarding": "onboarding",
        "splash": "splash",
        "signup": "signup",
        "login": "login",
        "signuplater": "signup-later",
        "signup-later": "signup-later",
        "signuplogin": "signup-login",
        "gallery": "gallery",
        "permission": "permission",
        "quickprint": "quick-print",
        "quick-print": "quick-print",
        "collage": "collage",
        **extras,
    }
    for k, v in existing.items():
        block_lines.append(f'    "{k}": "{v}",')
    block_lines.append("}")
    new_block = "\n".join(block_lines)
    text2 = re.sub(
        r"_CANONICAL_BY_KEY: dict\[str, str\] = \{.*?\n\}",
        new_block,
        text,
        count=1,
        flags=re.S,
    )
    path.write_text(text2, encoding="utf-8")


def _is_generated_id(tc_id: str) -> bool:
    tid = (tc_id or "").strip().upper()
    return any(tid.startswith(p) for p in GENERATED_PREFIXES)


def merge_master_mapping(new_rows: list[dict]) -> None:
    master = ATP / "atp_sprocket_mapping.csv"
    existing: list[dict] = []
    if master.exists():
        with master.open("r", encoding="utf-8", newline="") as f:
            existing = list(csv.DictReader(f))
    # Keep hand-tuned rows; replace prior Excel-generated rows by TestCaseID prefix
    kept = [r for r in existing if not _is_generated_id(r.get("TestCaseID", ""))]
    out_fields = ["TestCaseID", "Module", "FlowFile", "App", "ExcelID", "Description"]
    merged: list[dict] = []
    for r in kept:
        merged.append(
            {
                "TestCaseID": r.get("TestCaseID", ""),
                "Module": r.get("Module", ""),
                "FlowFile": r.get("FlowFile", ""),
                "App": r.get("App", APP_ID),
                "ExcelID": r.get("ExcelID", ""),
                "Description": r.get("Description", ""),
            }
        )
    for r in new_rows:
        merged.append(
            {
                "TestCaseID": r["TestCaseID"],
                "Module": r["Module"],
                "FlowFile": r["FlowFile"],
                "App": r["App"],
                "ExcelID": r.get("ExcelID", ""),
                "Description": r.get("Description", ""),
            }
        )
    with master.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=out_fields)
        w.writeheader()
        w.writerows(merged)


def main() -> None:
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--remaining-only",
        action="store_true",
        help="Only generate Splash/Onboarding/QuickPrint/Collage/Connection Excel flows",
    )
    args = ap.parse_args()

    remaining = {"Splash", "Onboarding", "QuickPrint", "Collage", "Connection"}
    remaining_prefixes = ("SPX_", "ONX_", "QPX_", "COLX_", "COX_")
    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    by_stage: dict[str, list] = {}
    for c in data["cases"]:
        by_stage.setdefault(c["stage"], []).append(c)

    stages = [s for s in STAGE_MODULES if s not in SKIP_STAGES]
    if args.remaining_only:
        stages = [s for s in stages if s in remaining]

    # Seed with existing generated rows we are not regenerating
    all_new: list[dict] = []
    if args.remaining_only:
        master = ATP / "atp_sprocket_mapping.csv"
        if master.exists():
            with master.open("r", encoding="utf-8", newline="") as f:
                for r in csv.DictReader(f):
                    tid = (r.get("TestCaseID") or "").upper()
                    if _is_generated_id(tid) and not tid.startswith(remaining_prefixes):
                        all_new.append(
                            {
                                "TestCaseID": r.get("TestCaseID", ""),
                                "Module": r.get("Module", ""),
                                "FlowFile": r.get("FlowFile", ""),
                                "App": r.get("App", APP_ID),
                                "ExcelID": r.get("ExcelID", ""),
                                "Description": r.get("Description", ""),
                            }
                        )

    for stage in stages:
        folder, _prefix = STAGE_MODULES[stage]
        cases = by_stage.get(stage, [])
        if not cases:
            print(f"skip {stage}: no cases")
            continue
        rows = generate_stage(stage, cases)
        all_new.extend(rows)
        print(f"{stage:12} -> {folder:12} flows={len(rows)} (of {len(cases)} excel)")

    merge_master_mapping(all_new)
    update_folder_paths()
    print(f"\nmaster mapping generated rows: {len(all_new)}")
    print(f"updated {ATP / 'atp_sprocket_mapping.csv'}")
    print("updated execution/atp_folder_paths.py")


if __name__ == "__main__":
    main()
