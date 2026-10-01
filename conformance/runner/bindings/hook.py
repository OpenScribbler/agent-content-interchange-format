from __future__ import annotations

import copy
from typing import Any

from . import binding
from .common import (
    assert_diagnostic,
    assert_output_contains,
    assert_output_excludes,
    assert_relation,
    assert_verdict_reason,
    diagnostics_for,
    render,
    send,
)
from ..protocol import AdapterResponse
from ..report import VectorResult
from ..vectors import Vector

ABSENT = "<absent>"

# The provider tags are the protocol-side labels for the provider-native
# event spellings annotated in hook.yaml comments.
PROVIDER_BY_EVENT = {
    "PreToolUse": "claude-code",
    "BeforeTool": "gemini-cli",
    "tool.execute.before": "opencode",
    "onToolStart": "unknown-provider",
}


def _result(vector: Vector) -> VectorResult:
    return VectorResult(id=vector.id, catalog=vector.catalog)


def _send(result: VectorResult, session: Any, ctx: Any, request: dict[str, Any]) -> AdapterResponse:
    response = session.request(request)
    result.add_request(response.request_line)
    ctx.observations.append(response)
    if response.kind == "harness-error":
        result.set_status("harness-error", response.harness_error or "adapter harness error")
    return response


def _sidecar_ingest(hook: dict[str, Any], body_root: str | None = None) -> dict[str, Any]:
    request_input: dict[str, Any] = {"kind": "hook", "sidecar": hook}
    if body_root is not None:
        request_input["body_root"] = body_root
    return {"op": "ingest", "input": request_input}


def _provider_ingest(provider: str, hook: dict[str, Any]) -> dict[str, Any]:
    return {
        "op": "ingest",
        "input": {
            "kind": "hook",
            "provider_config": {
                "provider": provider,
                "path": "hooks.json",
                "content": hook,
            },
        },
    }


def _evaluate_requires(item_requires: dict[str, Any], consumer_recognizes: list[str]) -> dict[str, Any]:
    return {
        "op": "evaluate_requires",
        "input": {
            "item_requires": item_requires,
            "consumer_recognizes": consumer_recognizes,
        },
    }


def _project_derived_capabilities(item: dict[str, Any] | Any) -> dict[str, Any]:
    return {
        "op": "project",
        "input": {
            "item": item,
            "projection": "derived_capabilities",
        },
    }


def _assert_result_field(result: VectorResult, case: str, response: AdapterResponse, field: str, expected: Any) -> None:
    if response.kind == "unsupported":
        result.set_status("unsupported", f"{case}: adapter returned unsupported")
        return
    if response.kind == "harness-error":
        return
    if response.kind == "spec-error":
        result.add_check(case, field, expected, {"error": response.error}, False)
        return
    observed = (response.result or {}).get(field, ABSENT)
    result.add_check(case, field, expected, observed, observed == expected)


def _assert_value(result: VectorResult, case: str, field: str, expected: Any, observed: Any, response: AdapterResponse) -> None:
    if response.kind == "unsupported":
        result.set_status("unsupported", f"{case}: adapter returned unsupported")
        return
    if response.kind == "harness-error":
        return
    if response.kind == "spec-error":
        result.add_check(case, field, expected, {"error": response.error}, False)
        return
    result.add_check(case, field, expected, observed, observed == expected)


def _assert_error(result: VectorResult, case: str, response: AdapterResponse, expected: str) -> None:
    if response.kind == "unsupported":
        result.set_status("unsupported", f"{case}: adapter returned unsupported")
        return
    if response.kind == "harness-error":
        return
    if response.kind == "spec-error":
        result.add_check(case, "error", expected, response.error, response.error == expected)
        return
    result.add_check(case, "error", expected, response.result or {}, False)


def _assert_derived_capability(
    result: VectorResult,
    case: str,
    response: AdapterResponse,
    key: str,
    expected_label: str,
) -> None:
    expected = _derivable_label_to_bool(result, expected_label)
    if response.kind == "unsupported":
        result.set_status("unsupported", f"{case}: adapter returned unsupported")
        return
    if response.kind == "harness-error":
        return
    if response.kind == "spec-error":
        result.add_check(case, f"derived_capabilities.{key}", expected, {"error": response.error}, False)
        return
    derived = (response.result or {}).get("derived_capabilities")
    observed = derived.get(key, ABSENT) if isinstance(derived, dict) else ABSENT
    result.add_check(case, f"derived_capabilities.{key}", expected, observed, observed is expected)


