"""Canonical project and app identifiers (Kodak Step Print Android)."""

from __future__ import annotations

PROJECT_DISPLAY_NAME = "Kodak Step Print Android"
PROJECT_SHORT_NAME = "Kodak Step Print"
APP_PACKAGE_DEFAULT = "com.kodak.steptouch"
GITHUB_REPO_URL = "https://github.com/testing71794-cloud/Kodak-Step-print-Android"
OPENROUTER_APP_TITLE_DEFAULT = f"{PROJECT_SHORT_NAME} Automation"
EXECUTION_SUMMARY_TITLE = f"{PROJECT_DISPLAY_NAME} Execution Summary"

# Legacy Jenkins job parameters / old Smile app id
LEGACY_APP_PACKAGES = frozenset({"com.kodaksmile", "com.kodaksmile.dev"})


def normalize_app_package(app_id: str) -> str:
    """Map legacy Smile package ids to Kodak Step Print Android default."""
    raw = (app_id or "").strip()
    if not raw or raw in LEGACY_APP_PACKAGES:
        return APP_PACKAGE_DEFAULT
    return raw
