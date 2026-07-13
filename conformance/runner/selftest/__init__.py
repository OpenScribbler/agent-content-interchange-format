from __future__ import annotations

import re
import sys
import tempfile
from pathlib import Path
from typing import Any

import yaml

from .. import bindings
from ..protocol import AdapterResponse, AdapterSession, encode_request
from ..run import RunOptions, run_conformance
from ..scopes import totality_check
from ..vectors import load_catalogs

CONFORMANCE_ROOT = Path(__file__).resolve().parents[2]
HASH_RE = re.compile(r"^[0-9a-f]{64}$")
SABOTAGE_MUTATORS = ("field", "distinct-perturb", "memoize")


def main(argv: list[str] | None = None) -> int:
    del argv
    checks = [
        ("binding coverage", check_binding_coverage),
        ("anti-softening", check_anti_softening),
        ("protocol round-trip", check_protocol_roundtrip),
        ("scopes totality", check_scopes_totality),
        ("sabotage", check_sabotage),
    ]
    failures: list[str] = []
    for name, check in checks:
        try:
            check()
            print(f"ok - {name}")
        except Exception as exc:
            failures.append(f"{name}: {exc}")
            print(f"not ok - {name}: {exc}")
    if failures:
        print("")
        print("selftest failures:")
        for failure in failures:
            print(f"  {failure}")
        return 1
    return 0


def check_binding_coverage() -> None:
    catalogs = load_catalogs()
    errors = bindings.coverage_errors(catalogs)
    if errors:
        raise AssertionError("; ".join(errors))


def check_anti_softening() -> None:
    catalogs = load_catalogs()
    bindings.load_all()
    literals: set[str] = set()
    collected: set[Any] = set()
    for vid in sorted(bindings.bound_ids()):
        vector = catalogs.by_id[vid]
        literals.update(_asserted_literals(vector.data.get("expect")))
        with tempfile.TemporaryDirectory(prefix="acif-selftest-fixtures-") as tmp:
            result = bindings.get(vid)(vector, _StubSession(), _StubContext(tmp))  # type: ignore[misc]
        for check in result.checks:
            collected.update(_flatten_expected(check.get("expected")))
        collected.update(result.expected_literals)
    missing = sorted(lit for lit in literals if lit not in collected)
    if missing:
        raise AssertionError("runtime assertions did not collect expect literal(s): " + ", ".join(missing))


def _asserted_literals(value: Any, parent_key: str | None = None) -> set[str]:
    out: set[str] = set()
    if isinstance(value, dict):
        for key, child in value.items():
            if key == "reason":
                continue
            out.update(_asserted_literals(child, key))
    elif isinstance(value, list):
        for child in value:
            out.update(_asserted_literals(child, parent_key))
    elif isinstance(value, str):
        if HASH_RE.match(value) or value.startswith("acif.") or _is_enumish(value):
            out.add(value)
    return out


def _is_enumish(value: str) -> bool:
    return bool(re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.-]*", value))


def _flatten_expected(value: Any) -> set[Any]:
    if isinstance(value, dict):
        out: set[Any] = set()
        for child in value.values():
            out.update(_flatten_expected(child))
        return out
    if isinstance(value, list):
        out: set[Any] = set()
        for child in value:
            out.update(_flatten_expected(child))
        return out
    return {value}


class _StubSession:
    def request(self, request: dict[str, Any]) -> AdapterResponse:
        return AdapterResponse(
            kind="ok",
            request_line=encode_request(request),
            response_line='{"ok":true,"result":{}}',
            raw={"ok": True, "result": {}},
            result={},
        )


class _StubContext:
    def __init__(self, fixture_root: str):
        self.fixture_root = fixture_root
        self.observations: list[Any] = []

    def materialize(self, files: dict[str, Any]) -> str:
        del files
        return self.fixture_root


def check_protocol_roundtrip() -> None:
    command = f"{sys.executable} -m runner.selftest.canned_adapter"
    session = AdapterSession(command, cwd=CONFORMANCE_ROOT)
    try:
        hello = session.start()
        if hello.get("adapter_protocol") != 1:
            raise AssertionError("canned adapter did not negotiate protocol 1")
        response = session.request({"op": "ingest", "input": {"kind": "hook", "sidecar": {}}})
        if response.kind != "ok":
            raise AssertionError(f"expected ok response, got {response.kind}")
        if not isinstance(response.result, dict) or "body_hash" not in response.result:
            raise AssertionError("ok response did not carry the expected result shape")
        unsupported = session.request({"op": "not_real", "input": {}})
        if unsupported.kind != "unsupported":
            raise AssertionError(f"expected unsupported response, got {unsupported.kind}")
    finally:
        session.close()


def check_scopes_totality() -> None:
    errors = totality_check(load_catalogs())
    if errors:
        raise AssertionError("; ".join(errors))


def check_sabotage() -> None:
    catalogs = load_catalogs()
    base = run_conformance(
        RunOptions(
            adapter=f"{sys.executable} adapters/reference.py",
            cwd=str(CONFORMANCE_ROOT),
        )
    )
    mutated_reports = {
        mutator: run_conformance(
            RunOptions(
                adapter=f"{sys.executable} -m runner.selftest.mutating_adapter --mode {mutator} -- {sys.executable} adapters/reference.py",
                cwd=str(CONFORMANCE_ROOT),
            )
        )
        for mutator in SABOTAGE_MUTATORS
    }
    base_rows = {row["id"]: row for row in base["vectors"]}
    mutated_rows = {
        mutator: {row["id"]: row for row in report["vectors"]}
        for mutator, report in mutated_reports.items()
    }
    catalog_ids = set(catalogs.by_id)
    missing = sorted(catalog_ids - set(base_rows))
    if missing:
        raise AssertionError("vector ids missing from report: " + ", ".join(missing))
    failures: list[str] = []
    killed_by: dict[str, str] = {}
    skip = {"unsupported", "harness-error", "out-of-scope", "env-blocked"}
    for vid in sorted(catalog_ids):
        base_status = base_rows[vid]["status"]
        if base_status in skip or base_rows[vid].get("vacuous"):
            continue
        killers = [
            mutator
            for mutator in SABOTAGE_MUTATORS
            if mutated_rows[mutator].get(vid, {}).get("status") == "fail"
        ]
        if not killers:
            statuses = {mutator: mutated_rows[mutator].get(vid, {}).get("status") for mutator in SABOTAGE_MUTATORS}
            failures.append(f"{vid}: no mutator killed vector (baseline {base_status}, mutated {statuses})")
        else:
            killed_by[vid] = killers[0]
    if failures:
        raise AssertionError("; ".join(failures))
    counts = {mutator: list(killed_by.values()).count(mutator) for mutator in SABOTAGE_MUTATORS}
    print(
        "sabotage kill summary: "
        + ", ".join(f"{mutator}={counts[mutator]}" for mutator in SABOTAGE_MUTATORS)
    )
    print("sabotage kill map: " + ", ".join(f"{vid}={killed_by[vid]}" for vid in sorted(killed_by)))