def _derivable_label_to_bool(result: VectorResult, label: str) -> bool:
    result.add_check_equivalent(label)
    if label == "derivable-true":
        return True
    if label == "derivable-false":
        return False
    raise ValueError(f"unknown derivable label {label!r}")


def _canonical_event(response: AdapterResponse) -> Any:
    canonical = (response.result or {}).get("canonical")
    if isinstance(canonical, dict):
        return canonical.get("event", ABSENT)
    return ABSENT


def _canonical_matcher(response: AdapterResponse) -> Any:
    canonical = (response.result or {}).get("canonical")
    if isinstance(canonical, dict):
        return canonical.get("matcher", ABSENT)
    return ABSENT


def _canonical_handler_type(response: AdapterResponse) -> Any:
    canonical = (response.result or {}).get("canonical")
    if not isinstance(canonical, dict):
        return ABSENT
    handlers = canonical.get("handlers")
    if not isinstance(handlers, list) or not handlers:
        return ABSENT
    first = handlers[0]
    if not isinstance(first, dict):
        return ABSENT
    return first.get("type", ABSENT)


def _body_hash(response: AdapterResponse) -> Any:
    return (response.result or {}).get("body_hash", ABSENT)


def _all_ok(responses: list[AdapterResponse]) -> bool:
    return all(response.kind == "ok" for response in responses)


@binding("TV-HOOK-a")
def tv_hook_a(vector: Vector, session: Any, ctx: Any) -> VectorResult:
    result = _result(vector)
    expected = vector.data["expect"]["conformant"]
    for idx, variant in enumerate(vector.data["input"]["variants"]):
        response = _send(result, session, ctx, _sidecar_ingest(variant["hook"]))
        _assert_result_field(result, f"variants[{idx}]", response, "conformant", expected)
    return result


@binding("TV-HOOK-b")
def tv_hook_b(vector: Vector, session: Any, ctx: Any) -> VectorResult:
    result = _result(vector)
    exp = vector.data["expect"]
    response = _send(result, session, ctx, _sidecar_ingest(vector.data["input"]["hook"]))
    _assert_result_field(result, "hook", response, "conformant", exp["conformant"])
    assert_verdict_reason(result, "hook", response, exp["reason"], session, exp.get("params"))
    return result


@binding("TV-HOOK-c")
def tv_hook_c(vector: Vector, session: Any, ctx: Any) -> VectorResult:
    result = _result(vector)
    inp = vector.data["input"]
    exp = vector.data["expect"]
    response = _send(result, session, ctx, _evaluate_requires(inp["item_requires"], inp["consumer_recognizes"]))
    _assert_result_field(result, "requires", response, "evaluation", exp["evaluation"])
    _assert_result_field(result, "requires", response, "install", exp["install"])
    return result


@binding("TV-HOOK-d")
def tv_hook_d(vector: Vector, session: Any, ctx: Any) -> VectorResult:
    result = _result(vector)
    inp = vector.data["input"]
    exp = vector.data["expect"]
    ingest_response = _send(result, session, ctx, _sidecar_ingest(inp["conforming"]["hook"]))
    if ingest_response.kind == "ok":
        canonical = (ingest_response.result or {}).get("canonical", ABSENT)
        project_response = _send(result, session, ctx, _project_derived_capabilities(canonical))
        # DERIVATION: [ACIF-HOOK] §10.1, §6.2 (from vector spec) defines
        # handler_types as constant derivable-true on conforming records.
        _assert_derived_capability(result, "conforming", project_response, "handler_types", exp["conforming"]["handler_types"])
    elif ingest_response.kind == "unsupported":
        result.set_status("unsupported", "conforming ingest: adapter returned unsupported")
    elif ingest_response.kind == "spec-error":
        result.add_check("conforming", "ingest", "ok", {"error": ingest_response.error}, False)
    response = _send(result, session, ctx, _sidecar_ingest(inp["empty_handlers"]["hook"]))
    _assert_error(result, "empty_handlers", response, exp["empty_handlers"]["error"])
    return result


@binding("TV-HOOK-e")
def tv_hook_e(vector: Vector, session: Any, ctx: Any) -> VectorResult:
    result = _result(vector)
    inp = vector.data["input"]
    exp = vector.data["expect"]
    # DERIVATION: [ACIF-HOOK] §10.1 (from vector spec) defines
    # matcher_patterns from the canonical matcher field.
    response = _send(result, session, ctx, _project_derived_capabilities(inp["with_matcher"]["hook"]))
    _assert_derived_capability(result, "with_matcher", response, "matcher_patterns", exp["with_matcher"]["matcher_patterns"])
    response = _send(result, session, ctx, _project_derived_capabilities(inp["without_matcher"]["hook"]))
    _assert_derived_capability(result, "without_matcher", response, "matcher_patterns", exp["without_matcher"]["matcher_patterns"])
    return result


