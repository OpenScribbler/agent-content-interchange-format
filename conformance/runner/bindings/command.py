from __future__ import annotations

from typing import Any

from . import binding
from .common import (
    ABSENT,
    assert_diagnostic,
    assert_output_contains,
    assert_output_equals,
    assert_relation,
    assert_result_field,
    assert_verdict_reason,
    assert_value,
    evaluate_requires,
    field,
    hash_value,
    ingest,
    output_value,
    project,
    render,
    result_for,
    send,
)
from ..protocol import AdapterResponse
from ..vectors import Vector


def _command_item(command: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"command": {} if command is None else command}


def _entry_file(source: dict[str, Any]) -> str:
    return next(iter(source["files"]))


def _ingest_files(ctx: Any, source: dict[str, Any], *, source_provider: str | None = None) -> dict[str, Any]:
    context = {"source_provider": source_provider} if source_provider is not None else None
    return ingest("command", body_root=ctx.materialize(source["files"]), entry_file=_entry_file(source), context=context)


def _canonical_body(response: AdapterResponse) -> Any:
    canonical = hash_value(response, "canonical")
    for path in ("command.body", "command.prose", "body", "prose"):
        observed = field(canonical, path)
        if observed is not ABSENT:
            return observed
    return ABSENT


def _advisory_present(response: AdapterResponse) -> Any:
    projection = hash_value(response, "projection")
    return field(projection, "argument_substitution_token.present")


def _all_ok(responses: list[AdapterResponse]) -> bool:
    return all(response.kind == "ok" for response in responses)


@binding("TV-COMMAND-a")
def tv_command_a(vector: Vector, session: Any, ctx: Any):
    result = result_for(vector)
    inp = vector.data["input"]
    exp = vector.data["expect"]
    gemini = send(result, session, ctx, _ingest_files(ctx, inp["source_gemini"], source_provider="gemini-form"))
    canonical = send(result, session, ctx, _ingest_files(ctx, inp["source_canonical"], source_provider="canonical"))
    for case, response in (("source_gemini", gemini), ("source_canonical", canonical)):
        assert_value(result, case, "canonical_body", exp["canonical_body"], _canonical_body(response), response)
        assert_result_field(result, case, response, "body_hash", exp["body_hash"])
    if _all_ok([gemini, canonical]):
        assert_relation(
            result,
            "sources",
            "body_hash_identical_across_sources",
            exp["body_hash_identical_across_sources"],
            [hash_value(gemini, "body_hash"), hash_value(canonical, "body_hash")],
            hash_value(gemini, "body_hash") == hash_value(canonical, "body_hash"),
        )
    render_gemini = send(result, session, ctx, render(hash_value(canonical, "canonical"), "gemini-form"))
    assert_output_equals(result, "render_gemini", render_gemini, exp["render_gemini"])
    render_no_row = send(
        result,
        session,
        ctx,
        render(hash_value(canonical, "canonical"), "no-row-target"),
        tags={"degradation_path": "command-untranslated", "paired_diagnostic": exp["render_no_row"]["diagnostic"]},
    )
    assert_output_contains(result, "render_no_row", render_no_row, "carries", exp["render_no_row"]["carries"])
    assert_diagnostic(result, "render_no_row", render_no_row, exp["render_no_row"]["diagnostic"])
    return result


@binding("TV-COMMAND-b")
def tv_command_b(vector: Vector, session: Any, ctx: Any):
    result = result_for(vector)
    inp = vector.data["input"]
    exp = vector.data["expect"]
    responses: list[AdapterResponse] = []
    for case in ("variant_1", "variant_2"):
        response = send(result, session, ctx, _ingest_files(ctx, inp[case], source_provider="input-form"))
        responses.append(response)
        assert_value(result, case, "canonical_body", exp["canonical_body"], _canonical_body(response), response)
        assert_result_field(result, case, response, "body_hash", exp["body_hash"])
        assert_diagnostic(result, case, response, exp["diagnostic"])
    if _all_ok(responses):
        assert_relation(
            result,
            "variants",
            "body_hash_identical",
            exp["body_hash_identical"],
            [hash_value(response, "body_hash") for response in responses],
            hash_value(responses[0], "body_hash") == hash_value(responses[1], "body_hash"),
        )
        rendered = send(result, session, ctx, render(hash_value(responses[0], "canonical"), "input-form"))
        original = next(iter(inp["variant_1"]["files"].values()))
        rendered_output = output_value(rendered)
        observed_identity = rendered_output == original if isinstance(rendered_output, str) else ABSENT
        assert_relation(
            result,
            "render",
            "render_back_identity",
            exp["render_back_identity"],
            observed_identity,
            observed_identity is True,
        )
    return result


