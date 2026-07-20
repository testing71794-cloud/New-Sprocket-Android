"""Resolve Jenkins ATP stage folder names to on-disk ATP TestCase Flows directories."""
from __future__ import annotations

import re
from pathlib import Path

# Legacy Kodak Smile Jenkins stage names → Sprocket Android ATP folders.
_CANONICAL_BY_KEY: dict[str, str] = {
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
}


def _norm_key(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (name or "").strip().lower())


def resolve_atp_subfolder(repo: Path, folder: str) -> str:
    """
    Map stage argument (e.g. Connection, SignUp_Login) to actual child folder name
  (e.g. connection, signup-login) using case-insensitive directory match.
    """
    raw = (folder or "").strip()
    if not raw:
        return ""
    target = _CANONICAL_BY_KEY.get(_norm_key(raw), raw)
    atp_root = repo / "ATP TestCase Flows"
    if atp_root.is_dir():
        for child in sorted(atp_root.iterdir()):
            if child.is_dir() and child.name.lower() == target.lower():
                return child.name
    return target


def is_subflow_helper(path: Path) -> bool:
    """Reusable Maestro subflows are run via runFlow, not as top-level Jenkins tests."""
    return any(part.lower() == "subflows" for part in path.parts)


def discover_atp_yaml_files(repo: Path, atp_subfolder: str, *, exclude_subflows: bool = True) -> list[Path]:
    atp_root = repo / "ATP TestCase Flows"
    if not atp_root.is_dir():
        return []
    sub = resolve_atp_subfolder(repo, atp_subfolder) if (atp_subfolder or "").strip() else ""
    if sub:
        folder_root = atp_root / sub
        if not folder_root.is_dir():
            return []
        roots = [folder_root]
    else:
        roots = [atp_root]
    flows: list[Path] = []
    for root in roots:
        for p in sorted(root.rglob("*"), key=lambda x: str(x).lower()):
            if not p.is_file() or p.suffix.lower() not in (".yaml", ".yml"):
                continue
            if exclude_subflows and is_subflow_helper(p):
                continue
            flows.append(p)
    return flows
