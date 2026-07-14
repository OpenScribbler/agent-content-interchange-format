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
        ("appendix-a payload pins", check_appendix_payload_pins),
        ("verdict-reason gating", check_verdict_reason_gating),
        ("protocol round-trip", check_protocol_roundtrip),
        ("scopes totality", check_scopes_totality),
        ("suite manifest", check_suite_manifest),
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


APPENDIX_PIN_ROW_RE = re.compile(r"^\|\s*`(acif\.[a-z_.]+)`\s*\|.*\|\s*(TV-[A-Za-z0-9-]+)\s*\|$")


def check_appendix_payload_pins() -> None:
    """PROTOCOL.md §3.1: Appendix A pins the params of every diagnostic a
    vector asserts payload content for — both directions."""
    catalogs = load_catalogs()
    bindings.load_all()
    pinned = _appendix_payload_pins()
    asserted: set[tuple[str, str]] = set()
    for vid in sorted(bindings.bound_ids()):
        vector = catalogs.by_id[vid]
        with tempfile.TemporaryDirectory(prefix="acif-selftest-fixtures-") as tmp:
            result = bindings.get(vid)(vector, _StubSession(), _StubContext(tmp))
        for check in result.checks:
            expected = check.get("expected")
            if check.get("field") == "diagnostic" and isinstance(expected, dict) and "params" in expected:
                asserted.add((expected["id"], vid))
    problems = [
        f"{vid} asserts params of {diag_id} but Appendix A does not pin it to that vector"
        for diag_id, vid in sorted(asserted)
        if vid not in pinned.get(diag_id, set())
    ]
    problems.extend(
        f"Appendix A pins {diag_id} to {vid}, which does not assert its params"
        for diag_id, vids in sorted(pinned.items())
        for vid in sorted(vids)
        if (diag_id, vid) not in asserted
    )
    if problems:
        raise AssertionError("; ".join(problems))


def _appendix_payload_pins() -> dict[str, set[str]]:
    text = (CONFORMANCE_ROOT / "runner" / "PROTOCOL.md").read_text(encoding="utf-8")
    section = text.split("Payload-pinned (a vector asserts params content):", 1)[1].split("Identifier-only", 1)[0]
    pins: dict[str, set[str]] = {}
    for line in section.splitlines():
        match = APPENDIX_PIN_ROW_RE.match(line.strip())
        if match:
            pins.setdefault(match.group(1), set()).add(match.group(2))
    return pins


def _asserted_literals(value: Any, parent_key: str | None = None) -> set[str]:
    out: set[str] = set()
    if isinstance(value, dict):
        for key, child in value.items():
            # reason_note is the catalog's informative annotation (the
            # pre-flip free-text reason strings); reason itself is asserted.
            if key == "reason_note":
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


class _VerdictSession:
    """Scripted session answering each request with the next canned verdict."""

    def __init__(self, protocol: int, results: list[dict[str, Any]]):
        self.hello = {"adapter_protocol": protocol}
        self._results = results

    def request(self, request: dict[str, Any]) -> AdapterResponse:
        result = self._results.pop(0)
        raw = {"ok": True, "result": result}
        return AdapterResponse(
            kind="ok",
            request_line=encode_request(request),
            response_line=str(raw),
            raw=raw,
            result=result,
        )


def check_verdict_reason_gating() -> None:
    """PROTOCOL §3: verdict reasons (and their Appendix-A param shapes) are
    asserted exact-string for adapters declaring adapter_protocol >= 2, and
    stay unasserted for adapters declaring 1 — never retroactive."""
    catalogs = load_catalogs()
    bindings.load_all()

    def run(vid: str, protocol: int, results: list[dict[str, Any]]) -> bool:
        vector = catalogs.by_id[vid]
        session = _VerdictSession(protocol, list(results))
        with tempfile.TemporaryDirectory(prefix="acif-selftest-fixtures-") as tmp:
            result = bindings.get(vid)(vector, session, _StubContext(tmp))
        return result.status == "pass" and all(check["pass"] for check in result.checks)

    tv11 = catalogs.by_id["TV-11"]
    minted = [{"conformant": False, "reason": tv11.data["expect"][f"case_{i}"]["reason"]} for i in range(1, 5)]
    free_text = [{"conformant": False, "reason": tv11.data["expect"][f"case_{i}"]["reason_note"]} for i in range(1, 5)]
    if not run("TV-11", 2, minted):
        raise AssertionError("protocol-2 adapter emitting minted identifiers must pass TV-11")
    if run("TV-11", 2, free_text):
        raise AssertionError("protocol-2 adapter emitting free-text reasons must fail TV-11")
    if not run("TV-11", 1, free_text):
        raise AssertionError("protocol-1 adapter must stay unasserted on reason")

    tv6 = catalogs.by_id["TV-6"]
    with_params = [{"conformant": False, "reason": tv6.data["expect"]["reason"], "params": dict(tv6.data["expect"]["params"])}]
    without_params = [{"conformant": False, "reason": tv6.data["expect"]["reason"]}]
    if not run("TV-6", 2, with_params):
        raise AssertionError("protocol-2 adapter carrying the pinned field param must pass TV-6")
    if run("TV-6", 2, without_params):
        raise AssertionError("protocol-2 adapter omitting the pinned field param must fail TV-6")
    if not run("TV-6", 1, without_params):
        raise AssertionError("protocol-1 adapter must stay unasserted on verdict params")


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
        if hello.get("adapter_protocol") != 2:
            raise AssertionError("canned adapter did not negotiate protocol 2")
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


def check_suite_manifest() -> None:
    manifest_path = CONFORMANCE_ROOT / "suite-manifest.yaml"
    entries = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(entries, list) or not entries:
        raise AssertionError("suite-manifest.yaml is empty or not a list")
    head = max(entries, key=lambda e: e["suite"])
    catalogs = load_catalogs()
    bindings.load_all()
    drift: list[str] = []
    if head["catalogs"] != catalogs.catalog_hashes:
        changed = sorted(
            name
            for name in set(head["catalogs"]) | set(catalogs.catalog_hashes)
            if head["catalogs"].get(name) != catalogs.catalog_hashes.get(name)
        )
        drift.append("catalogs: " + ", ".join(changed))
    if head["binding_set"] != bindings.binding_set_hash():
        drift.append("binding_set")
    if head["vectors"] != len(catalogs.by_id):
        drift.append(f"vectors: manifest {head['vectors']} != suite {len(catalogs.by_id)}")
    if drift:
        raise AssertionError(
            "manifest head (suite %s) drifted from the working tree — append a manifest entry per CHANGE-PROCESS.md: %s"
            % (head["suite"], "; ".join(drift))
        )


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