@binding("TV-COMMAND-c")
def tv_command_c(vector: Vector, session: Any, ctx: Any):
    result = result_for(vector)
    for idx, case in enumerate(vector.data["input"]["cases"], start=1):
        item = _command_item({"body": case["body"]})
        response = send(result, session, ctx, project(item, "advisory"))
        expected_label = vector.data["expect"][f"case_{idx}"]
        expected = expected_label == "recognized"
        result.add_check_equivalent(expected_label)
        assert_value(result, f"case_{idx}", "argument_substitution_token.present", expected, _advisory_present(response), response)
    return result


@binding("TV-COMMAND-d")
def tv_command_d(vector: Vector, session: Any, ctx: Any):
    result = result_for(vector)
    inp = vector.data["input"]
    exp = vector.data["expect"]
    response = send(result, session, ctx, _ingest_files(ctx, {"files": inp["files"]}, source_provider="gemini-form"))
    assert_value(result, "files", "canonical_body", exp["canonical_body"], _canonical_body(response), response)
    advisory = send(result, session, ctx, project(hash_value(response, "canonical"), "advisory"))
    observed = _advisory_present(advisory)
    assert_relation(result, "files", "advisory_scan_counts_fenced_token", exp["advisory_scan_counts_fenced_token"], observed, observed)
    return result


@binding("TV-COMMAND-e")
def tv_command_e(vector: Vector, session: Any, ctx: Any):
    result = result_for(vector)
    exp = vector.data["expect"]
    response = send(result, session, ctx, _ingest_files(ctx, vector.data["input"], source_provider="canonical"))
    advisory = send(result, session, ctx, project(hash_value(response, "canonical"), "advisory"))
    observed = _advisory_present(advisory)
    assert_relation(result, "files", "recognized_as_placeholder", exp["recognized_as_placeholder"], observed, observed)
    # DERIVATION: [ACIF-COMMAND] §7 (from vector spec) has no escape
    # grammar; the same advisory observation carries this boolean.
    assert_relation(result, "files", "no_escape_grammar", exp["no_escape_grammar"], observed, observed)
    return result


@binding("TV-COMMAND-f")
def tv_command_f(vector: Vector, session: Any, ctx: Any):
    result = result_for(vector)
    exp = vector.data["expect"]
    response = send(result, session, ctx, _ingest_files(ctx, vector.data["input"], source_provider="canonical"))
    original = next(iter(vector.data["input"]["files"].values()))
    assert_relation(result, "files", "canonical_body_verbatim", exp["canonical_body_verbatim"], _canonical_body(response), _canonical_body(response) == original)
    advisory = send(result, session, ctx, project(hash_value(response, "canonical"), "advisory"))
    assert_result_field(result, "files", advisory, "projection", exp["advisory"])
    result.add_check_equivalent(exp["note"])
    return result


@binding("TV-COMMAND-g")
def tv_command_g(vector: Vector, session: Any, ctx: Any):
    result = result_for(vector)
    exp = vector.data["expect"]
    response = send(result, session, ctx, _ingest_files(ctx, vector.data["input"], source_provider="canonical"))
    original = next(iter(vector.data["input"]["files"].values()))
    assert_relation(result, "files", "canonical_body_verbatim", exp["canonical_body_verbatim"], _canonical_body(response), _canonical_body(response) == original)
    advisory = send(result, session, ctx, project(hash_value(response, "canonical"), "advisory"))
    observed = _advisory_present(advisory)
    observed_bool = observed is False
    assert_relation(result, "files", "not_recognized_as_placeholder", exp["not_recognized_as_placeholder"], observed_bool, observed_bool)
    return result


