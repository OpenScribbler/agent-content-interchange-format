from __future__ import annotations

import re
import shlex
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

import yaml

from .. import bindings
from ..protocol import AdapterResponse, AdapterSession, ProtocolError, classify_response, encode_request
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
        ("capability-vocabulary sync", check_capability_vocabulary),
        ("diagnostic-ids sync", check_diagnostic_ids),
        ("source-mechanisms sync", check_source_mechanisms),
        ("hook event tables sync", check_hook_event_tables),
        ("install-entry-points sync", check_install_entry_points),
        ("absent fields never satisfy a relation", check_absent_relations),
        ("render-d structural lossy check", check_render_d_structural),
        ("protocol partial-line timeout", check_partial_line_timeout),
        ("handshake and response strictness", check_handshake_strictness),
        ("cli exit status", check_exit_status),
        ("differential clean discipline", check_differential_clean),
        ("sabotage credits only baseline passes", check_sabotage_baseline),
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


VOCABULARY_SPEC_DIRS = {
    "skill": "skill-interchange",
    "rule": "rule-interchange",
    "command": "command-interchange",
    "agent": "agent-interchange",
    "hook": "hooks-interchange",
    "mcp_config": "mcp-interchange",
}
BACKTICKED_KEY_RE = re.compile(r"`([a-z][a-z0-9_]*)`")
DERIVABLE_ROW_RE = re.compile(r"^\|\s*`([a-z][a-z0-9_]*)`\s*\|")


def check_capability_vocabulary() -> None:
    """capability-vocabulary.yaml must match each spec's Capability
    Dispositions section: DERIVABLE key sets exactly equal the §x.1
    tables; every out_of_scope_at_l1 key appears backticked inside an
    OUT-OF-SCOPE-AT-L1 subsection. Spec-prose parsing happens here, at
    the authority, so downstream copies diff against the yaml only."""
    vocab_path = CONFORMANCE_ROOT / "capability-vocabulary.yaml"
    document = yaml.safe_load(vocab_path.read_text(encoding="utf-8"))
    vocabulary = document.get("vocabulary") if isinstance(document, dict) else None
    if not isinstance(vocabulary, dict):
        raise AssertionError("capability-vocabulary.yaml missing vocabulary mapping")
    if set(vocabulary) != set(VOCABULARY_SPEC_DIRS):
        raise AssertionError(
            "vocabulary types %s != expected %s"
            % (sorted(vocabulary), sorted(VOCABULARY_SPEC_DIRS))
        )
    errors: list[str] = []
    specs_root = CONFORMANCE_ROOT.parent / "specs"
    for kind, entry in vocabulary.items():
        spec_text = (specs_root / VOCABULARY_SPEC_DIRS[kind] / "spec.md").read_text(encoding="utf-8")
        section = _dispositions_section(spec_text)
        if section is None:
            errors.append(f"{kind}: no Capability Dispositions section found")
            continue
        table_keys = _derivable_table_keys(section)
        declared = entry.get("derivable") or []
        if len(set(declared)) != len(declared):
            errors.append(f"{kind}: duplicate derivable keys")
        if set(declared) != set(table_keys):
            errors.append(
                f"{kind}: derivable drift — yaml {sorted(declared)} != spec table {sorted(table_keys)}"
            )
        out_text = _out_of_scope_text(section)
        for key in entry.get("out_of_scope_at_l1") or []:
            if f"`{key}`" not in out_text:
                errors.append(f"{kind}: out-of-scope key `{key}` not named in the spec's OUT-OF-SCOPE-AT-L1 subsection")
    if errors:
        raise AssertionError("; ".join(errors))


def _dispositions_section(spec_text: str) -> str | None:
    lines = spec_text.splitlines()
    start = None
    for idx, line in enumerate(lines):
        if start is None:
            if re.match(r"^## \d+\. Capability Dispositions", line):
                start = idx
        elif line.startswith("## "):
            return "\n".join(lines[start:idx])
    return "\n".join(lines[start:]) if start is not None else None


def _derivable_table_keys(section: str) -> list[str]:
    keys: list[str] = []
    in_derivable = False
    for line in section.splitlines():
        if line.startswith("### "):
            in_derivable = "DERIVABLE keys" in line
            continue
        if in_derivable:
            match = DERIVABLE_ROW_RE.match(line)
            if match and match.group(1) != "key":
                keys.append(match.group(1))
    return keys


