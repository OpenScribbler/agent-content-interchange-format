from __future__ import annotations

import json
from typing import Any

import yaml

from . import binding
from .common import (
    ABSENT,
    _blocked_for_result_assertion,
    assert_relation,
    diagnostics_for,
    hash_value,
    ingest,
    output_value,
    provider_config,
    render,
    result_for,
    send,
)
from ..report import VectorResult
from ..vectors import Vector


TRIGGERS = {
    "hook-os-drop": {"vector": "TV-PLATFORM-o", "scope": "hook"},
    "rule-gate-loss": {"vector": "TV-RULE-m", "scope": "rule"},
    "command-untranslated": {"vector": "TV-COMMAND-a", "scope": "command"},
}


def _parse_output(target: str, output: Any) -> Any:
    if not isinstance(output, str):
        return ABSENT
    try:
        if target == "json-format":
            return json.loads(output)
        if target == "yaml-format":
            return yaml.safe_load(output)
    except Exception:
        return ABSENT
    return output


def _contains_value(value: Any, expected: Any) -> bool:
    if value == expected:
        return True
    if isinstance(value, dict):
        return any(_contains_value(child, expected) for child in value.values())
    if isinstance(value, list):
        return any(_contains_value(child, expected) for child in value)
    return False


def _canonical_for_type(kind: str) -> dict[str, Any]:
    if kind == "mcp_config":
        return {"mcp": {"servers": {"demo": {"type": "stdio", "command": "npx"}}}}
    if kind == "agent":
        return {"agent": {"tools": ["file_edit", "file_write"]}}
    return {kind: {}}


@binding("TV-RENDER-a")
def tv_render_a(vector: Vector, session: Any, ctx: Any):
    result = result_for(vector)
    inp = vector.data["input"]
    exp = vector.data["expect"]
    target = inp["render_context"]["target_provider"]
    responses = [
        send(result, session, ctx, render(inp["canonical"], target, inp["render_context"]))
        for _ in range(inp["invocations"])
    ]
    if all(response.kind == "ok" for response in responses):
        outputs = [output_value(response) for response in responses]
        assert_relation(result, "invocations", "output_byte_identical", exp["output_byte_identical"], outputs, len(set(outputs)) == 1)
    return result


@binding("TV-RENDER-b")
def tv_render_b(vector: Vector, session: Any, ctx: Any):
    result = result_for(vector)
    inp = vector.data["input"]
    exp = vector.data["expect"]
    for target in inp["render_targets"]:
        canonical = {"passthrough": inp["canonical_passthrough_value"]}
        response = send(result, session, ctx, render(canonical, target))
        parsed = _parse_output(target, output_value(response))
        parses = parsed is not ABSENT
        round_trips = _contains_value(parsed, inp["canonical_passthrough_value"]) if parses else False
        assert_relation(result, target, "output_parses_in_target_format", exp["output_parses_in_target_format"], parses, parses)
        assert_relation(result, target, "value_round_trips_byte_identical", exp["value_round_trips_byte_identical"], round_trips, round_trips)
        # DERIVATION: [ACIF-RENDER] §8; [ACIF-CORE] §8.5 (from vector spec)
        # defines splice detection as the negation of structured parse+roundtrip.
        splice_detected = not (parses and round_trips)
        assert_relation(result, target, "string_splice_detected", exp["string_splice_detected"], splice_detected, splice_detected)
    return result


@binding("TV-RENDER-c")
def tv_render_c(vector: Vector, session: Any, ctx: Any):
    del session, ctx
    result = result_for(vector)
    result.add_check_equivalent(vector.data["expect"]["output_without_paired_diagnostic"])
    return result


