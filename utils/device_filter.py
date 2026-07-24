"""
Restrict Maestro / ATP runs to Samsung USB devices only (exclude Motorola and others).

Set ATP_SAMSUNG_ONLY=0 to disable (not recommended for this project).
Optional override: ATP_DEVICE_SERIAL=RZCWA2B05RB pins a single Samsung serial.
"""
from __future__ import annotations

import os
import re
import subprocess

# Lab inventory (serials are stable; manufacturer/model checked via adb when possible).
_KNOWN_SAMSUNG_SERIALS = frozenset({"rzcwa2b05rb"})
_KNOWN_MOTOROLA_SERIALS = frozenset({"za222rfq75"})


def samsung_only_enabled() -> bool:
    """Opt-in only (local Sprocket checks). Jenkins / default runs: off."""
    v = (os.environ.get("ATP_SAMSUNG_ONLY") or "0").strip().lower()
    return v in ("1", "true", "yes", "on")


def pinned_device_serial() -> str:
    return (os.environ.get("ATP_DEVICE_SERIAL") or "").strip()


def _adb_prop(device_id: str, prop: str) -> str:
    try:
        r = subprocess.run(
            ["adb", "-s", device_id, "shell", "getprop", prop],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=20,
        )
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
        return ""
    return re.sub(r"[\r\n].*", "", (r.stdout or "")).strip()


def device_manufacturer(device_id: str) -> str:
    return _adb_prop(device_id, "ro.product.manufacturer").lower()


def device_model(device_id: str) -> str:
    return _adb_prop(device_id, "ro.product.model").lower()


def is_motorola_device(device_id: str) -> bool:
    s = (device_id or "").strip().lower()
    if s in _KNOWN_MOTOROLA_SERIALS:
        return True
    mfr = device_manufacturer(device_id)
    model = device_model(device_id)
    return "motorola" in mfr or "moto" in model or model.startswith("moto")


def is_samsung_device(device_id: str) -> bool:
    s = (device_id or "").strip()
    if not s:
        return False
    sl = s.lower()
    if sl in _KNOWN_MOTOROLA_SERIALS:
        return False
    if sl in _KNOWN_SAMSUNG_SERIALS:
        return True
    mfr = device_manufacturer(s)
    model = device_model(s)
    if "motorola" in mfr or "moto" in model:
        return False
    if "samsung" in mfr:
        return True
    if model.startswith("sm-"):
        return True
    return False


def filter_samsung_devices(serials: list[str]) -> list[str]:
    """Return only Samsung serials; preserve order."""
    if not serials:
        return []
    pin = pinned_device_serial()
    if pin:
        return [s for s in serials if s.strip() == pin]
    if not samsung_only_enabled():
        return list(serials)
    out: list[str] = []
    for s in serials:
        t = (s or "").strip()
        if not t:
            continue
        if is_samsung_device(t):
            out.append(t)
    return out


def describe_rejected_devices(serials: list[str]) -> str:
    parts: list[str] = []
    for s in serials:
        t = (s or "").strip()
        if not t or is_samsung_device(t):
            continue
        mfr = device_manufacturer(t) or "unknown"
        model = device_model(t) or "unknown"
        parts.append(f"{t} ({mfr} / {model})")
    return ", ".join(parts)


def require_samsung_devices(serials: list[str]) -> list[str]:
    """
    Filter to Samsung-only. Raises RuntimeError when Samsung-only is on but no Samsung device is available.
    """
    pin = pinned_device_serial()
    if pin:
        filtered = [s for s in serials if s.strip() == pin]
        if not filtered:
            raise RuntimeError(
                f"ATP_DEVICE_SERIAL={pin} is not connected. "
                f"Connected: {', '.join(serials) or '(none)'}"
            )
        return filtered

    if not samsung_only_enabled():
        return list(serials)

    filtered = filter_samsung_devices(serials)
    if filtered:
        return filtered

    rejected = describe_rejected_devices(serials)
    raise RuntimeError(
        "Samsung device required (ATP_SAMSUNG_ONLY=1). "
        f"Connect Samsung USB device (e.g. RZCWA2B05RB / Samsung M34). "
        f"Rejected non-Samsung: {rejected or 'none listed'}. "
        "Disconnect Motorola and other non-Samsung phones from this agent."
    )