def _out_of_scope_text(section: str) -> str:
    chunks: list[str] = []
    collecting = False
    for line in section.splitlines():
        if line.startswith("### "):
            collecting = "OUT-OF-SCOPE-AT-L1" in line
        if collecting:
            chunks.append(line)
    return "\n".join(chunks)


DIAGNOSTIC_CLASSES = ("reject", "diagnostic", "refuse")
ERROR_ID_ROW_RE = re.compile(r"^\|\s*`(acif\.[a-z0-9_.]+)`\s*\|\s*([a-z]+)")


def check_diagnostic_ids() -> None:
    """diagnostic-ids.yaml must match each L1 spec's Error Identifiers table:
    every identifier, grouped by its Class-column disposition token
    (reject|diagnostic|refuse), bidirectionally. Spec-prose parsing happens
    here, at the authority, so downstream copies diff against the yaml only.
    A type that mints no identifiers (agent) has all-empty buckets."""
    path = CONFORMANCE_ROOT / "diagnostic-ids.yaml"
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    diagnostics = document.get("diagnostics") if isinstance(document, dict) else None
    if not isinstance(diagnostics, dict):
        raise AssertionError("diagnostic-ids.yaml missing diagnostics mapping")
    if set(diagnostics) != set(VOCABULARY_SPEC_DIRS):
        raise AssertionError(
            "diagnostic types %s != expected %s"
            % (sorted(diagnostics), sorted(VOCABULARY_SPEC_DIRS))
        )
    errors: list[str] = []
    specs_root = CONFORMANCE_ROOT.parent / "specs"
    for kind, entry in diagnostics.items():
        extra = set(entry) - {"spec", "section"} - set(DIAGNOSTIC_CLASSES)
        if extra:
            errors.append(f"{kind}: unrecognized key(s) {sorted(extra)}")
        spec_text = (specs_root / VOCABULARY_SPEC_DIRS[kind] / "spec.md").read_text(encoding="utf-8")
        section = _error_identifiers_section(spec_text)
        if section is None:
            errors.append(f"{kind}: no Error Identifiers section found")
            continue
        spec_by_class = _error_id_rows(section)
        unknown = set(spec_by_class) - set(DIAGNOSTIC_CLASSES)
        if unknown:
            errors.append(f"{kind}: spec table has unrecognized class token(s) {sorted(unknown)}")
        for cls in DIAGNOSTIC_CLASSES:
            declared = entry.get(cls) or []
            if len(set(declared)) != len(declared):
                errors.append(f"{kind}: duplicate {cls} ids")
            if set(declared) != spec_by_class.get(cls, set()):
                errors.append(
                    f"{kind}: {cls} drift — yaml {sorted(declared)} != spec table {sorted(spec_by_class.get(cls, set()))}"
                )
    if errors:
        raise AssertionError("; ".join(errors))


def _error_identifiers_section(spec_text: str) -> str | None:
    lines = spec_text.splitlines()
    start = None
    for idx, line in enumerate(lines):
        if start is None:
            if re.match(r"^## \d+\. Error Identifiers", line):
                start = idx
        elif line.startswith("## "):
            return "\n".join(lines[start:idx])
    return "\n".join(lines[start:]) if start is not None else None


def _error_id_rows(section: str) -> dict[str, set[str]]:
    by_class: dict[str, set[str]] = {}
    for line in section.splitlines():
        match = ERROR_ID_ROW_RE.match(line.strip())
        if match:
            by_class.setdefault(match.group(2), set()).add(match.group(1))
    return by_class


SOURCE_MECHANISM_SECTIONS = {
    "rule": ("rule-interchange", r"^### A\.2 "),
    "hook": ("hooks-interchange", r"^### 7\.4 "),
}
TOKEN_ROW_RE = re.compile(r"^\|\s*`([a-z][a-z0-9_-]*)`(?:\s*\(alias\s*`([a-z][a-z0-9_-]*)`\))?\s*\|")


