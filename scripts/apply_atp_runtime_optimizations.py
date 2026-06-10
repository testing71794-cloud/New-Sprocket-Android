#!/usr/bin/env python3
"""
Safe ATP YAML runtime optimizations (rollback: git checkout -- <paths>).

1. Remove redundant waitForAnimationToEnd immediately before runFlow (subflow owns waits).
2. Collage suite: replace inline swipe / home-wait blocks with shared flows.

Does not change assertions, test steps, launchApp, or Maestro version.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
ATP_ROOT = REPO / "ATP TestCase Flows"

SWIPE_INLINE = re.compile(
    r"- runFlow:\n"
    r"    when:\n"
    r'      visible: "Swipe to continue"\n'
    r"    commands:\n"
    r'      - tapOn:\n'
    r'          point: "50%,50%"\n'
    r"      - waitForAnimationToEnd\n"
    r"      - swipe:\n"
    r'          start: "75%,55%"\n'
    r'          end: "15%,45%"\n'
    r"      - waitForAnimationToEnd\n",
    re.MULTILINE,
)

HOME_WAIT_BLOCK = re.compile(
    r"- extendedWaitUntil:\n"
    r'    visible: "KODAK SMILE"\n'
    r"    timeout: 2000\n"
    r'- assertVisible: "KODAK SMILE"\n'
    r"- assertVisible: \$\{output\.home\.titleText\}\n",
    re.MULTILINE,
)


def strip_wait_before_runflow(text: str) -> tuple[str, int]:
    """Drop '- waitForAnimationToEnd' when the next command is '- runFlow:'."""
    lines = text.splitlines(keepends=True)
    out: list[str] = []
    removed = 0
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.rstrip("\r\n") == "- waitForAnimationToEnd":
            j = i + 1
            while j < len(lines) and lines[j].strip() in ("", "#"):
                j += 1
            if j < len(lines) and lines[j].lstrip().startswith("- runFlow:"):
                removed += 1
                i += 1
                continue
        out.append(line)
        i += 1
    return "".join(out), removed


def optimize_collage_file(text: str) -> tuple[str, dict[str, int]]:
    stats: dict[str, int] = {"swipe": 0, "home": 0}
    new_text, n = SWIPE_INLINE.subn(
        "- runFlow: ../../flows/swipeOnboardingIfShown.yaml\n", text
    )
    stats["swipe"] = n
    text = new_text
    new_text, n = HOME_WAIT_BLOCK.subn(
        "- runFlow: ../../flows/waitForHomeScreen.yaml\n", text
    )
    stats["home"] = n
    text = new_text
    return text, stats


def process_file(path: Path, *, collage: bool, dry_run: bool) -> dict[str, int]:
    raw = path.read_text(encoding="utf-8")
    text, wait_removed = strip_wait_before_runflow(raw)
    stats: dict[str, int] = {"wait_before_runflow": wait_removed}
    if collage:
        text, cstats = optimize_collage_file(text)
        stats.update(cstats)
    if text != raw and not dry_run:
        path.write_text(text, encoding="utf-8", newline="\n")
    if text != raw:
        stats["changed"] = 1
    else:
        stats["changed"] = 0
    return stats


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true", help="Report only; do not write files")
    ap.add_argument(
        "--folder",
        default="",
        help="ATP subfolder name (e.g. Collage). Default: all under ATP TestCase Flows",
    )
    args = ap.parse_args()
    root = ATP_ROOT / args.folder if args.folder else ATP_ROOT
    if not root.is_dir():
        print(f"ERROR: not a directory: {root}", file=sys.stderr)
        return 2

    totals: dict[str, int] = {}
    files_changed = 0
    yaml_files = sorted(root.rglob("*.yaml")) + sorted(root.rglob("*.yml"))
    for yf in yaml_files:
        collage = "Collage" in yf.parts
        st = process_file(yf, collage=collage, dry_run=args.dry_run)
        if st.get("changed"):
            files_changed += 1
            rel = yf.relative_to(REPO)
            print(
                f"{'[dry-run] ' if args.dry_run else ''}{rel}: "
                f"wait_removed={st.get('wait_before_runflow', 0)} "
                f"swipe={st.get('swipe', 0)} home={st.get('home', 0)}"
            )
        for k, v in st.items():
            if k != "changed":
                totals[k] = totals.get(k, 0) + v

    print(
        f"\n{'[dry-run] ' if args.dry_run else ''}Files changed: {files_changed}; "
        f"totals: {totals}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
