from __future__ import annotations

from typing import Any

from ..protocol import AdapterResponse
from ..report import VectorResult
from ..vectors import Vector

ABSENT = "<absent>"


def result_for(vector: Vector) -> VectorResult:
    return VectorResult(id=vector.id, catalog=vector.catalog)


def send(
    result: VectorResult,
    session: Any,
    ctx: Any,
    request: dict[str, Any],
    *,
    tags: dict[str, Any] | None = None,
) -> AdapterResponse:
    response = session.request(request)
    result.add_request(response.request_line)
    response._acif_vector_id = result.id  # type: ignore[attr-defined]
    if tags:
        for key, value in tags.items():
            setattr(response, f"_acif_{key}", value)
    ctx.observations.append(response)
    if response.kind == "harness-error":
        result.set_status("harness-error", response.harness_error or "adapter harness error")
    elif response.kind == "unsupported":
        result.set_status("unsupported", "adapter returned unsupported")
    return response


def ingest(
    kind: str,
    *,
    body_root: str | None = None,
    entry_file: str | None = None,
    sidecar: Any = ABSENT,
    provider_config: dict[str, Any] | None = None,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    request_input: dict[str, Any] = {"kind": kind}
    if body_root is not None:
        request_input["body_root"] = body_root
    if entry_file is not None:
        request_input["entry_file"] = entry_file
    if sidecar is not ABSENT:
        request_input["sidecar"] = sidecar
    if provider_config is not None:
        request_input["provider_config"] = provider_config
    if context is not None:
        request_input["context"] = context
    return {"op": "ingest", "input": request_input}


def provider_config(provider: str, path: str, content: Any) -> dict[str, Any]:
    return {"provider": provider, "path": path, "content": content}


def derive_pack_id(namespace: str, repository_url: str, display_name: str) -> dict[str, Any]:
    return {
        "op": "derive_pack_id",
        "input": {
            "namespace": namespace,
            "repository_url": repository_url,
            "display_name": display_name,
        },
    }


def resolve_pack(item: dict[str, Any], known_packs: list[Any] | None = None) -> dict[str, Any]:
    return {
        "op": "resolve_pack",
        "input": {
            "item": item,
            "known_packs": [] if known_packs is None else known_packs,
        },
    }


def evaluate_requires(item_requires: dict[str, Any], consumer_recognizes: list[str]) -> dict[str, Any]:
    return {
        "op": "evaluate_requires",
        "input": {
            "item_requires": item_requires,
            "consumer_recognizes": consumer_recognizes,
        },
    }


def project(item: Any, projection: str, **extra: Any) -> dict[str, Any]:
    request_input = {
        "item": item,
        "projection": projection,
    }
    request_input.update(extra)
    return {
        "op": "project",
        "input": request_input,
    }


def project_derived_capabilities(item: Any) -> dict[str, Any]:
    return project(item, "derived_capabilities")


def project_script_selection(item: Any, targets: list[str]) -> dict[str, Any]:
    return project(item, "script_selection", targets=targets)


def render(canonical: Any, target: str, invocation: dict[str, Any] | None = None) -> dict[str, Any]:
    request_input: dict[str, Any] = {"canonical": canonical, "target": target}
    if invocation is not None:
        request_input["invocation"] = invocation
    return {"op": "render", "input": request_input}


def resolve_reference(item: Any, registry_state: dict[str, Any]) -> dict[str, Any]:
    return {
        "op": "resolve_reference",
        "input": {
            "item": item,
            "registry_state": registry_state,
        },
    }


def evaluate_install(item: Any, install_target_os: str | None = None) -> dict[str, Any]:
    request_input: dict[str, Any] = {"item": item}
    if install_target_os is not None:
        request_input["install_target_os"] = install_target_os
    return {"op": "evaluate_install", "input": request_input}


def reconcile_frontmatter(sidecar_value: Any, source_frontmatter: Any, mode: str) -> dict[str, Any]:
    return {
        "op": "reconcile_frontmatter",
        "input": {
            "sidecar_value": sidecar_value,
            "source_frontmatter": source_frontmatter,
            "mode": mode,
        },
    }


def normalize_uri(uri: str) -> dict[str, Any]:
    return {"op": "normalize_uri", "input": {"uri": uri}}


def fetch_uri(url: str, trust_ca: str, resolve: dict[str, str]) -> dict[str, Any]:
    return {"op": "fetch_uri", "input": {"url": url, "trust_ca": trust_ca, "resolve": resolve}}


def derive_url_name(uri: str, body_classification: str, frontmatter_name: str | None = None) -> dict[str, Any]:
    request_input: dict[str, Any] = {
        "uri": uri,
        "body_classification": body_classification,
    }
    if frontmatter_name is not None:
        request_input["frontmatter_name"] = frontmatter_name
    return {"op": "derive_url_name", "input": request_input}


def evaluate_freshness(
    record: dict[str, Any],
    *,
    consumer_clock: str | None = None,
    policies: list[str] | None = None,
    attestation_evaluation: str | None = None,
    declared_tolerance_seconds: int | None = None,
    attestation_system: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    request_input: dict[str, Any] = {"record": record}
    if consumer_clock is not None:
        request_input["consumer_clock"] = consumer_clock
    if policies is not None:
        request_input["policies"] = policies
    if attestation_evaluation is not None:
        request_input["attestation_evaluation"] = attestation_evaluation
    if declared_tolerance_seconds is not None:
        request_input["declared_tolerance_seconds"] = declared_tolerance_seconds
    if attestation_system is not None:
        request_input["attestation_system"] = attestation_system
    if extra:
        request_input.update(extra)
    return {"op": "evaluate_freshness", "input": request_input}


def field(value: Any, path: str) -> Any:
    current = value
    for part in path.split("."):
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return ABSENT
    return current


def result_field(response: AdapterResponse, path: str) -> Any:
    return field(response.result or {}, path)


def canonical_field(response: AdapterResponse, path: str) -> Any:
    return result_field(response, "canonical" + (("." + path) if path else ""))


def projection_field(response: AdapterResponse, path: str) -> Any:
    projection = result_field(response, "projection")
    if path == "":
        return projection
    return field(projection, path)


def assert_result_field(
    result: VectorResult,
    case: str,
    response: AdapterResponse,
    path: str,
    expected: Any,
) -> None:
    if _blocked_for_result_assertion(result, case, response, path, expected):
        return
    observed = result_field(response, path)
    result.add_check(case, path, expected, observed, observed == expected)


def assert_projection(
    result: VectorResult,
    case: str,
    response: AdapterResponse,
    expected: Any,
) -> None:
    if _blocked_for_result_assertion(result, case, response, "projection", expected):
        return
    observed = result_field(response, "projection")
    result.add_check(case, "projection", expected, observed, observed == expected)


def assert_projection_field(
    result: VectorResult,
    case: str,
    response: AdapterResponse,
    path: str,
    expected: Any,
) -> None:
    if _blocked_for_result_assertion(result, case, response, f"projection.{path}", expected):
        return
    observed = projection_field(response, path)
    result.add_check(case, f"projection.{path}", expected, observed, observed == expected)


def assert_value(
    result: VectorResult,
    case: str,
    field_name: str,
    expected: Any,
    observed: Any,
    response: AdapterResponse | None = None,
) -> None:
    if response is not None and _blocked_for_result_assertion(result, case, response, field_name, expected):
        return
    result.add_check(case, field_name, expected, observed, observed == expected)


def assert_relation(
    result: VectorResult,
    case: str,
    field_name: str,
    expected: Any,
    values: Any,
    relation: bool,
) -> None:
    result.add_check(case, field_name, expected, values, relation == bool(expected))


def assert_ok(
    result: VectorResult,
    case: str,
    response: AdapterResponse,
    field_name: str,
    expected: bool,
) -> None:
    if response.kind == "unsupported":
        result.set_status("unsupported", f"{case}: adapter returned unsupported")
        return
    if response.kind == "harness-error":
        return
    observed = response.kind == "ok"
    result.add_check(case, field_name, expected, observed, observed == expected)


def assert_error(result: VectorResult, case: str, response: AdapterResponse, expected: str) -> None:
    if response.kind == "unsupported":
        result.set_status("unsupported", f"{case}: adapter returned unsupported")
        return
    if response.kind == "harness-error":
        return
    if response.kind == "spec-error":
        result.add_check(case, "error", expected, response.error, response.error == expected)
        return
    result.add_check(case, "error", expected, response.result or {}, False)


def assert_present_absent(
    result: VectorResult,
    case: str,
    response: AdapterResponse,
    path: str,
    expected: str,
) -> None:
    if _blocked_for_result_assertion(result, case, response, path, expected):
        return
    value = result_field(response, path)
    observed = "absent" if value is ABSENT else "present"
    result.add_check(case, path, expected, observed, observed == expected)


def assert_absent(
    result: VectorResult,
    case: str,
    response: AdapterResponse,
    path: str,
    expected: Any,
) -> None:
    if _blocked_for_result_assertion(result, case, response, path, expected):
        return
    observed = result_field(response, path)
    result.add_check(case, path, expected, observed, observed is ABSENT)


def assert_output_equals(
    result: VectorResult,
    case: str,
    response: AdapterResponse,
    expected: str,
) -> None:
    assert_result_field(result, case, response, "output", expected)


def assert_output_contains(
    result: VectorResult,
    case: str,
    response: AdapterResponse,
    field_name: str,
    expected: Any,
) -> None:
    if _blocked_for_result_assertion(result, case, response, field_name, expected):
        return
    output = result_field(response, "output")
    if isinstance(expected, list):
        observed = [item for item in expected if isinstance(output, str) and str(item) in output]
        passed = len(observed) == len(expected)
    else:
        observed = isinstance(output, str) and str(expected) in output
        passed = bool(observed)
    result.add_check(case, field_name, expected, observed, passed)


def assert_output_excludes(
    result: VectorResult,
    case: str,
    response: AdapterResponse,
    field_name: str,
    expected: list[Any],
) -> None:
    if _blocked_for_result_assertion(result, case, response, field_name, expected):
        return
    output = result_field(response, "output")
    observed = [item for item in expected if not (isinstance(output, str) and str(item) in output)]
    result.add_check(case, field_name, expected, observed, observed == expected)


def adapter_protocol(session: Any) -> int:
    hello = getattr(session, "hello", None)
    value = hello.get("adapter_protocol") if isinstance(hello, dict) else None
    return value if isinstance(value, int) else 1


def assert_verdict_reason(
    result: VectorResult,
    case: str,
    response: AdapterResponse,
    expected_reason: str,
    session: Any,
    params: dict[str, Any] | None = None,
) -> None:
    """Assert the minted verdict-reason identifier (PROTOCOL §3), gated on
    the adapter's DECLARED handshake protocol: adapters declaring
    adapter_protocol 1 stay unasserted forever — never retroactive. Under
    protocol 1 the expected literals are still collected so the
    anti-softening self-check accounts for them."""
    if adapter_protocol(session) < 2:
        result.add_check_equivalent(expected_reason)
        for value in (params or {}).values():
            result.add_check_equivalent(value)
        return
    assert_result_field(result, case, response, "reason", expected_reason)
    for key, value in (params or {}).items():
        assert_result_field(result, case, response, f"params.{key}", value)


def assert_diagnostic(
    result: VectorResult,
    case: str,
    response: AdapterResponse,
    expected_id: str,
    expected_params: dict[str, Any] | None = None,
) -> None:
    if response.kind == "unsupported":
        result.set_status("unsupported", f"{case}: adapter returned unsupported")
        return
    if response.kind == "harness-error":
        return
    diagnostics = diagnostics_for(response)
    matches = [
        diagnostic
        for diagnostic in diagnostics
        if isinstance(diagnostic, dict) and diagnostic.get("id") == expected_id
    ]
    observed = diagnostics
    passed = bool(matches)
    if expected_params is not None and matches:
        params = matches[0].get("params", {})
        passed = isinstance(params, dict) and all(params.get(k) == v for k, v in expected_params.items())
        observed = params
    if passed:
        family = diagnostic_family(expected_id)
        unexpected = [
            diagnostic.get("id")
            for diagnostic in diagnostics
            if isinstance(diagnostic.get("id"), str)
            and diagnostic.get("id", "").startswith(family + ".")
            and diagnostic.get("id") != expected_id
        ]
        if unexpected:
            passed = False
            observed = {"diagnostics": diagnostics, "unexpected_same_family": unexpected}
    result.add_check(case, "diagnostic", expected_id if expected_params is None else {"id": expected_id, "params": expected_params}, observed, passed)


def diagnostics_for(response: AdapterResponse) -> list[dict[str, Any]]:
    if response.kind == "ok":
        diagnostics = (response.result or {}).get("diagnostics", [])
    elif response.kind == "spec-error":
        diagnostics = response.diagnostics or []
    else:
        diagnostics = []
    if isinstance(diagnostics, list):
        return [d for d in diagnostics if isinstance(d, dict)]
    return []


def diagnostic_family(diagnostic_id: str) -> str:
    parts = diagnostic_id.split(".")
    return ".".join(parts[:2]) if len(parts) >= 2 else diagnostic_id


def assert_derived_capability(
    result: VectorResult,
    case: str,
    response: AdapterResponse,
    key: str,
    expected_label: str,
) -> None:
    expected = derivable_label_to_bool(result, expected_label)
    if _blocked_for_result_assertion(result, case, response, f"derived_capabilities.{key}", expected):
        return
    derived = result_field(response, "derived_capabilities")
    observed = derived.get(key, ABSENT) if isinstance(derived, dict) else ABSENT
    result.add_check(case, f"derived_capabilities.{key}", expected, observed, observed is expected)


def derivable_label_to_bool(result: VectorResult, label: str) -> bool:
    result.add_check_equivalent(label)
    if label == "derivable-true":
        return True
    if label == "derivable-false":
        return False
    raise ValueError(f"unknown derivable label {label!r}")


def hash_value(response: AdapterResponse, name: str) -> Any:
    return result_field(response, name)


def output_value(response: AdapterResponse) -> Any:
    return result_field(response, "output")


def _blocked_for_result_assertion(
    result: VectorResult,
    case: str,
    response: AdapterResponse,
    field_name: str,
    expected: Any,
) -> bool:
    if response.kind == "unsupported":
        result.set_status("unsupported", f"{case}: adapter returned unsupported")
        return True
    if response.kind == "harness-error":
        return True
    if response.kind == "spec-error":
        result.add_check(case, field_name, expected, {"error": response.error}, False)
        return True
    return False