def check_source_mechanisms() -> None:
    """source-mechanisms.yaml must match the token column of [ACIF-RULE]
    Appendix A.2 and [ACIF-HOOK] §7.4 — token set, alias map, and
    recognition-requiring markings, bidirectionally. Spec-prose parsing
    happens here, at the authority, so downstream copies diff against the
    yaml only."""
    path = CONFORMANCE_ROOT / "source-mechanisms.yaml"
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    mechanisms = document.get("source_mechanisms") if isinstance(document, dict) else None
    if not isinstance(mechanisms, dict):
        raise AssertionError("source-mechanisms.yaml missing source_mechanisms mapping")
    if set(mechanisms) != set(SOURCE_MECHANISM_SECTIONS):
        raise AssertionError(
            "source-mechanism types %s != expected %s"
            % (sorted(mechanisms), sorted(SOURCE_MECHANISM_SECTIONS))
        )
    errors: list[str] = []
    specs_root = CONFORMANCE_ROOT.parent / "specs"
    for kind, (spec_dir, heading_re) in SOURCE_MECHANISM_SECTIONS.items():
        entry = mechanisms[kind]
        spec_text = (specs_root / spec_dir / "spec.md").read_text(encoding="utf-8")
        section = _spec_section(spec_text, heading_re)
        if section is None:
            errors.append(f"{kind}: no token-table section found")
            continue
        spec_tokens: dict[str, bool] = {}
        spec_aliases: dict[str, str] = {}
        for line in section.splitlines():
            match = TOKEN_ROW_RE.match(line.strip())
            if not match:
                continue
            spec_tokens[match.group(1)] = "recognition-requiring" in line.lower()
            if match.group(2):
                spec_aliases[match.group(2)] = match.group(1)
        if kind == "hook" and "Every mechanism row is **recognition-requiring**" in section:
            spec_tokens = {token: True for token in spec_tokens}
        declared = {row["token"]: bool(row["recognition_requiring"]) for row in entry.get("tokens") or []}
        if len(declared) != len(entry.get("tokens") or []):
            errors.append(f"{kind}: duplicate tokens")
        if declared != spec_tokens:
            errors.append(f"{kind}: token drift — yaml {sorted(declared.items())} != spec table {sorted(spec_tokens.items())}")
        if (entry.get("aliases") or {}) != spec_aliases:
            errors.append(f"{kind}: alias drift — yaml {entry.get('aliases')} != spec table {spec_aliases}")
    if errors:
        raise AssertionError("; ".join(errors))


HOOK_A1_ROW_RE = re.compile(r"^\|\s*`([a-z][a-z0-9_]*)`\s*\|\s*(.+?)\s*\|$")
HOOK_A1_PAIR_RE = re.compile(r"^([a-z][a-z0-9-]*) `([^`]+)`$")
HOOK_A4_ROW_RE = re.compile(r"^\|\s*`([a-z][a-z0-9_]*)`\s*\|\s*([a-z][a-z0-9-]*)\s*\|\s*`([^`]+)`\s*\|\s*(lossless|degraded)\b")


def check_hook_event_tables() -> None:
    """The reference adapter's HOOK_NATIVES and HOOK_RENDER_PINS must match
    [ACIF-HOOK] Appendix A.1 and A.4 row for row. The adapter keeps its own
    transcription; this parses the spec tables at the authority and diffs."""
    import importlib.util

    spec_text = (CONFORMANCE_ROOT.parent / "specs" / "hooks-interchange" / "spec.md").read_text(encoding="utf-8")
    a1 = _spec_section(spec_text, r"^### A\.1 ")
    a4 = _spec_section(spec_text, r"^### A\.4 ")
    if a1 is None or a4 is None:
        raise AssertionError("[ACIF-HOOK] A.1 or A.4 section not found")
    spec_natives: dict[str, list[tuple[str, str]]] = {}
    for line in a1.splitlines():
        match = HOOK_A1_ROW_RE.match(line.strip())
        if not match:
            continue
        pairs = []
        for raw in match.group(2).split(" · "):
            pair = HOOK_A1_PAIR_RE.match(raw.strip())
            if not pair:
                raise AssertionError(f"A.1 {match.group(1)}: unparseable mapping {raw!r}")
            pairs.append((pair.group(1), pair.group(2)))
        spec_natives[match.group(1)] = pairs
    spec_pins = {
        (m.group(1), m.group(2)): (m.group(3), m.group(4) == "degraded")
        for m in (HOOK_A4_ROW_RE.match(line.strip()) for line in a4.splitlines())
        if m
    }
    count = re.search(r"^### A\.1 .*\((\d+) events\)", a1, re.M)
    errors: list[str] = []
    if count is None or int(count.group(1)) != len(spec_natives):
        errors.append(f"A.1 heading count != {len(spec_natives)} parsed rows")
    module_spec = importlib.util.spec_from_file_location("_acif_reference_adapter", CONFORMANCE_ROOT / "adapters" / "reference.py")
    reference = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(reference)
    adapter_natives = {canonical: list(pairs) for canonical, pairs in reference.HOOK_NATIVES.items()}
    for canonical in sorted(set(spec_natives) | set(adapter_natives)):
        if spec_natives.get(canonical) != adapter_natives.get(canonical):
            errors.append(f"A.1 {canonical}: spec {spec_natives.get(canonical)} != reference {adapter_natives.get(canonical)}")
    for key in sorted(set(spec_pins) | set(reference.HOOK_RENDER_PINS)):
        if spec_pins.get(key) != reference.HOOK_RENDER_PINS.get(key):
            errors.append(f"A.4 {key}: spec {spec_pins.get(key)} != reference {reference.HOOK_RENDER_PINS.get(key)}")
    if errors:
        raise AssertionError("; ".join(errors))


