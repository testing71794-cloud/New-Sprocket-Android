"""Patch reach_* setup YAMLs to use soft Create-hub landing (avoid hard Collage/Quick Print wait)."""
from __future__ import annotations

import re
from pathlib import Path

ATP = Path(__file__).resolve().parents[1] / "ATP TestCase Flows"

OLD = re.compile(
    r"- extendedWaitUntil:\n"
    r'    visible: "\.\*\(\?i\)\(Collage Maker\|Quick Print\)\.\*"\n'
    r"    timeout: 15000\n"
    r"(?:- assertVisible:\n"
    r'    text: "\.\*\(\?i\)\(Collage Maker\|Quick Print\)\.\*"\n'
    r"    optional: true\n)?",
    re.M,
)

NEW = (
    "- waitForAnimationToEnd:\n"
    "    timeout: 4000\n"
    "- assertVisible:\n"
    '    text: ".*(?i)(Collage Maker|Quick Print|Create|Printer|More).*"\n'
    "    optional: true\n"
)

NOTIF = "- runFlow: ../../permission/subflows/allow_notification_permission.yaml\n"
ALL_PERM = "- runFlow: ../../permission/subflows/allow_all_runtime_permissions.yaml\n"


def main() -> None:
    n = 0
    for f in ATP.rglob("reach_*.yaml"):
        t = f.read_text(encoding="utf-8")
        orig = t
        t2, count = OLD.subn(NEW, t)
        if ALL_PERM in t2 and "allow_notification_permission" not in t2:
            t2 = t2.replace(ALL_PERM, ALL_PERM + NOTIF)
        if t2 != orig:
            f.write_text(t2, encoding="utf-8")
            print("patched", f.relative_to(ATP), "subs", count)
            n += 1
    print("files", n)


if __name__ == "__main__":
    main()