@binding("TV-COMMAND-h")
def tv_command_h(vector: Vector, session: Any, ctx: Any):
    result = result_for(vector)
    inp = vector.data["input"]
    exp = vector.data["expect"]
    responses = []
    for case in ("variant_1", "variant_2"):
        response = send(result, session, ctx, _ingest_files(ctx, inp[case], source_provider="canonical"))
        responses.append(response)
        assert_result_field(result, case, response, "body_hash", exp["body_hash"])
    if _all_ok(responses):
        assert_relation(result, "variants", "body_hash_identical", exp["body_hash_identical"], [hash_value(r, "body_hash") for r in responses], hash_value(responses[0], "body_hash") == hash_value(responses[1], "body_hash"))
        assert_relation(result, "variants", "metadata_hash_differs", exp["metadata_hash_differs"], [hash_value(r, "metadata_hash") for r in responses], hash_value(responses[0], "metadata_hash") != hash_value(responses[1], "metadata_hash"))
    return result


@binding("TV-COMMAND-i")
def tv_command_i(vector: Vector, session: Any, ctx: Any):
    result = result_for(vector)
    expected = vector.data["expect"]["conformant"]
    for idx, variant in enumerate(vector.data["input"]["variants"]):
        response = send(result, session, ctx, ingest("command", sidecar=_command_item(variant["command"])))
        assert_result_field(result, f"variants[{idx}]", response, "conformant", expected)
    return result


@binding("TV-COMMAND-j")
def tv_command_j(vector: Vector, session: Any, ctx: Any):
    result = result_for(vector)
    for idx, case in enumerate(vector.data["input"]["cases"], start=1):
        expected = vector.data["expect"][f"case_{idx}"]
        response = send(result, session, ctx, ingest("command", sidecar=_command_item(case["command"])))
        assert_result_field(result, f"case_{idx}", response, "conformant", expected["conformant"])
        assert_verdict_reason(result, f"case_{idx}", response, expected["reason"], session, expected.get("params"))
    return result


@binding("TV-COMMAND-k")
def tv_command_k(vector: Vector, session: Any, ctx: Any):
    result = result_for(vector)
    inp = vector.data["input"]
    exp = vector.data["expect"]
    response = send(result, session, ctx, evaluate_requires(inp["item_requires"], inp["consumer_recognizes"]))
    assert_result_field(result, "requires", response, "evaluation", exp["evaluation"])
    assert_result_field(result, "requires", response, "install", exp["install"])
    return result


@binding("TV-COMMAND-l")
def tv_command_l(vector: Vector, session: Any, ctx: Any):
    result = result_for(vector)
    exp = vector.data["expect"]["if_emitted"]
    response = send(result, session, ctx, project(_command_item(vector.data["input"]["command"]), "builtin_shadowing_advisory"))
    if response.kind == "ok" and hash_value(response, "projection") is ABSENT:
        result.vacuous = True
        return result
    assert_result_field(result, "if_emitted", response, "projection.names_provider", exp["names_provider"])
    assert_result_field(result, "if_emitted", response, "projection.names_colliding_name", exp["names_colliding_name"])
    return result


@binding("TV-COMMAND-m")
def tv_command_m(vector: Vector, session: Any, ctx: Any):
    result = result_for(vector)
    exp = vector.data["expect"]
    response = send(result, session, ctx, _ingest_files(ctx, vector.data["input"], source_provider="canonical"))
    advisory = send(result, session, ctx, project(hash_value(response, "canonical"), "advisory"))
    assert_result_field(result, "files", advisory, "projection", exp["advisory"])
    if advisory.kind == "ok":
        observed_projection = hash_value(advisory, "projection")
        forbidden_present = [name for name in exp["forbidden_fields"] if field(observed_projection, f"argument_substitution_token.{name}") is not ABSENT]
        result.add_check("files", "forbidden_fields", exp["forbidden_fields"], forbidden_present, forbidden_present == [])
    return result