INSTALL_ROW_RE = re.compile(
    r"^\|\s*`([a-z][a-z0-9-]*)`\s*\|\s*(\w+)\s*\|\s*(\w+)\s*\|\s*([a-z, ]*?)\s*\|\s*`([^`]+)`\s*\|\s*(\w+)\s*\|\s*(\w+)\s*\|\s*(.*?)\s*\|$"
)
INSTALL_SCOPES = {"user", "project", "managed"}
INSTALL_LAYOUTS = {"single_file", "directory_of_files", "merged_into_shared_file"}
INSTALL_STATUSES = {"current", "superseded"}
INSTALL_TYPES = {"rule", "hook", "skill", "command", "agent", "mcp_config"}
INSTALL_PLACEHOLDER_RE = re.compile(r"<[^>]*>")
INSTALL_OSES = ("darwin", "linux", "windows")
INSTALL_MANAGED_ABS_RE = re.compile(r"^(/|[A-Z]:/)")


def check_install_entry_points() -> None:
    """install-entry-points.yaml must match [ACIF-INSTALL] Appendix A.2 —
    row set, field values, and order (order is normative precedence),
    bidirectionally — and both must satisfy the [ACIF-INSTALL] §6–§9
    structural rules: closed enums, closed placeholder grammar, the
    (provider, content type, scope, path_template) uniqueness invariant,
    and the pinned alphabetical group ordering. Spec-prose parsing happens
    here, at the authority, so downstream copies diff against the yaml."""
    path = CONFORMANCE_ROOT / "install-entry-points.yaml"
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    matrix = document.get("install_entry_points") if isinstance(document, dict) else None
    if not isinstance(matrix, dict):
        raise AssertionError("install-entry-points.yaml missing install_entry_points mapping")
    spec_text = (CONFORMANCE_ROOT.parent / "specs" / "install-targets" / "spec.md").read_text(encoding="utf-8")
    section = _spec_section(spec_text, r"^### A\.2 ")
    if section is None:
        raise AssertionError("no A.2 section found in [ACIF-INSTALL]")
    spec_rows: list[tuple[str, str, str, str, str, str, str, str]] = []
    for line in section.splitlines():
        match = INSTALL_ROW_RE.match(line.strip())
        if match and match.group(1) != "Provider":
            spec_rows.append(match.groups())
    if not spec_rows:
        raise AssertionError("A.2 table parsed zero rows")
    yaml_rows: list[tuple[str, str, str, str, str, str, str, str]] = []
    errors: list[str] = []
    providers = list(matrix)
    if providers != sorted(providers):
        errors.append("provider groups not alphabetical")
    for provider, types in matrix.items():
        type_keys = list(types)
        if type_keys != sorted(type_keys):
            errors.append(f"{provider}: content-type groups not alphabetical")
        for ctype, entries in types.items():
            if ctype not in INSTALL_TYPES:
                errors.append(f"{provider}: unknown content type {ctype!r}")
            for entry in entries:
                os_value = entry.get("os")
                if "os" not in entry:
                    os_cell = ""
                elif (
                    not isinstance(os_value, list)
                    or not os_value
                    or any(member not in INSTALL_OSES for member in os_value)
                    or os_value != sorted(set(os_value))
                    or len(os_value) == len(INSTALL_OSES)
                ):
                    errors.append(
                        f"{provider}/{ctype}: os {os_value!r} is not a sorted, duplicate-free, "
                        "non-empty proper subset of {darwin, linux, windows}"
                    )
                    os_cell = str(os_value)
                else:
                    os_cell = ", ".join(os_value)
                yaml_rows.append(
                    (provider, ctype, str(entry.get("scope")), os_cell, str(entry.get("path_template")),
                     str(entry.get("layout")), str(entry.get("status")), str(entry.get("as_of")))
                )
    seen: set[tuple[str, str, str, str]] = set()
    for provider, ctype, scope, os_cell, template, layout, status, _as_of in yaml_rows:
        if scope not in INSTALL_SCOPES:
            errors.append(f"{provider}/{ctype}: scope {scope!r} outside the closed enum")
        if layout not in INSTALL_LAYOUTS:
            errors.append(f"{provider}/{ctype}: layout {layout!r} outside the closed enum")
        if status not in INSTALL_STATUSES:
            errors.append(f"{provider}/{ctype}: status {status!r} outside the closed enum")
        for token in INSTALL_PLACEHOLDER_RE.findall(template):
            if token == "<appdata>":
                if not template.startswith("<appdata>/") or template.count("<appdata>") != 1 or os_cell != "windows":
                    errors.append(
                        f"{provider}/{ctype}: <appdata> must be the leading segment of a row whose os is [windows]: {template!r}"
                    )
            elif token != "<content-name>":
                errors.append(f"{provider}/{ctype}: placeholder {token!r} outside the closed grammar")
        if scope == "managed" and not INSTALL_MANAGED_ABS_RE.match(template):
            errors.append(f"{provider}/{ctype}: managed template is not absolute: {template!r}")
        if layout == "merged_into_shared_file" and "<content-name>" in template:
            errors.append(f"{provider}/{ctype}: merged_into_shared_file template carries <content-name>: {template!r}")
        key = (provider, ctype, scope, template)
        if key in seen:
            errors.append(f"duplicate row {key}")
        seen.add(key)
    if spec_rows != yaml_rows:
        spec_set, yaml_set = set(spec_rows), set(yaml_rows)
        missing = spec_set - yaml_set
        extra = yaml_set - spec_set
        if missing or extra:
            errors.append(f"row drift — in spec not yaml: {sorted(missing)[:3]}; in yaml not spec: {sorted(extra)[:3]}")
        else:
            errors.append("row order drift between A.2 table and yaml (order is normative precedence)")
    if errors:
        raise AssertionError("; ".join(errors))