@binding("TV-RENDER-d")
def tv_render_d(vector: Vector, session: Any, ctx: Any):
    result = result_for(vector)
    for idx, case in enumerate(vector.data["input"]["cases"], start=1):
        expected = vector.data["expect"][f"case_{idx}"]
        canonical = _canonical_for_type(case["type"])
        before = send(result, session, ctx, ingest(case["type"], sidecar=canonical.get("mcp") or canonical.get("agent") or canonical))
        rendered = send(result, session, ctx, render(canonical, case["target"]))
        roundtrip = send(
            result,
            session,
            ctx,
            ingest(case["type"], provider_config=provider_config(case["target"], "rendered", output_value(rendered))),
        )
        case_id = f"case_{idx}"
        responses = (before, rendered, roundtrip)
        for field_name in ("roundtrip_body_hash_identical", "differences_within_lossy_set"):
            if field_name not in expected:
                continue
            # Every leg of the round trip is part of the property: a leg
            # that errors fails the check rather than skipping it.
            if any(_blocked_for_result_assertion(result, case_id, response, field_name, expected[field_name]) for response in responses):
                continue
            if field_name == "roundtrip_body_hash_identical":
                pre_hash, post_hash = hash_value(before, "body_hash"), hash_value(roundtrip, "body_hash")
                assert_relation(result, case_id, field_name, expected[field_name], [pre_hash, post_hash], pre_hash == post_hash)
                continue
            lossy = hash_value(rendered, "lossy")
            observed = sorted(lossy) if isinstance(lossy, list) else ABSENT
            result.add_check(case_id, "lossy_set", case["lossy_set"], observed, observed == sorted(case["lossy_set"]))
            # [ACIF-RENDER] §9: canonicalize(render(C, p)) == C modulo
            # LOSSY(type, p). The declaration above is not evidence of the
            # property; compare the canonical forms structurally.
            pre = hash_value(before, "canonical")
            post = hash_value(roundtrip, "canonical")
            within = _within_lossy_set(case["type"], canonical, pre, post, case["lossy_set"])
            assert_relation(result, case_id, field_name, expected[field_name], [pre, post], within)
    return result


# Each documented-lossy token's collapse ([ACIF-CORE] Appendix A.2): the
# canonical tool names the target cannot distinguish, mapped onto the one
# reverse translation prefers. The collapse applies to the canonical
# tool-name field only; every other field must round-trip unchanged.
LOSSY_COLLAPSES = {
    "write-edit-distinction": {"file_write": "file_edit"},
}
TOOL_FIELD = {"agent": ("agent", "tools")}


def _within_lossy_set(kind: str, source: Any, pre: Any, post: Any, lossy_set: list[str]) -> bool:
    """pre is the adapter's canonical form of `source`, post its canonical
    form of the rendered output. pre's tool list must be the vector's own
    (anchoring it to what was rendered), post's must equal pre's after the
    collapse, and nothing outside the tool field may differ."""
    path = TOOL_FIELD[kind]
    source_tools, pre_tools, post_tools = (_at(value, path) for value in (source, pre, post))
    if not all(isinstance(tools, list) for tools in (source_tools, pre_tools, post_tools)):
        return False
    mapping: dict[str, str] = {}
    for token in lossy_set:
        mapping.update(LOSSY_COLLAPSES[token])
    return (
        sorted(pre_tools) == sorted(source_tools)
        and {mapping.get(t, t) for t in pre_tools} == {mapping.get(t, t) for t in post_tools}
        and _without(pre, path) == _without(post, path)
    )


def _at(value: Any, path: tuple[str, ...]) -> Any:
    for key in path:
        if not isinstance(value, dict) or key not in value:
            return ABSENT
        value = value[key]
    return value


def _without(value: Any, path: tuple[str, ...]) -> Any:
    if not path or not isinstance(value, dict):
        return value
    head, rest = path[0], path[1:]
    out = {key: child for key, child in value.items() if key != head}
    if rest and head in value:
        out[head] = _without(value[head], rest)
    return out


def _paired_degradation_invariant(observations: list[Any], vector_results: list[VectorResult]) -> None:
    rows = {row.id: row for row in vector_results}
    row = rows.get("TV-RENDER-c")
    if row is None or row.status == "out-of-scope":
        return

    exercised: set[str] = set()
    for response in observations:
        path = getattr(response, "_acif_degradation_path", None)
        expected = getattr(response, "_acif_paired_diagnostic", None)
        if path is None or expected is None:
            continue
        exercised.add(path)
        if response.kind != "ok":
            continue
        observed_ids = [diagnostic.get("id") for diagnostic in diagnostics_for(response)]
        row.add_check(path, "paired_diagnostic", expected, observed_ids, expected in observed_ids)

    for path, trigger in TRIGGERS.items():
        trigger_row = rows.get(trigger["vector"])
        if trigger_row is None or trigger_row.status == "out-of-scope":
            continue
        if path not in exercised:
            row.set_status("harness-error", f"{path}: claimed trigger vector {trigger['vector']} was not exercised")


def _register_invariant() -> None:
    from .. import run as runner_run

    if _paired_degradation_invariant not in runner_run.INVARIANT_CHECKERS:
        runner_run.INVARIANT_CHECKERS.append(_paired_degradation_invariant)
    runner_run.INVARIANT_VECTOR_IDS.add("TV-RENDER-c")


_register_invariant()
