"""Module selection and execution-plan builder (WHAT to run).

Does not schedule devices or change ATP_DEVICE_EXECUTION / ATP_SCHEDULER.
The existing orchestrator still decides HOW tests run across phones.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from .atp_folder_paths import (
    discover_atp_yaml_files,
    list_atp_modules,
    resolve_atp_subfolder,
)


class UnknownModuleError(ValueError):
    """Raised when the user names a module that is not an ATP TestCase Flows folder."""


@dataclass(frozen=True)
class PlannedFlow:
    module: str
    case_id: str
    path: Path


@dataclass
class ExecutionPlan:
    modules: list[str]
    flows: list[PlannedFlow] = field(default_factory=list)
    duplicates_skipped: list[str] = field(default_factory=list)
    empty_modules_skipped: list[str] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.flows)


def _case_id(path: Path) -> str:
    return path.stem.split(" - ", 1)[0].strip() or path.stem


def parse_module_spec(raw: str, *, available: list[str]) -> list[str]:
    """Parse ALL / comma/semicolon/space list. Unknown names raise UnknownModuleError."""
    text = (raw or "").strip()
    if not text or text.lower() in ("all", "*"):
        return list(available)
    tokens = [t for t in re.split(r"[,;\s]+", text) if t]
    if any(t.lower() in ("all", "*") for t in tokens):
        return list(available)
    avail_map = {a.lower(): a for a in available}
    alias = {a.replace("-", "_").lower(): a for a in available}
    resolved: list[str] = []
    unknown: list[str] = []
    seen: set[str] = set()
    for token in tokens:
        key = token.lower()
        name = avail_map.get(key) or alias.get(key.replace("-", "_"))
        if not name:
            unknown.append(token)
            continue
        if name not in seen:
            seen.add(name)
            resolved.append(name)
    if unknown:
        raise UnknownModuleError(
            "ERROR: Unknown module '{0}'\nAvailable modules:\n{1}".format(
                "', '".join(unknown),
                "\n".join(f"  {m}" for m in available),
            )
        )
    if not resolved:
        raise UnknownModuleError(
            "ERROR: No modules selected.\nAvailable modules:\n"
            + "\n".join(f"  {m}" for m in available)
        )
    return resolved


def build_execution_plan(repo: Path, module_spec: str) -> ExecutionPlan:
    available = list_atp_modules(repo)
    modules = parse_module_spec(module_spec, available=available)
    flows: list[PlannedFlow] = []
    skipped: list[str] = []
    empty: list[str] = []
    kept: list[str] = []
    seen: set[tuple[str, str]] = set()
    for folder in modules:
        resolved = resolve_atp_subfolder(repo, folder) or folder
        found = discover_atp_yaml_files(repo, resolved, exclude_subflows=True)
        if not found:
            empty.append(resolved)
            continue
        kept.append(resolved)
        for path in found:
            cid = _case_id(path)
            key = (resolved.lower(), path.resolve().as_posix().lower())
            if key in seen:
                skipped.append(f"{resolved}/{cid}")
                continue
            seen.add(key)
            flows.append(PlannedFlow(module=resolved, case_id=cid, path=path))
    return ExecutionPlan(
        modules=kept,
        flows=flows,
        duplicates_skipped=skipped,
        empty_modules_skipped=empty,
    )


def log_execution_plan(plan: ExecutionPlan) -> None:
    print("Execution Plan", flush=True)
    print(f"Selected modules: {', '.join(plan.modules)}", flush=True)
    print(f"Total planned tests: {plan.total}", flush=True)
    if plan.empty_modules_skipped:
        print(
            f"Empty modules skipped (no top-level YAML): {', '.join(plan.empty_modules_skipped)}",
            flush=True,
        )
    if plan.duplicates_skipped:
        print(
            f"Duplicate tests skipped: {len(plan.duplicates_skipped)} ({', '.join(plan.duplicates_skipped[:20])})",
            flush=True,
        )
    by_mod: dict[str, list[PlannedFlow]] = {}
    for fl in plan.flows:
        by_mod.setdefault(fl.module, []).append(fl)
    for mod in plan.modules:
        print(f"Module: {mod}", flush=True)
        for fl in by_mod.get(mod, []):
            print(f"  {fl.case_id}", flush=True)