def _spec_section(spec_text: str, heading_re: str) -> str | None:
    lines = spec_text.splitlines()
    pattern = re.compile(heading_re)
    start = None
    for idx, line in enumerate(lines):
        if start is None:
            if pattern.match(line):
                start = idx
        elif line.startswith(("## ", "### ")):
            return "\n".join(lines[start:idx])
    return "\n".join(lines[start:]) if start is not None else None


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
    killed_by, failures, uncovered = sabotage_kills(base_rows, mutated_rows, catalog_ids)
    if failures:
        raise AssertionError("; ".join(failures))
    counts = {mutator: list(killed_by.values()).count(mutator) for mutator in SABOTAGE_MUTATORS}
    print(
        "sabotage kill summary: "
        + ", ".join(f"{mutator}={counts[mutator]}" for mutator in SABOTAGE_MUTATORS)
    )
    print("sabotage kill map: " + ", ".join(f"{vid}={killed_by[vid]}" for vid in sorted(killed_by)))
    print(f"sabotage uncovered (baseline fail, no kill possible): {len(uncovered)}: " + ", ".join(uncovered))


def sabotage_kills(
    base_rows: dict[str, dict[str, Any]],
    mutated_rows: dict[str, dict[str, dict[str, Any]]],
    ids: set[str],
) -> tuple[dict[str, str], list[str], list[str]]:
    """A mutator kills a vector only when it turns a baseline pass into a
    fail. A vector the baseline already fails proves nothing about the
    mutators, so it is reported as uncovered, never credited."""
    failures: list[str] = []
    killed_by: dict[str, str] = {}
    uncovered: list[str] = []
    for vid in sorted(ids):
        base_status = base_rows[vid]["status"]
        if base_status == "fail":
            uncovered.append(vid)
            continue
        if base_status != "pass" or base_rows[vid].get("vacuous"):
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
    return killed_by, failures, uncovered


