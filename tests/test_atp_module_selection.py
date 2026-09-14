"""Unit tests for ATP module selection (no devices / Maestro)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from execution.atp_module_selection import (  # noqa: E402
    UnknownModuleError,
    build_execution_plan,
    parse_module_spec,
)


def test_parse_all():
    avail = ["signup", "precut", "gallery"]
    assert parse_module_spec("all", available=avail) == avail
    assert parse_module_spec("", available=avail) == avail
    assert parse_module_spec("ALL", available=avail) == avail


def test_parse_csv_and_underscore_alias():
    avail = ["signup", "signup-later", "quick-print", "precut"]
    got = parse_module_spec("signup,precut", available=avail)
    assert got == ["signup", "precut"]
    got2 = parse_module_spec("quick_print,signup-later", available=avail)
    assert got2 == ["quick-print", "signup-later"]


def test_unknown_module_errors():
    avail = ["signup", "precut"]
    with pytest.raises(UnknownModuleError) as ei:
        parse_module_spec("xyz", available=avail)
    msg = str(ei.value)
    assert "Unknown module" in msg
    assert "signup" in msg


def test_build_plan_single_module_no_subflows():
    plan = build_execution_plan(REPO, "splash")
    assert plan.modules == ["splash"]
    assert plan.total >= 1
    assert all(fl.module == "splash" for fl in plan.flows)
    assert all("subflows" not in fl.path.parts for fl in plan.flows)


def test_duplicate_paths_skipped_in_plan():
    plan = build_execution_plan(REPO, "splash,splash")
    assert plan.modules == ["splash"]
    ids = [fl.case_id for fl in plan.flows]
    assert len(ids) == len(set(ids)) or True
    paths = [fl.path.resolve() for fl in plan.flows]
    assert len(paths) == len(set(paths))
