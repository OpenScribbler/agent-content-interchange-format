from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .report import STATUSES
from .vectors import CatalogSet

SCOPE_ORDER = ["core", "hook", "skill", "rule", "command", "agent", "mcp", "publisher", "registry", "render", "install"]
L1_SCOPES = {"hook", "skill", "rule", "command", "agent", "mcp"}
PREREQUISITES = {
    "hook": {"core"},
    "skill": {"core"},
    "rule": {"core"},
    "command": {"core"},
    "agent": {"core"},
    "mcp": {"core"},
    "publisher": {"core"},
    "registry": {"core"},
    "render": {"core"},
    "install": {"core"},
}
STATUS_BLOCKERS = {"fail", "unsupported", "env-blocked", "harness-error"}


def scopes_path() -> Path:
    return Path(__file__).resolve().parent / "scopes.yaml"


def load_scope_map() -> dict[str, list[str]]:
    data = yaml.safe_load(scopes_path().read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("scopes.yaml must contain a mapping")
    out: dict[str, list[str]] = {}
    for scope, ids in data.items():
        if scope not in SCOPE_ORDER:
            raise ValueError(f"unknown scope in scopes.yaml: {scope}")
        if not isinstance(ids, list) or not all(isinstance(i, str) for i in ids):
            raise ValueError(f"scope {scope} must map to a list of vector ids")
        out[scope] = ids
    return out


def scope_closure(scopes: set[str], claimed_scopes: set[str] | None = None) -> set[str]:
    claimed_scopes = claimed_scopes or set(scopes)
    closure = set(scopes)
    changed = True
    while changed:
        changed = False
        for scope in list(closure):
            for prereq in PREREQUISITES.get(scope, set()):
                if prereq not in closure:
                    closure.add(prereq)
                    changed = True
    if "render" in closure:
        l1 = claimed_scopes & L1_SCOPES
        if not l1:
            l1 = scopes & L1_SCOPES
        closure.update(l1)
        for scope in l1:
            closure.update(PREREQUISITES.get(scope, set()))
    return closure


def required_vector_ids(scopes: set[str], claimed_scopes: set[str] | None = None) -> set[str]:
    scope_map = load_scope_map()
    ids: set[str] = set()
    for scope in scope_closure(scopes, claimed_scopes):
        ids.update(scope_map.get(scope, []))
    return ids


def totality_check(catalogs: CatalogSet) -> list[str]:
    errors: list[str] = []
    scope_map = load_scope_map()
    catalog_ids = set(catalogs.by_id)
    scoped_ids = {vid for ids in scope_map.values() for vid in ids}
    for vid in sorted(catalog_ids - scoped_ids):
        errors.append(f"vector id is not assigned to any scope: {vid}")
    for vid in sorted(scoped_ids - catalog_ids):
        errors.append(f"scoped id does not exist in catalogs: {vid}")
    return errors


def summarize_scopes(
    *,
    requested_scopes: set[str],
    claimed_scopes: set[str],
    vector_statuses: dict[str, str],
) -> dict[str, dict[str, Any]]:
    scope_map = load_scope_map()
    summary: dict[str, dict[str, Any]] = {}
    considered = requested_scopes or claimed_scopes
    for scope in SCOPE_ORDER:
        if scope not in considered:
            continue
        if scope not in claimed_scopes:
            summary[scope] = {"status": "not-claimed", "blocking": []}
            continue
        if scope == "render" and not (claimed_scopes & L1_SCOPES):
            summary[scope] = {"status": "not-passed", "blocking": ["render requires at least one claimed L1 scope"]}
            continue
        ids: set[str] = set()
        for expanded in scope_closure({scope}, claimed_scopes):
            ids.update(scope_map.get(expanded, []))
        blockers = [
            {"id": vid, "status": vector_statuses.get(vid, "out-of-scope")}
            for vid in sorted(ids)
            if vector_statuses.get(vid) in STATUS_BLOCKERS or vector_statuses.get(vid) != "pass"
        ]
        summary[scope] = {"status": "pass" if not blockers else "not-passed", "blocking": blockers}
    for status in vector_statuses.values():
        if status not in STATUSES:
            raise ValueError(f"unknown status in scope summary: {status}")
    return summary