STUB_ADAPTER = Path(__file__).resolve().parent / "stub_adapter.py"
# Vectors an all-empty adapter passed before presence was checked ahead of
# the relation (PROTOCOL §3: an asserted field absent from result is a fail).
ABSENT_RELATION_VECTORS = ("TV-MCP-k2", "TV-MCP-l", "TV-RENDER-a", "TV-URI-r", "TV-URI-s", "TV-URI-t")


def _stub(mode: str) -> str:
    return f"{shlex.quote(sys.executable)} {shlex.quote(str(STUB_ADAPTER))} --mode {mode}"


def check_absent_relations() -> None:
    catalogs = load_catalogs()
    bindings.load_all()
    passed = []
    for vid in ABSENT_RELATION_VECTORS:
        with tempfile.TemporaryDirectory(prefix="acif-selftest-fixtures-") as tmp:
            result = bindings.get(vid)(catalogs.by_id[vid], _StubSession(), _StubContext(tmp))
        if result.status == "pass":
            passed.append(vid)
    if passed:
        raise AssertionError("empty results passed: " + ", ".join(passed))


def check_render_d_structural() -> None:
    """[ACIF-RENDER] §9: the round trip must differ from the input only by
    the declared collapse; declaring the lossy token is not evidence."""
    catalogs = load_catalogs()
    bindings.load_all()
    vector = catalogs.by_id["TV-RENDER-d"]
    case_1 = [{"body_hash": "h"}, {"output": "x"}, {"body_hash": "h"}]
    lossy = ["write-edit-distinction"]
    error = {"__error__": "acif.body.empty"}

    def run(before: dict[str, Any], after: dict[str, Any], first: list[dict[str, Any]] = case_1) -> str:
        session = _ScriptedSession(first + [before, {"output": "y", "lossy": lossy}, after])
        with tempfile.TemporaryDirectory(prefix="acif-selftest-fixtures-") as tmp:
            return bindings.get("TV-RENDER-d")(vector, session, _StubContext(tmp)).status

    def agent(**block: Any) -> dict[str, Any]:
        return {"canonical": {"agent": block}}

    both = agent(tools=["file_edit", "file_write"])
    cases = [
        ("an honest write->edit collapse", both, agent(tools=["file_edit"]), case_1, "pass"),
        ("a round trip outside the lossy set", both, agent(tools=["shell"]), case_1, "fail"),
        ("a round trip with no canonical form", both, {}, case_1, "fail"),
        ("a case-2 round-trip ingest that errors", both, error, case_1, "fail"),
        ("a case-1 round-trip ingest that errors", both, agent(tools=["file_edit"]), case_1[:2] + [error], "fail"),
        # Not anchored to the rendered tools field: the collapse values sit
        # in an unrelated key.
        ("collapse values outside agent.tools", {"canonical": {"x": ["file_edit", "file_write"]}}, {"canonical": {"x": ["file_edit"]}}, case_1, "fail"),
        # The collapse must not rewrite opaque fields.
        ("an opaque agent.model rewritten by the collapse", agent(tools=["file_edit", "file_write"], model="file_write"), agent(tools=["file_edit"], model="file_edit"), case_1, "fail"),
    ]
    wrong = [f"{name}: {status} (expected {want})" for name, pre, post, first, want in cases if (status := run(pre, post, first)) != want]
    if wrong:
        raise AssertionError("; ".join(wrong))


class _ScriptedSession(_VerdictSession):
    """_VerdictSession whose script may also answer {"__error__": id}."""

    def __init__(self, results: list[dict[str, Any]]):
        super().__init__(2, results)

    def request(self, request: dict[str, Any]) -> AdapterResponse:
        if "__error__" in self._results[0]:
            raw = {"ok": False, "error": self._results.pop(0)["__error__"]}
            return classify_response(raw, encode_request(request), str(raw))
        return super().request(request)


