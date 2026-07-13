from __future__ import annotations

import json
from typing import Any

import yaml

from . import binding
from .common import (
    ABSENT,
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
        result.add_check("invocations", "output_byte_identical", exp["output_byte_identical"], outputs, len(set(outputs)) == 1)
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
        result.add_check(target, "output_parses_in_target_format", exp["output_parses_in_target_format"], parses, parses == exp["output_parses_in_target_format"])
        result.add_check(target, "value_round_trips_byte_identical", exp["value_round_trips_byte_identical"], round_trips, round_trips == exp["value_round_trips_byte_identical"])
        # DERIVATION: [ACIF-RENDER] §8; [ACIF-CORE] §8.5 (from vector spec)
        # defines splice detection as the negation of structured parse+roundtrip.
        splice_detected = not (parses and round_trips)
        result.add_check(target, "string_splice_detected", exp["string_splice_detected"], splice_detected, splice_detected == exp["string_splice_detected"])
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
        if "roundtrip_body_hash_identical" in expected and all(response.kind == "ok" for response in (before, rendered, roundtrip)):
            result.add_check(
                f"case_{idx}",
                "roundtrip_body_hash_identical",
                expected["roundtrip_body_hash_identical"],
                [hash_value(before, "body_hash"), hash_value(roundtrip, "body_hash")],
                hash_value(before, "body_hash") == hash_value(roundtrip, "body_hash"),
            )
        if "differences_within_lossy_set" in expected:
            lossy = hash_value(rendered, "lossy")
            observed = sorted(lossy) if isinstance(lossy, list) else ABSENT
            expected_lossy = sorted(case["lossy_set"])
            result.add_check(f"case_{idx}", "lossy_set", case["lossy_set"], observed, observed == expected_lossy)
            result.add_check(
                f"case_{idx}",
                "differences_within_lossy_set",
                expected["differences_within_lossy_set"],
                observed,
                observed == expected_lossy,
            )
    return result


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


_register_invariant()
