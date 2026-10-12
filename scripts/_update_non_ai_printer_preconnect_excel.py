"""Update non-AI Print Preview / print-path Excel rows for lab pre-connected printer.

Skips AI Tools rows. Rewrites connection/search/Add Printer steps to:
pre-connect printer → open feature → tap Print (when applicable).
"""
from __future__ import annotations

from pathlib import Path

from openpyxl import load_workbook
from openpyxl.styles import PatternFill

XLSX = Path(r"c:\Users\CA Global\Downloads\Hp new sprocket ATP Sheet.xlsx")

COMMON_PREFIX = (
    "1. Install and launch the application.\n"
    '2. Verify the Splash Screen displays the HP logo (hp sprocket) with "sprocket" text.\n'
    "3. Wait for the Splash Screen to complete.\n"
    "4. Swipe through the onboarding screens.\n"
    '5. Tap "Get Started".\n'
    '6. Tap "Sign Up Later".\n'
    "7. Wait until the Home screen is displayed.\n"
    '8. If the notification permission popup appears, tap "Allow".\n'
    "9. Ensure a compatible printer is already connected to the app (lab pre-connect).\n"
    "10. Do not tap Add Printer, Skip to Connection, or Searching for Printers.\n"
)

NOTE = "Updated: printer pre-connected; tap Print directly (no Add Printer / search)."

# excel_id -> (description, steps_suffix starting at step 11, expected)
UPDATES: dict[str, dict[str, str]] = {
    "Print Preview_01": {
        "description": (
            "Verify Print Preview opens from Quick Print when the printer is "
            "pre-connected (Print CTA shown; no Add Printer / search)."
        ),
        "steps_suffix": (
            '11. Tap "Create" if needed, then tap "Quick Print".\n'
            "12. Select one image from the gallery.\n"
            "13. Wait for the Print Preview screen.\n"
            '14. Verify the green CTA shows "Print" (not "Add Printer").'
        ),
        "expected": (
            "With a pre-connected printer, Quick Print opens Print Preview and "
            "shows Print instead of Add Printer. No printer search is required."
        ),
    },
    "Print Preview_02": {
        "description": (
            "Verify Print Preview opens when HP600/Studio Plus is pre-connected "
            "(no Wi-Fi Add Printer / search flow)."
        ),
        "steps_suffix": (
            '11. Tap "Create" if needed, then tap "Quick Print".\n'
            "12. Select one image from the gallery.\n"
            "13. Wait for the Print Preview screen.\n"
            '14. Verify "Print" is displayed and usable.'
        ),
        "expected": (
            "With a pre-connected HP600/Studio Plus, Print Preview shows Print. "
            "No Add Printer / Searching for Printers flow is required."
        ),
    },
    "Print Preview_03": {
        "description": (
            "Verify the 2 x 3 Print Preview canvas with a pre-connected HP200 "
            "(no Add Printer / search)."
        ),
        "steps_suffix": (
            '11. Tap "Quick Print" and select one image.\n'
            "12. Wait for Print Preview.\n"
            '13. Verify "Print" is displayed and the 2 x 3 canvas is shown.'
        ),
        "expected": (
            "Print Preview shows Print with the HP200 2 x 3 canvas. "
            "No printer search / Add Printer flow is required."
        ),
    },
    "Print Preview_04": {
        "description": (
            "Verify the 2 x 3 Print Preview canvas with a pre-connected original "
            "HP Sprocket (no Add Printer / search)."
        ),
        "steps_suffix": (
            '11. Tap "Quick Print" and select one image.\n'
            "12. Wait for Print Preview.\n"
            '13. Verify "Print" is displayed and the 2 x 3 canvas is shown.'
        ),
        "expected": (
            "Print Preview shows Print with the 2 x 3 canvas. "
            "No printer search / Add Printer flow is required."
        ),
    },
    "Print Preview_05": {
        "description": (
            "Verify the 2 x 3 Print Preview canvas with a pre-connected HP Sprocket "
            "Studio (no Add Printer / search)."
        ),
        "steps_suffix": (
            '11. Tap "Quick Print" and select one image.\n'
            "12. Wait for Print Preview.\n"
            '13. Verify "Print" is displayed and the 2 x 3 canvas is shown.'
        ),
        "expected": (
            "Print Preview shows Print with the Studio 2 x 3 canvas. "
            "No printer search / Add Printer flow is required."
        ),
    },
    "Print Preview_09": {
        "description": (
            "Verify Print is shown when connected, then Add Printer after the "
            "printer is powered off (start from pre-connected; no search)."
        ),
        "steps_suffix": (
            '11. Tap "Quick Print" and select one image.\n'
            '12. Verify "Print" is displayed.\n'
            "13. Power off / disconnect the printer (manual).\n"
            '14. Verify the CTA changes to "Add Printer" / No Printers Added.'
        ),
        "expected": (
            "While connected, Print is shown. After power-off, Add Printer appears. "
            "Initial setup must not use Add Printer / search."
        ),
    },
}

