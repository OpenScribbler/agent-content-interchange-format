from __future__ import annotations

import copy
from typing import Any

import yaml

from . import binding
from .common import (
    assert_derived_capability,
    assert_error,
    assert_ok,
    assert_relation,
    assert_result_field,
    evaluate_requires,
    hash_value,
    ingest,
    project_derived_capabilities,
    resolve_reference,
    result_for,
    send,
)
from ..protocol import AdapterResponse
from ..vectors import Vector


def _skill_item(skill: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"skill": {} if skill is None else skill}


def _activation_case(case: dict[str, Any]) -> dict[str, Any]:
    if case.get("activation") == "absent":
        return _skill_item({})
    return _skill_item({"activation": case["activation"]})


def _entry_file(source: dict[str, Any]) -> str:
    return source.get("entry_file", "SKILL.md")


def _ingest_files(ctx: Any, source: dict[str, Any]) -> dict[str, Any]:
    root = ctx.materialize(source["files"])
    return ingest("skill", body_root=root, entry_file=_entry_file(source))


def _split_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---\n", 4)
    if end == -1:
        return {}, text
    raw = text[4:end]
    body = text[end + len("\n---\n") :]
    parsed = yaml.safe_load(raw) or {}
    return parsed, body


def _deep_update(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(base)
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_update(out[key], value)
        else:
            out[key] = value
    return out


def _with_frontmatter(files: dict[str, str], entry_file: str, patch: dict[str, Any]) -> dict[str, str]:
    updated = dict(files)
    frontmatter, body = _split_frontmatter(updated[entry_file])
    frontmatter = _deep_update(frontmatter, patch)
    updated[entry_file] = "---\n" + yaml.safe_dump(frontmatter, sort_keys=False) + "---\n" + body
    return updated


def _with_entry_body(files: dict[str, str], entry_file: str, body: str) -> dict[str, str]:
    updated = dict(files)
    frontmatter, _ = _split_frontmatter(updated[entry_file])
    if frontmatter:
        updated[entry_file] = "---\n" + yaml.safe_dump(frontmatter, sort_keys=False) + "---\n" + body
    else:
        updated[entry_file] = body
    return updated


def _all_ok(responses: list[AdapterResponse]) -> bool:
    return all(response.kind == "ok" for response in responses)


@binding("TV-SKILL-a")
def tv_skill_a(vector: Vector, session: Any, ctx: Any):
    result = result_for(vector)
    expected = vector.data["expect"]["conformant"]
    for idx, variant in enumerate(vector.data["input"]["variants"]):
        response = send(result, session, ctx, ingest("skill", sidecar=_skill_item(variant["skill"])))
        assert_result_field(result, f"variants[{idx}]", response, "conformant", expected)
    return result


@binding("TV-SKILL-b")
def tv_skill_b(vector: Vector, session: Any, ctx: Any):
    result = result_for(vector)
    inp = vector.data["input"]
    exp = vector.data["expect"]
    # PROTOCOL.md §3: reason is informative diagnostic text, never asserted.
    response = send(result, session, ctx, ingest("skill", sidecar=_skill_item(inp["foreign"]["skill"])))
    assert_result_field(result, "foreign", response, "conformant", exp["foreign"]["conformant"])
    response = send(result, session, ctx, ingest("skill", sidecar=inp["latent_match"]))
    assert_result_field(result, "latent_match", response, "conformant", exp["latent_match"]["conformant"])
    return result


@binding("TV-SKILL-c")
def tv_skill_c(vector: Vector, session: Any, ctx: Any):
    result = result_for(vector)
    inp = vector.data["input"]
    exp = vector.data["expect"]
    response = send(result, session, ctx, evaluate_requires(inp["item_requires"], inp["consumer_recognizes"]))
    assert_result_field(result, "requires", response, "evaluation", exp["evaluation"])
    assert_result_field(result, "requires", response, "install", exp["install"])
    return result


@binding("TV-SKILL-d")
def tv_skill_d(vector: Vector, session: Any, ctx: Any):
    result = result_for(vector)
    for idx, case in enumerate(vector.data["input"]["cases"], start=1):
        response = send(result, session, ctx, project_derived_capabilities(_activation_case(case)))
        # DERIVATION: [ACIF-SKILL] §10.1 (from vector spec) maps activation
        # type/defaults to the auto_invocable D_K boolean.
        assert_derived_capability(result, f"case_{idx}", response, "auto_invocable", vector.data["expect"][f"case_{idx}"])
    return result


@binding("TV-SKILL-e")
def tv_skill_e(vector: Vector, session: Any, ctx: Any):
    result = result_for(vector)
    for idx, case in enumerate(vector.data["input"]["cases"], start=1):
        response = send(result, session, ctx, project_derived_capabilities(_activation_case(case)))
        # DERIVATION: [ACIF-SKILL] §10.1 (from vector spec) maps activation
        # type/defaults to the disable_model_invocation D_K boolean.
        assert_derived_capability(result, f"case_{idx}", response, "disable_model_invocation", vector.data["expect"][f"case_{idx}"])
    return result


@binding("TV-SKILL-f")
def tv_skill_f(vector: Vector, session: Any, ctx: Any):
    result = result_for(vector)
    for idx, case in enumerate(vector.data["input"]["cases"], start=1):
        response = send(result, session, ctx, project_derived_capabilities(_activation_case(case)))
        # DERIVATION: [ACIF-SKILL] §10.1 (from vector spec) defines
        # user_invocable as a resolves-to-false predicate.
        assert_derived_capability(result, f"case_{idx}", response, "user_invocable", vector.data["expect"][f"case_{idx}"])
    return result


@binding("TV-SKILL-g")
def tv_skill_g(vector: Vector, session: Any, ctx: Any):
    result = result_for(vector)
    case_1_response: AdapterResponse | None = None
    for idx, case in enumerate(vector.data["input"]["cases"], start=1):
        expected = vector.data["expect"][f"case_{idx}"]
        response = send(result, session, ctx, _ingest_files(ctx, {"files": case["files"]}))
        if idx == 1:
            case_1_response = response
        assert_result_field(result, f"case_{idx}", response, "classification", expected["classification"])
        if "body_hash" in expected:
            assert_result_field(result, f"case_{idx}", response, "body_hash", expected["body_hash"])
        if "body_hash_equals_case_1" in expected and case_1_response is not None and response.kind == "ok" and case_1_response.kind == "ok":
            assert_relation(
                result,
                f"case_{idx}",
                "body_hash_equals_case_1",
                expected["body_hash_equals_case_1"],
                [hash_value(case_1_response, "body_hash"), hash_value(response, "body_hash")],
                hash_value(case_1_response, "body_hash") == hash_value(response, "body_hash"),
            )
        if "skill_bundled_resources" in expected:
            canonical = hash_value(response, "canonical")
            projection = send(result, session, ctx, project_derived_capabilities(canonical))
            # DERIVATION: [ACIF-SKILL] §10.1; [ACIF-CORE] §7.2 (from vector
            # spec) maps body classification to skill_bundled_resources.
            assert_derived_capability(result, f"case_{idx}", projection, "skill_bundled_resources", expected["skill_bundled_resources"])
    return result


@binding("TV-SKILL-h")
def tv_skill_h(vector: Vector, session: Any, ctx: Any):
    result = result_for(vector)
    inp = vector.data["input"]
    exp = vector.data["expect"]
    source = inp["source"]
    base = send(result, session, ctx, _ingest_files(ctx, source))
    assert_result_field(result, "source", base, "canonical.skill.activation", exp["canonical.skill.activation"])
    declared_files = _with_frontmatter(source["files"], _entry_file(source), {"activation": exp["canonical.skill.activation"]})
    declared = send(result, session, ctx, _ingest_files(ctx, {"files": declared_files, "entry_file": _entry_file(source)}))
    if _all_ok([base, declared]):
        assert_relation(
            result,
            "source",
            "body_hash_unaffected_by_materialization",
            exp["body_hash_unaffected_by_materialization"],
            [hash_value(base, "body_hash"), hash_value(declared, "body_hash")],
            hash_value(base, "body_hash") == hash_value(declared, "body_hash"),
        )
        assert_relation(
            result,
            "source",
            "metadata_hash_unaffected_by_materialization",
            exp["metadata_hash_unaffected_by_materialization"],
            [hash_value(base, "metadata_hash"), hash_value(declared, "metadata_hash")],
            hash_value(base, "metadata_hash") == hash_value(declared, "metadata_hash"),
        )
    return result


@binding("TV-SKILL-i")
def tv_skill_i(vector: Vector, session: Any, ctx: Any):
    result = result_for(vector)
    for idx, case in enumerate(vector.data["input"]["cases"], start=1):
        response = send(result, session, ctx, _ingest_files(ctx, {"files": case["files"]}))
        assert_result_field(result, f"case_{idx}", response, "classification", vector.data["expect"][f"case_{idx}"])
    return result


@binding("TV-SKILL-j")
def tv_skill_j(vector: Vector, session: Any, ctx: Any):
    result = result_for(vector)
    inp = vector.data["input"]
    exp = vector.data["expect"]
    response = send(result, session, ctx, resolve_reference(_skill_item(inp["skill"]), inp["registry_state"]))
    assert_result_field(result, "skill", response, "cross_reference", exp["cross_reference"])
    if response.kind == "ok":
        observed = bool(hash_value(response, "reciprocal_entries"))
        assert_relation(result, "skill", "reciprocal_entry_emitted", exp["reciprocal_entry_emitted"], observed, observed)
    return result


@binding("TV-SKILL-k")
def tv_skill_k(vector: Vector, session: Any, ctx: Any):
    result = result_for(vector)
    inp = vector.data["input"]
    exp = vector.data["expect"]
    base_files = inp["base"]["files"]
    base = send(result, session, ctx, _ingest_files(ctx, {"files": base_files}))
    edit_1_files = _with_frontmatter(base_files, "SKILL.md", inp["edits"][0]["frontmatter"])
    edit_1 = send(result, session, ctx, _ingest_files(ctx, {"files": edit_1_files}))
    edit_2_files = dict(base_files)
    edit_2_files[inp["edits"][1]["file"]] = inp["edits"][1]["content"]
    edit_2 = send(result, session, ctx, _ingest_files(ctx, {"files": edit_2_files}))
    if _all_ok([base, edit_1, edit_2]):
        assert_relation(result, "edit_1", "metadata_hash_moves", exp["edit_1"]["metadata_hash_moves"], [hash_value(base, "metadata_hash"), hash_value(edit_1, "metadata_hash")], hash_value(base, "metadata_hash") != hash_value(edit_1, "metadata_hash"))
        assert_relation(result, "edit_1", "body_hash_moves", exp["edit_1"]["body_hash_moves"], [hash_value(base, "body_hash"), hash_value(edit_1, "body_hash")], hash_value(base, "body_hash") != hash_value(edit_1, "body_hash"))
        assert_relation(result, "edit_2", "metadata_hash_moves", exp["edit_2"]["metadata_hash_moves"], [hash_value(base, "metadata_hash"), hash_value(edit_2, "metadata_hash")], hash_value(base, "metadata_hash") != hash_value(edit_2, "metadata_hash"))
        assert_relation(result, "edit_2", "body_hash_moves", exp["edit_2"]["body_hash_moves"], [hash_value(base, "body_hash"), hash_value(edit_2, "body_hash")], hash_value(base, "body_hash") != hash_value(edit_2, "body_hash"))
    return result


@binding("TV-SKILL-l")
def tv_skill_l(vector: Vector, session: Any, ctx: Any):
    result = result_for(vector)
    for idx, case in enumerate(vector.data["input"]["cases"], start=1):
        response = send(result, session, ctx, ingest("skill", sidecar=_skill_item({"activation": case["activation"]})))
        assert_error(result, f"case_{idx}", response, vector.data["expect"][f"case_{idx}"]["error"])
    return result


@binding("TV-SKILL-m")
def tv_skill_m(vector: Vector, session: Any, ctx: Any):
    result = result_for(vector)
    response = send(result, session, ctx, ingest("skill", sidecar=_skill_item(vector.data["input"]["skill"])))
    assert_ok(result, "skill", response, "accept", vector.data["expect"]["accept"])
    return result


@binding("TV-SKILL-n")
def tv_skill_n(vector: Vector, session: Any, ctx: Any):
    result = result_for(vector)
    inp = vector.data["input"]
    exp = vector.data["expect"]
    responses: list[AdapterResponse] = []
    for case in ("variant_1", "variant_2"):
        response = send(result, session, ctx, _ingest_files(ctx, inp[case]))
        responses.append(response)
        assert_result_field(result, case, response, "classification", exp["classification"])
        assert_result_field(result, case, response, "body_hash", exp["body_hash"])
    if _all_ok(responses):
        assert_relation(
            result,
            "variants",
            "body_hash_identical_across_variants",
            exp["body_hash_identical_across_variants"],
            [hash_value(response, "body_hash") for response in responses],
            hash_value(responses[0], "body_hash") == hash_value(responses[1], "body_hash"),
        )
    return result