@binding("TV-HOOK-f")
def tv_hook_f(vector: Vector, session: Any, ctx: Any) -> VectorResult:
    result = _result(vector)
    inp = vector.data["input"]
    exp = vector.data["expect"]
    # DERIVATION: [ACIF-HOOK] §10.1 (from vector spec) defines
    # async_execution from the canonical handler async flags.
    response = _send(result, session, ctx, _project_derived_capabilities(inp["async_true"]["hook"]))
    _assert_derived_capability(result, "async_true", response, "async_execution", exp["async_true"]["async_execution"])
    response = _send(result, session, ctx, _project_derived_capabilities(inp["async_absent"]["hook"]))
    _assert_derived_capability(result, "async_absent", response, "async_execution", exp["async_absent"]["async_execution"])
    return result


@binding("TV-HOOK-g")
def tv_hook_g(vector: Vector, session: Any, ctx: Any) -> VectorResult:
    result = _result(vector)
    inp = vector.data["input"]
    exp = vector.data["expect"]
    responses: list[AdapterResponse] = []
    expected_event = exp["all_variants_canonicalize_to"]
    expected_hash = exp["body_hash"]

    for idx, variant in enumerate(inp["provider_native_variants"]):
        hook = {"event": variant["event"], "handlers": inp["common_handlers"]}
        response = _send(result, session, ctx, _provider_ingest(PROVIDER_BY_EVENT[variant["event"]], hook))
        responses.append(response)
        _assert_value(result, f"provider_native_variants[{idx}]", "all_variants_canonicalize_to", expected_event, _canonical_event(response), response)
        _assert_result_field(result, f"provider_native_variants[{idx}]", response, "body_hash", expected_hash)

    canonical_hook = {"event": inp["canonical"]["event"], "handlers": inp["common_handlers"]}
    response = _send(result, session, ctx, _sidecar_ingest(canonical_hook))
    responses.append(response)
    _assert_value(result, "canonical", "all_variants_canonicalize_to", expected_event, _canonical_event(response), response)
    _assert_result_field(result, "canonical", response, "body_hash", expected_hash)

    if _all_ok(responses):
        observed_hashes = [_body_hash(response) for response in responses]
        assert_relation(
            result,
            "recognized_variants",
            "body_hash_identical_across_variants",
            exp["body_hash_identical_across_variants"],
            observed_hashes,
            len(set(observed_hashes)) == 1,
        )

    unrecognized_hook = {"event": inp["unrecognized"]["event"], "handlers": inp["common_handlers"]}
    response = _send(result, session, ctx, _provider_ingest(PROVIDER_BY_EVENT["onToolStart"], unrecognized_hook))
    _assert_error(result, "unrecognized", response, exp["unrecognized"]["error"])
    return result


@binding("TV-HOOK-h")
def tv_hook_h(vector: Vector, session: Any, ctx: Any) -> VectorResult:
    result = _result(vector)
    inp = vector.data["input"]
    exp = vector.data["expect"]

    absent_response = _send(result, session, ctx, _sidecar_ingest(inp["absent_type"]["hook"]))
    _assert_value(
        result,
        "absent_type",
        "canonical_handler_type",
        exp["absent_type"]["canonical_handler_type"],
        _canonical_handler_type(absent_response),
        absent_response,
    )

    # DERIVATION: [ACIF-HOOK] §8.2 says an absent handler type materializes
    # to command, so the explicit command variant is constructed for the
    # committed equality assertion.
    explicit_hook = copy.deepcopy(inp["absent_type"]["hook"])
    explicit_hook["handlers"][0]["type"] = "command"
    explicit_response = _send(result, session, ctx, _sidecar_ingest(explicit_hook))
    if absent_response.kind == "ok" and explicit_response.kind == "ok":
        assert_relation(
            result,
            "absent_type",
            "body_hash_equals_explicit_command_variant",
            exp["absent_type"]["body_hash_equals_explicit_command_variant"],
            [_body_hash(absent_response), _body_hash(explicit_response)],
            _body_hash(absent_response) == _body_hash(explicit_response),
        )
    elif explicit_response.kind == "unsupported":
        result.set_status("unsupported", "explicit command variant: adapter returned unsupported")
    elif explicit_response.kind == "harness-error":
        result.set_status("harness-error", explicit_response.harness_error or "adapter harness error")

    response = _send(result, session, ctx, _sidecar_ingest(inp["unrecognized_type"]["hook"]))
    _assert_error(result, "unrecognized_type", response, exp["unrecognized_type"]["error"])
    return result


