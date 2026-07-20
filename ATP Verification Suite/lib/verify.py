"""Non-throwing verification helpers — always return PASS/FAIL with reason."""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional

from .hierarchy import Hierarchy


@dataclass
class VerifyResult:
    status: str  # PASS | FAIL
    reason: str
    actual: str = ""

    @property
    def ok(self) -> bool:
        return self.status == "PASS"


def _fail(reason: str, actual: str = "") -> VerifyResult:
    return VerifyResult(status="FAIL", reason=reason, actual=actual or reason)


def _pass(actual: str = "OK") -> VerifyResult:
    return VerifyResult(status="PASS", reason="", actual=actual)


def _with_retry(fn, retries: int = 2, delay: float = 0.5) -> VerifyResult:
    last: Optional[VerifyResult] = None
    for attempt in range(retries + 1):
        try:
            last = fn()
            if last.ok:
                return last
        except Exception as exc:  # noqa: BLE001
            last = _fail(f"exception: {exc}")
        if attempt < retries:
            time.sleep(delay)
    return last or _fail("unknown failure")


def verifyVisible(h: Hierarchy, selector: str, refresh: bool = True) -> VerifyResult:
    def run() -> VerifyResult:
        if refresh:
            if not h.refresh():
                return _fail("hierarchy dump failed", "no hierarchy")
        hits = h.find(selector)
        if hits:
            labels = [x.content_desc or x.text for x in hits[:3]]
            return _pass(f"visible: {labels}")
        return _fail(f"not visible: {selector}", f"selector '{selector}' not in hierarchy")

    return _with_retry(run)


def verifyNotVisible(h: Hierarchy, selector: str, refresh: bool = True) -> VerifyResult:
    def run() -> VerifyResult:
        if refresh:
            if not h.refresh():
                return _fail("hierarchy dump failed", "no hierarchy")
        hits = h.find(selector)
        if not hits:
            return _pass(f"not visible: {selector}")
        return _fail(f"still visible: {selector}", f"found {[x.content_desc or x.text for x in hits[:2]]}")

    return _with_retry(run)


def verifyText(h: Hierarchy, selector: str, refresh: bool = True) -> VerifyResult:
    return verifyVisible(h, selector, refresh=refresh)


def verifyEnabled(h: Hierarchy, selector: str, refresh: bool = True) -> VerifyResult:
    def run() -> VerifyResult:
        if refresh and not h.refresh():
            return _fail("hierarchy dump failed")
        hits = h.find(selector)
        if not hits:
            return _fail(f"element not found: {selector}")
        if any(x.enabled for x in hits):
            return _pass(f"enabled: {selector}")
        return _fail(f"disabled: {selector}", "enabled=false")

    return _with_retry(run)


def verifyDisabled(h: Hierarchy, selector: str, refresh: bool = True) -> VerifyResult:
    def run() -> VerifyResult:
        if refresh and not h.refresh():
            return _fail("hierarchy dump failed")
        hits = h.find(selector)
        if not hits:
            return _fail(f"element not found: {selector}")
        if all(not x.enabled for x in hits):
            return _pass(f"disabled: {selector}")
        return _fail(f"enabled unexpectedly: {selector}", "enabled=true")

    return _with_retry(run)


def verifyImage(h: Hierarchy, selector: str, refresh: bool = True) -> VerifyResult:
    # Accessibility often exposes logos as content-desc / ImageView without text.
    return verifyVisible(h, selector, refresh=refresh)


def verifyNavigation(h: Hierarchy, expected_screen_marker: str, refresh: bool = True) -> VerifyResult:
    return verifyVisible(h, expected_screen_marker, refresh=refresh)


def verifyToast(h: Hierarchy, text: str, refresh: bool = True) -> VerifyResult:
    # Toasts are transient; single refresh best-effort.
    return verifyVisible(h, text, refresh=refresh)


def verifyDialog(h: Hierarchy, text: str, refresh: bool = True) -> VerifyResult:
    return verifyVisible(h, text, refresh=refresh)


def verifyPermission(h: Hierarchy, text: str = "Allow", refresh: bool = True) -> VerifyResult:
    # Permission dialogs: Allow / While using / Allow all / Don't allow
    for candidate in (text, "Allow all", "While using the app", "Allow", "Don't allow"):
        r = verifyVisible(h, candidate, refresh=refresh)
        if r.ok:
            return _pass(f"permission UI: {candidate}")
        refresh = False
    return _fail("permission dialog not detected", "no Allow/Don't allow")
