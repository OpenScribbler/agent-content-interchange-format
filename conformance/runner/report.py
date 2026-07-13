from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import RUNNER_PROTOCOL, RUNNER_VERSION

STATUSES = {"pass", "fail", "unsupported", "out-of-scope", "env-blocked", "harness-error"}
STATUS_PRIORITY = {
    "pass": 0,
    "out-of-scope": 0,
    "unsupported": 1,
    "env-blocked": 2,
    "fail": 3,
    "harness-error": 4,
}


@dataclass
class VectorResult:
    id: str
    catalog: str
    status: str = "pass"
    message: str = ""
    vacuous: bool = False
    checks: list[dict[str, Any]] = field(default_factory=list)
    request_lines: list[str] = field(default_factory=list)
    fixture_paths: list[str] = field(default_factory=list)
    expected_literals: set[Any] = field(default_factory=set)

    def set_status(self, status: str, message: str | None = None) -> None:
        if status not in STATUSES:
            raise ValueError(f"unknown vector status {status}")
        if STATUS_PRIORITY[status] >= STATUS_PRIORITY.get(self.status, 0):
            self.status = status
            if message:
                self.message = message

    def add_request(self, request_line: str) -> None:
        self.request_lines.append(request_line)

    def add_check(self, case: str, field: str, expected: Any, observed: Any, passed: bool) -> None:
        self.checks.append(
            {
                "case": case,
                "field": field,
                "expected": expected,
                "observed": observed,
                "pass": bool(passed),
            }
        )
        if not passed:
            self.set_status("fail", f"{case}: {field} mismatch")

    def add_check_equivalent(self, expected: Any) -> None:
        self.expected_literals.add(expected)

    def to_json(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "catalog": self.catalog,
            "status": self.status,
            "vacuous": self.vacuous,
            "message": self.message,
            "expected_vs_observed": self.checks,
            "request_lines": self.request_lines,
            "fixture_paths": self.fixture_paths,
        }


def make_out_of_scope(vector_id: str, catalog: str, message: str = "") -> VectorResult:
    return VectorResult(id=vector_id, catalog=catalog, status="out-of-scope", message=message)


def build_report(
    *,
    adapter_invocation: str,
    hello_result: dict[str, Any] | None,
    hello_error: str | None,
    adapter_protocol: int | None,
    catalog_hashes: dict[str, str],
    binding_set_hash: str,
    env_probes: dict[str, Any],
    requested_scopes: list[str],
    claimed_scopes: list[str],
    selected_scopes: list[str],
    scope_status: dict[str, Any],
    vector_results: list[VectorResult],
) -> dict[str, Any]:
    report = {
        "runner": {
            "version": RUNNER_VERSION,
            "runner_protocol": RUNNER_PROTOCOL,
        },
        "adapter": {
            "invocation": adapter_invocation,
            "hello": hello_result,
            "hello_error": hello_error,
            "adapter_protocol": adapter_protocol,
            "claimed_scopes": claimed_scopes,
        },
        "catalog_hashes": catalog_hashes,
        "binding_set_hash": binding_set_hash,
        "env_probes": env_probes,
        "scopes": {
            "requested": requested_scopes,
            "selected": selected_scopes,
            "summary": scope_status,
        },
        "vectors": [r.to_json() for r in vector_results],
    }
    validate_report(report)
    return report


def validate_report(report: dict[str, Any]) -> None:
    required = {
        "runner",
        "adapter",
        "catalog_hashes",
        "binding_set_hash",
        "env_probes",
        "scopes",
        "vectors",
    }
    missing = required - set(report)
    if missing:
        raise ValueError(f"report missing keys: {sorted(missing)}")
    if not isinstance(report["vectors"], list):
        raise ValueError("report vectors must be a list")
    for row in report["vectors"]:
        if row.get("status") not in STATUSES:
            raise ValueError(f"invalid vector status: {row.get('status')!r}")
        if not isinstance(row.get("request_lines"), list):
            raise ValueError(f"{row.get('id')} request_lines must be a list")
        if not isinstance(row.get("expected_vs_observed"), list):
            raise ValueError(f"{row.get('id')} expected_vs_observed must be a list")


def write_report(path: str | Path, report: dict[str, Any]) -> None:
    Path(path).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def human_report(report: dict[str, Any]) -> str:
    lines: list[str] = []
    scope_summary = report["scopes"]["summary"]
    not_passed = [
        f"{scope}: {info['status']}"
        for scope, info in sorted(scope_summary.items())
        if info.get("status") != "pass"
    ]
    lines.append("Scopes not passed / not claimed:")
    if not_passed:
        lines.extend(f"  {item}" for item in not_passed)
    else:
        lines.append("  none")

    catalog_counts: dict[str, dict[str, int]] = {}
    for row in report["vectors"]:
        counts = catalog_counts.setdefault(row["catalog"], {s: 0 for s in sorted(STATUSES)})
        counts[row["status"]] += 1
    lines.append("")
    lines.append("Per-catalog summary:")
    for catalog in sorted(catalog_counts):
        counts = catalog_counts[catalog]
        parts = [f"{status}={count}" for status, count in sorted(counts.items()) if count]
        vacuous = sum(1 for row in report["vectors"] if row["catalog"] == catalog and row.get("vacuous"))
        if vacuous:
            parts.append(f"vacuous={vacuous}")
        lines.append(f"  {catalog}: " + ", ".join(parts))

    problem_rows = [
        row for row in report["vectors"]
        if row["status"] in {"fail", "harness-error", "env-blocked", "unsupported"}
    ]
    if problem_rows:
        lines.append("")
        lines.append("Failures and blockers:")
        for row in problem_rows:
            suffix = f" - {row['message']}" if row.get("message") else ""
            lines.append(f"  {row['id']} [{row['status']}]{suffix}")
            if row["status"] in {"fail", "harness-error"}:
                for request_line in row.get("request_lines", []):
                    lines.append(f"    request: {request_line}")
            for fixture_path in row.get("fixture_paths", []):
                lines.append(f"    fixture: {fixture_path}")
    return "\n".join(lines)