@binding("TV-HOOK-i")
def tv_hook_i(vector: Vector, session: Any, ctx: Any) -> VectorResult:
    result = _result(vector)
    body_root = ctx.materialize({})
    response = _send(result, session, ctx, _sidecar_ingest(vector.data["input"]["hook"], body_root=body_root))
    _assert_error(result, "hook", response, vector.data["expect"]["error"])
    return result


@binding("TV-HOOK-j")
def tv_hook_j(vector: Vector, session: Any, ctx: Any) -> VectorResult:
    result = _result(vector)
    inp = vector.data["input"]
    exp = vector.data["expect"]
    response = _send(result, session, ctx, _sidecar_ingest(inp["absolute"]["hook"]))
    _assert_error(result, "absolute", response, exp["absolute"]["error"])
    response = _send(result, session, ctx, _sidecar_ingest(inp["traversal"]["hook"]))
    _assert_error(result, "traversal", response, exp["traversal"]["error"])
    return result


def _render_hook(event: str, handlers: list[dict[str, Any]], target: str) -> dict[str, Any]:
    return render({"hook": {"event": event, "handlers": handlers}}, target)


def _assert_diagnostic_absent(result: VectorResult, case: str, response: AdapterResponse, diagnostic_id: str) -> None:
    if response.kind == "unsupported":
        result.set_status("unsupported", f"{case}: adapter returned unsupported")
        return
    if response.kind == "harness-error":
        return
    observed = [d.get("id") for d in diagnostics_for(response) if d.get("id") == diagnostic_id]
    result.add_check(case, "diagnostic_absent", diagnostic_id, observed, not observed)


@binding("TV-HOOK-k")
def tv_hook_k(vector: Vector, session: Any, ctx: Any) -> VectorResult:
    result = _result(vector)
    inp = vector.data["input"]
    exp = vector.data["expect"]
    for name, case in inp["cases"].items():
        response = _send(result, session, ctx, _render_hook(case["event"], inp["common_handlers"], inp["render_target"]))
        assert_output_contains(result, name, response, "emitted", exp[name]["emitted"])
        assert_output_excludes(result, name, response, "excluded", exp[name]["excluded"])
        _assert_diagnostic_absent(result, name, response, exp["diagnostic_absent"])
    return result


@binding("TV-HOOK-l")
def tv_hook_l(vector: Vector, session: Any, ctx: Any) -> VectorResult:
    result = _result(vector)
    inp = vector.data["input"]
    exp = vector.data["expect"]
    responses: dict[str, AdapterResponse] = {}
    for name, case in inp["cases"].items():
        hook = {"event": case["event"], "handlers": inp["common_handlers"]}
        response = _send(result, session, ctx, _provider_ingest(inp["provider"], hook))
        responses[name] = response
        _assert_value(result, name, "canonical_event", exp[name]["canonical_event"], _canonical_event(response), response)
    for left, right in inp["body_hash_equal_pairs"]:
        if _all_ok([responses[left], responses[right]]):
            hashes = [_body_hash(responses[left]), _body_hash(responses[right])]
            result.add_check(f"{left}={right}", "body_hash_equal", exp["body_hash_equal"], hashes, hashes[0] == hashes[1] and hashes[0] is not ABSENT)
    return result


@binding("TV-HOOK-m")
def tv_hook_m(vector: Vector, session: Any, ctx: Any) -> VectorResult:
    result = _result(vector)
    inp = vector.data["input"]
    exp = vector.data["expect"]
    for name, case in inp["cases"].items():
        response = send(
            result,
            session,
            ctx,
            _render_hook(case["event"], inp["common_handlers"], inp["render_target"]),
            tags={"degradation_path": "hook-event-untranslatable", "paired_diagnostic": exp[name]["diagnostic"]},
        )
        assert_output_contains(result, name, response, "emitted", exp[name]["emitted"])
        assert_diagnostic(result, name, response, exp[name]["diagnostic"], exp[name]["params"])
    return result


