"""
Generate one Maestro module flow YAML per ATP stage (documentation + optional soft asserts).

Re-run after catalog refresh:
  python "ATP Verification Suite/tools/generate_module_flows.py"
"""
from __future__ import annotations

import json
from pathlib import Path

SUITE = Path(__file__).resolve().parents[1]
FLOWS = SUITE / "flows"
CATALOG = SUITE / "catalog" / "atp_cases.json"

# Stages that already have hand-tuned navigation YAML
HAND_TUNED = {
    "Splash",
    "Onboarding",
    "Home",
    "Collage",
    "QuickPrint",
    "Connection",
    "Editor",
    "Printing",
    "Settings",
}

SETUP_ALIAS = {
    "PreCut": "Collage",
    "Video": "QuickPrint",
    "TilePrint": "Printing",
    "Camera": "Home",
    "AI": "Home",
    "Firmware": "Connection",
    "Alerts": "Home",
    "General": "Home",
}


def main() -> None:
    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    by_stage: dict[str, list] = {}
    for c in data["cases"]:
        by_stage.setdefault(c["stage"], []).append(c)

    for stage, cases in sorted(by_stage.items()):
        out_dir = FLOWS / stage
        out_dir.mkdir(parents=True, exist_ok=True)
        checklist = "\n".join(
            f"#   - {c['test_id']}: {c['description'][:80]}" for c in cases[:40]
        )
        more = f"\n#   ... +{len(cases) - 40} more" if len(cases) > 40 else ""

        if stage not in HAND_TUNED:
            alias = SETUP_ALIAS.get(stage, "Home")
            body = f"""# ATP Stage Flow: {stage}
# Auto-generated checklist. Navigation reuses {alias} setup; assertions via run_module.py.
appId: com.hp.impulse.sprocket
name: "Stage - {stage}"
tags:
  - atp-verification
  - {stage.lower()}
---
# Cases in this stage ({len(cases)}):
{checklist}{more}
- runFlow: ../{alias}/{alias}.yaml
"""
            (out_dir / f"{stage}.yaml").write_text(body, encoding="utf-8")
            (out_dir / "setup.yaml").write_text(
                f"appId: com.hp.impulse.sprocket\n---\n- runFlow: {stage}.yaml\n",
                encoding="utf-8",
            )

        # Always write a human-readable checklist sidecar
        lines = [f"# {stage} — {len(cases)} ATP cases\n"]
        for c in cases:
            lines.append(f"- [ ] {c['test_id']} | {c['module']} | {c['description'][:100]}")
        (out_dir / "CHECKLIST.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"{stage}: {len(cases)} cases -> {out_dir}")


if __name__ == "__main__":
    main()