def check_partial_line_timeout() -> None:
    """Both halves of a request fall under one deadline: a half-written
    response line, and a request the adapter stops reading (sized past
    the pipe buffer so the write itself would block)."""
    for mode, request in (
        ("partial", {"op": "ingest", "input": {}}),
        ("no-read", {"op": "ingest", "input": {"pad": "x" * (4 * 1024 * 1024)}}),
    ):
        session = AdapterSession(_stub(mode), timeout=0.5)
        try:
            session.start()
            started = time.monotonic()
            response = session.request(request)
            elapsed = time.monotonic() - started
        finally:
            session.close()
        if response.kind != "harness-error" or "timed out" not in (response.harness_error or ""):
            raise AssertionError(f"{mode}: must time out as harness-error, got {response.kind}: {response.harness_error}")
        if elapsed > 5:
            raise AssertionError(f"{mode}: held the request for {elapsed:.1f}s past a 0.5s timeout")


def check_handshake_strictness() -> None:
    for mode in ("bool-protocol", "float-protocol", "unknown-scope"):
        session = AdapterSession(_stub(mode), timeout=10)
        try:
            session.start()
        except ProtocolError:
            pass
        else:
            raise AssertionError(f"handshake accepted a {mode} hello")
        finally:
            session.close()
    ambiguous = [
        {"ok": True, "result": {}, "error": "acif.core.invalid"},
        {"ok": False, "error": "acif.core.invalid", "result": {}},
    ]
    for raw in ambiguous:
        if classify_response(raw, "{}", None).kind != "harness-error":
            raise AssertionError(f"ambiguous response classified as non-error: {raw}")


def check_exit_status() -> None:
    from ..__main__ import exit_status

    def report(statuses: list[str], hello_error: str | None = None) -> dict[str, Any]:
        adapter: dict[str, Any] = {"hello_error": hello_error} if hello_error else {}
        return {"adapter": adapter, "vectors": [{"status": s} for s in statuses]}

    cases = [
        (report(["pass", "out-of-scope", "unsupported"]), 0),
        (report(["pass", "fail"]), 1),
        (report(["pass", "harness-error"]), 1),
        (report(["out-of-scope"], hello_error="adapter hello failed"), 1),
    ]
    for rep, expected in cases:
        if exit_status(rep) != expected:
            raise AssertionError(f"exit_status({rep}) != {expected}")


def check_differential_clean() -> None:
    from ..differential import FAMILY_SCOPES, required_families, run_differential

    core = {f for f, s in FAMILY_SCOPES.items() if s == "core"}
    if required_families(["core", "hook"], ["core"]) != core:
        raise AssertionError("hook families must not be required unless both adapters claim hook")
    if "normalize_uri" not in required_families(["registry"], ["core", "registry"]):
        raise AssertionError("normalize_uri must be required when both adapters claim registry")
    for count in (0, 20):
        diff = run_differential(adapter_a=_stub("empty"), adapter_b=_stub("empty"), seed=0, count=count)["differential"]
        if diff["clean"]:
            raise AssertionError(f"two empty adapters over {count} trials must not be clean")
    # Two adapters omitting the same hash fields agree on nothing.
    diff = run_differential(adapter_a=_stub("partial-fields"), adapter_b=_stub("partial-fields"), seed=0, count=60)["differential"]
    if diff["clean"] or not diff["summary"]["incomplete"]:
        raise AssertionError("adapters omitting the same answer fields must be incomplete, not clean")
    agreeing = sorted(f for f, s in diff["families"].items() if s.get("agree") and f != "envelope")
    if agreeing:
        raise AssertionError("families agreed without their answer fields: " + ", ".join(agreeing))


def check_sabotage_baseline() -> None:
    ids = {"TV-A", "TV-B"}
    base = {"TV-A": {"status": "fail"}, "TV-B": {"status": "pass"}}
    mutated = {m: {"TV-A": {"status": "fail"}, "TV-B": {"status": "fail"}} for m in SABOTAGE_MUTATORS}
    killed_by, failures, uncovered = sabotage_kills(base, mutated, ids)
    if "TV-A" in killed_by or uncovered != ["TV-A"] or set(killed_by) != {"TV-B"} or failures:
        raise AssertionError(f"baseline-fail vector credited: killed={killed_by} uncovered={uncovered}")