@binding("TV-HOOK-n")
def tv_hook_n(vector: Vector, session: Any, ctx: Any) -> VectorResult:
    result = _result(vector)
    inp = vector.data["input"]
    exp = vector.data["expect"]
    responses: dict[str, AdapterResponse] = {}
    for name, case in inp["cases"].items():
        hook = {"event": case["event"], "handlers": inp["common_handlers"]}
        response = _send(result, session, ctx, _provider_ingest(inp["provider"], hook))
        responses[name] = response
        _assert_value(result, name, "canonical_event", exp[name]["canonical_event"], _canonical_event(response), response)
    for left, right in inp["body_hash_equal_pairs"]:
        if _all_ok([responses[left], responses[right]]):
            hashes = [_body_hash(responses[left]), _body_hash(responses[right])]
            result.add_check(f"{left}={right}", "body_hash_equal", exp["body_hash_equal"], hashes, hashes[0] == hashes[1] and hashes[0] is not ABSENT)
    for name, case in inp["rejects"].items():
        hook = {"event": case["event"], "handlers": inp["common_handlers"]}
        response = _send(result, session, ctx, _provider_ingest(case.get("provider", inp["provider"]), hook))
        _assert_error(result, name, response, exp[name]["error"])
    return result


@binding("TV-HOOK-o")
def tv_hook_o(vector: Vector, session: Any, ctx: Any) -> VectorResult:
    result = _result(vector)
    inp = vector.data["input"]
    exp = vector.data["expect"]
    for name, case in inp["cases"].items():
        response = _send(result, session, ctx, _render_hook(case["event"], inp["common_handlers"], case["target"]))
        assert_output_contains(result, name, response, "emitted", exp[name]["emitted"])
        assert_output_excludes(result, name, response, "excluded", exp[name]["excluded"])
        _assert_diagnostic_absent(result, name, response, exp["diagnostic_absent"])
    return result


@binding("TV-HOOK-p")
def tv_hook_p(vector: Vector, session: Any, ctx: Any) -> VectorResult:
    result = _result(vector)
    inp = vector.data["input"]
    exp = vector.data["expect"]
    responses: dict[str, AdapterResponse] = {}
    for name, case in inp["cases"].items():
        hook = {"event": case["event"], "handlers": inp["common_handlers"]}
        response = _send(result, session, ctx, _provider_ingest(case["provider"], hook))
        responses[name] = response
        _assert_value(result, name, "canonical_event", exp[name]["canonical_event"], _canonical_event(response), response)
    for left, right in inp["body_hash_equal_pairs"]:
        if _all_ok([responses[left], responses[right]]):
            hashes = [_body_hash(responses[left]), _body_hash(responses[right])]
            result.add_check(f"{left}={right}", "body_hash_equal", exp["body_hash_equal"], hashes, hashes[0] == hashes[1] and hashes[0] is not ABSENT)
    return result


@binding("TV-HOOK-q")
def tv_hook_q(vector: Vector, session: Any, ctx: Any) -> VectorResult:
    result = _result(vector)
    inp = vector.data["input"]
    exp = vector.data["expect"]
    for name, case in inp["cases"].items():
        response = send(
            result,
            session,
            ctx,
            _render_hook(case["event"], inp["common_handlers"], case["target"]),
            tags={"degradation_path": "hook-event-untranslatable", "paired_diagnostic": exp[name]["diagnostic"]},
        )
        assert_output_contains(result, name, response, "emitted", exp[name]["emitted"])
        assert_diagnostic(result, name, response, exp[name]["diagnostic"], exp[name]["params"])
    return result


@binding("TV-HOOK-r")
def tv_hook_r(vector: Vector, session: Any, ctx: Any) -> VectorResult:
    result = _result(vector)
    inp = vector.data["input"]
    exp = vector.data["expect"]
    responses: dict[str, AdapterResponse] = {}
    for name, case in inp["cases"].items():
        hook = {"event": case["event"], "matcher": case["matcher"], "handlers": inp["common_handlers"]}
        response = _send(result, session, ctx, _provider_ingest(inp["provider"], hook))
        responses[name] = response
        _assert_value(result, name, "canonical_event", exp[name]["canonical_event"], _canonical_event(response), response)
        if "canonical_matcher" in exp[name]:
            _assert_value(result, name, "canonical_matcher", exp[name]["canonical_matcher"], _canonical_matcher(response), response)
    for left, right in inp["body_hash_distinct_pairs"]:
        if _all_ok([responses[left], responses[right]]):
            hashes = [_body_hash(responses[left]), _body_hash(responses[right])]
            result.add_check(f"{left}!={right}", "body_hash_distinct", exp["body_hash_distinct"], hashes, hashes[0] != hashes[1] and ABSENT not in hashes)
    return result
