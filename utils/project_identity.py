"""Canonical project and app identifiers (HP Sprocket Android)."""

from __future__ import annotations

PROJECT_DISPLAY_NAME = "HP Sprocket Android"
PROJECT_SHORT_NAME = "Sprocket Android"
APP_PACKAGE_DEFAULT = "com.hp.impulse.sprocket"
GITHUB_REPO_URL = "https://github.com/testing71794-cloud/New-Sprocket-Android"
OPENROUTER_APP_TITLE_DEFAULT = f"{PROJECT_SHORT_NAME} Automation"
EXECUTION_SUMMARY_TITLE = f"{PROJECT_DISPLAY_NAME} Execution Summary"

# Legacy Jenkins job parameters / old app ids (Smile + Step Print)
LEGACY_APP_PACKAGES = frozenset(
    {
        "com.kodaksmile",
        "com.kodaksmile.dev",
        "com.kodak.steptouch",
    }
)


def normalize_app_package(app_id: str) -> str:
    """Map legacy Smile / Step Print package ids to HP Sprocket Android default."""
    raw = (app_id or "").strip()
    if not raw or raw in LEGACY_APP_PACKAGES:
        return APP_PACKAGE_DEFAULT
    return raw