# Duplicate Print Preview_06 rows — update both by description keyword
PREVIEW_06 = {
    "studio plus": {
        "description": (
            "Verify the 2 x 3 Print Preview canvas with a pre-connected Studio Plus "
            "(no Add Printer / Wi-Fi search)."
        ),
        "steps_suffix": (
            '11. Tap "Quick Print" and select one image.\n'
            "12. Wait for Print Preview.\n"
            '13. Verify "Print" is displayed and the 2 x 3 canvas is shown.'
        ),
        "expected": (
            "Print Preview shows Print with the Studio Plus 2 x 3 canvas. "
            "No printer search / Add Printer flow is required."
        ),
    },
    "select": {
        "description": (
            "Verify the 2.3 x 3.4 Print Preview canvas with a pre-connected "
            "HP Sprocket Select (no Add Printer / search)."
        ),
        "steps_suffix": (
            '11. Tap "Quick Print" and select one image.\n'
            "12. Wait for Print Preview.\n"
            '13. Verify "Print" is displayed and the 2.3 x 3.4 canvas is shown.'
        ),
        "expected": (
            "Print Preview shows Print with the Select 2.3 x 3.4 canvas. "
            "No printer search / Add Printer flow is required."
        ),
    },
}

PREVIEW_07 = {
    "description": (
        "Verify the 2.3 x 3.4 Print Preview canvas with a pre-connected "
        "HP Sprocket Plus (no Add Printer / search)."
    ),
    "steps_suffix": (
        '11. Tap "Quick Print" and select one image.\n'
        "12. Wait for Print Preview.\n"
        '13. Verify "Print" is displayed and the 2.3 x 3.4 canvas is shown.'
    ),
    "expected": (
        "Print Preview shows Print with the Plus 2.3 x 3.4 canvas. "
        "No printer search / Add Printer flow is required."
    ),
}

PREVIEW_08 = {
    "description": (
        "Verify the 3.5 x 4.25 Print Preview canvas with a pre-connected "
        "HP Sprocket 3x4 (no Add Printer / search)."
    ),
    "steps_suffix": (
        '11. Tap "Quick Print" and select one image.\n'
        "12. Wait for Print Preview.\n"
        '13. Verify "Print" is displayed and the 3.5 x 4.25 canvas is shown.'
    ),
    "expected": (
        "Print Preview shows Print with the 3x4 canvas. "
        "No printer search / Add Printer flow is required."
    ),
}


def _apply(row, u: dict) -> None:
    row[2].value = u["description"]
    row[3].value = COMMON_PREFIX + u["steps_suffix"]
    row[5].value = u["expected"]
    row[10].value = NOTE
    row[10].fill = PatternFill("solid", fgColor="FFF2CC")


def main() -> int:
    wb = load_workbook(XLSX)
    ws = wb["New Sprocket Final ATP"]
    updated = 0
    for row in ws.iter_rows(min_row=2, max_row=ws.max_row):
        aid = str(row[0].value or "").strip()
        mod = str(row[1].value or "")
        desc = str(row[2].value or "")
        if aid.startswith("AI Tools"):
            continue
        if aid in UPDATES:
            _apply(row, UPDATES[aid])
            updated += 1
        elif aid == "Print Preview_06":
            blob = (mod + " " + desc).lower()
            if "select" in blob:
                _apply(row, PREVIEW_06["select"])
            else:
                _apply(row, PREVIEW_06["studio plus"])
            updated += 1
        elif aid == "Print Preview_07":
            _apply(row, PREVIEW_07)
            updated += 1
        elif aid == "Print Preview_08":
            _apply(row, PREVIEW_08)
            updated += 1
        else:
            # Stamp comment on other non-AI print-path rows that still mention Add Printer
            steps = str(row[3].value or "")
            exp = str(row[5].value or "")
            blob = (steps + " " + desc + " " + exp).lower()
            if not any(
                k in (aid + " " + mod).lower()
                for k in (
                    "quick print",
                    "print preview",
                    "print state",
                    "print queue",
                    "collage",
                    "pre-cut",
                    "photo id",
                    "photobooth",
                    "tiles",
                )
            ):
                continue
            if "add printer" in blob or "skip to connection" in blob or "searching for printer" in blob:
                existing = str(row[10].value or "")
                if "pre-connected" not in existing.lower():
                    row[10].value = (existing + " | " if existing else "") + NOTE
                    row[10].fill = PatternFill("solid", fgColor="FFF2CC")
                    updated += 1

    wb.save(XLSX)
    print(f"Updated {updated} non-AI Excel rows (AI skipped)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
