from __future__ import annotations

from typing import Any

import yaml

from . import binding
from .common import (
    ABSENT,
    assert_derived_capability,
    assert_diagnostic,
    assert_error,
    assert_output_contains,
    assert_present_absent,
    assert_relation,
    assert_result_field,
    assert_verdict_reason,
    evaluate_requires,
    field,
    hash_value,
    ingest,
    output_value,
    project,
    project_derived_capabilities,
    provider_config,
    render,
    result_for,
    send,
)
from ..protocol import AdapterResponse
from ..vectors import Vector


def _rule_item(rule: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"rule": {} if rule is None else rule}


def _entry_file(source: dict[str, Any]) -> str:
    files = source.get("files", {})
    if "conventions.md" in files:
        return "conventions.md"
    return next(iter(files), "conventions.md")


def _ingest_files(ctx: Any, source: dict[str, Any]) -> dict[str, Any]:
    entry_file = _entry_file(source)
    return ingest("rule", body_root=ctx.materialize(source["files"]), entry_file=entry_file)


def _split_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---\n", 4)
    if end == -1:
        return {}, text
    return yaml.safe_load(text[4:end]) or {}, text[end + len("\n---\n") :]


def _with_frontmatter(files: dict[str, str], entry_file: str, patch: dict[str, Any]) -> dict[str, str]:
    updated = dict(files)
    frontmatter, body = _split_frontmatter(updated[entry_file])
    frontmatter.update(patch)
    updated[entry_file] = "---\n" + yaml.safe_dump(frontmatter, sort_keys=False) + "---\n" + body
    return updated


def _with_body(files: dict[str, str], entry_file: str, body: str) -> dict[str, str]:
    updated = dict(files)
    frontmatter, _ = _split_frontmatter(updated[entry_file])
    if frontmatter:
        updated[entry_file] = "---\n" + yaml.safe_dump(frontmatter, sort_keys=False) + "---\n" + body
    else:
        updated[entry_file] = body
    return updated


def _all_ok(responses: list[AdapterResponse]) -> bool:
    return all(response.kind == "ok" for response in responses)


@binding("TV-RULE-a")
def tv_rule_a(vector: Vector, session: Any, ctx: Any):
    result = result_for(vector)
    inp = vector.data["input"]
    exp = vector.data["expect"]
    source = inp["source"]
    base = send(result, session, ctx, _ingest_files(ctx, source))
    assert_result_field(result, "source", base, "canonical.rule.activation.mode", exp["canonical.rule.activation.mode"])
    assert_result_field(result, "source", base, "body_hash", exp["body_hash"])
    declared_files = _with_frontmatter(source["files"], _entry_file(source), {"activation": {"mode": exp["canonical.rule.activation.mode"]}})
    declared = send(result, session, ctx, _ingest_files(ctx, {"files": declared_files}))
    if _all_ok([base, declared]):
        assert_relation(
            result,
            "source",
            "body_hash_unaffected_by_materialization",
            exp["body_hash_unaffected_by_materialization"],
            [hash_value(base, "body_hash"), hash_value(declared, "body_hash")],
            hash_value(base, "body_hash") == hash_value(declared, "body_hash"),
        )
    if base.kind == "ok":
        # DERIVATION: [ACIF-RULE] §7/§8 — the materialized default is covered by
        # no hash, and this source declares no frontmatter, so faithful
        # observation ([ACIF-PUBLISHER]) yields no publisher_section and no
        # metadata_hash at all; the relation is that absence. Declaring the mode
        # MOVES metadata_hash (absent → present), so a declared-variant hash
        # comparison tests declaration, not materialization (suite repair,
        # syllago Stage 2).
        observed = hash_value(base, "metadata_hash")
        assert_relation(
            result,
            "source",
            "metadata_hash_unaffected_by_materialization",
            exp["metadata_hash_unaffected_by_materialization"],
            {"metadata_hash": observed},
            observed is ABSENT,
        )
    return result


@binding("TV-RULE-b")
def tv_rule_b(vector: Vector, session: Any, ctx: Any):
    result = result_for(vector)
    response = send(result, session, ctx, ingest("rule", sidecar=_rule_item(vector.data["input"]["rule"])))
    assert_error(result, "rule", response, vector.data["expect"]["error"])
    return result


@binding("TV-RULE-c")
def tv_rule_c(vector: Vector, session: Any, ctx: Any):
    result = result_for(vector)
    for idx, variant in enumerate(vector.data["input"]["variants"], start=1):
        response = send(result, session, ctx, ingest("rule", sidecar=_rule_item(variant["rule"])))
        assert_error(result, f"variant_{idx}", response, vector.data["expect"]["error"])
    return result


@binding("TV-RULE-d")
def tv_rule_d(vector: Vector, session: Any, ctx: Any):
    result = result_for(vector)
    exp = vector.data["expect"]
    for idx, case in enumerate(vector.data["input"]["cases"], start=1):
        response = send(result, session, ctx, ingest("rule", provider_config=provider_config("rule-activation-source", "rule", case)))
        expected = exp[f"case_{idx}"]
        if "error" in expected:
            assert_error(result, f"case_{idx}", response, expected["error"])
        else:
            assert_result_field(result, f"case_{idx}", response, "canonical.rule.activation.mode", expected["mode"])
    return result


@binding("TV-RULE-e")
def tv_rule_e(vector: Vector, session: Any, ctx: Any):
    result = result_for(vector)
    for idx, case in enumerate(vector.data["input"]["cases"], start=1):
        response = send(result, session, ctx, ingest("rule", sidecar=_rule_item(case["rule"])))
        assert_error(result, f"case_{idx}", response, vector.data["expect"][f"case_{idx}"]["error"])
    return result


@binding("TV-RULE-f")
def tv_rule_f(vector: Vector, session: Any, ctx: Any):
    result = result_for(vector)
    for idx, case in enumerate(vector.data["input"]["cases"], start=1):
        item = _rule_item({} if case.get("activation") == "absent" else {"activation": case["activation"]})
        response = send(result, session, ctx, project_derived_capabilities(item))
        # DERIVATION: [ACIF-RULE] §9.1 (from vector spec) maps activation
        # modes to the activation_mode D_K boolean.
        assert_derived_capability(result, f"case_{idx}", response, "activation_mode", vector.data["expect"][f"case_{idx}"])
    return result


@binding("TV-RULE-g")
def tv_rule_g(vector: Vector, session: Any, ctx: Any):
    result = result_for(vector)
    response = send(result, session, ctx, project(_rule_item(vector.data["input"]["rule"]), "rule_activation"))
    assert_result_field(result, "rule", response, "projection", vector.data["expect"]["projection"])
    return result


@binding("TV-RULE-h")
def tv_rule_h(vector: Vector, session: Any, ctx: Any):
    result = result_for(vector)
    expected = vector.data["expect"]["conformant"]
    for idx, variant in enumerate(vector.data["input"]["variants"]):
        response = send(result, session, ctx, ingest("rule", sidecar=_rule_item(variant["rule"])))
        assert_result_field(result, f"variants[{idx}]", response, "conformant", expected)
    return result


@binding("TV-RULE-i")
def tv_rule_i(vector: Vector, session: Any, ctx: Any):
    result = result_for(vector)
    for idx, case in enumerate(vector.data["input"]["cases"], start=1):
        expected = vector.data["expect"][f"case_{idx}"]
        response = send(result, session, ctx, ingest("rule", sidecar=_rule_item(case["rule"])))
        assert_result_field(result, f"case_{idx}", response, "conformant", expected["conformant"])
        assert_verdict_reason(result, f"case_{idx}", response, expected["reason"], session, expected.get("params"))
    return result


@binding("TV-RULE-j")
def tv_rule_j(vector: Vector, session: Any, ctx: Any):
    result = result_for(vector)
    inp = vector.data["input"]
    exp = vector.data["expect"]
    response = send(result, session, ctx, evaluate_requires(inp["item_requires"], inp["consumer_recognizes"]))
    assert_result_field(result, "requires", response, "evaluation", exp["evaluation"])
    assert_result_field(result, "requires", response, "install", exp["install"])
    return result


@binding("TV-RULE-k")
def tv_rule_k(vector: Vector, session: Any, ctx: Any):
    result = result_for(vector)
    inp = vector.data["input"]
    exp = vector.data["expect"]
    response = send(result, session, ctx, _ingest_files(ctx, {"files": inp["files"]}))
    assert_result_field(result, "files", response, "body_hash", exp["body_hash"])
    if response.kind == "ok":
        body = next(iter(inp["files"].values()))
        canonical = hash_value(response, "canonical")
        observed_canonical = field(canonical, "rule.body")
        if observed_canonical == ABSENT:
            observed_canonical = field(canonical, "body")
        assert_relation(result, "files", "canonical_body_verbatim", exp["canonical_body_verbatim"], observed_canonical, observed_canonical == body)
        rendered = send(result, session, ctx, render(hash_value(response, "canonical"), "native-rule-format"))
        assert_relation(
            result,
            "files",
            "render_back_verbatim",
            exp["render_back_verbatim"],
            output_value(rendered),
            output_value(rendered) == body,
        )
    return result


@binding("TV-RULE-l")
def tv_rule_l(vector: Vector, session: Any, ctx: Any):
    result = result_for(vector)
    inp = vector.data["input"]
    exp = vector.data["expect"]
    base_files = inp["base"]["files"]
    entry_file = next(iter(base_files))
    base = send(result, session, ctx, _ingest_files(ctx, {"files": base_files}))
    edit_1_files = _with_frontmatter(base_files, entry_file, inp["edits"][0]["frontmatter"])
    edit_1 = send(result, session, ctx, _ingest_files(ctx, {"files": edit_1_files}))
    edit_2_files = _with_body(base_files, entry_file, inp["edits"][1]["prose"])
    edit_2 = send(result, session, ctx, _ingest_files(ctx, {"files": edit_2_files}))
    if _all_ok([base, edit_1, edit_2]):
        assert_relation(result, "edit_1", "metadata_hash_moves", exp["edit_1"]["metadata_hash_moves"], [hash_value(base, "metadata_hash"), hash_value(edit_1, "metadata_hash")], hash_value(base, "metadata_hash") != hash_value(edit_1, "metadata_hash"))
        assert_relation(result, "edit_1", "body_hash_moves", exp["edit_1"]["body_hash_moves"], [hash_value(base, "body_hash"), hash_value(edit_1, "body_hash")], hash_value(base, "body_hash") != hash_value(edit_1, "body_hash"))
        assert_relation(result, "edit_2", "metadata_hash_moves", exp["edit_2"]["metadata_hash_moves"], [hash_value(base, "metadata_hash"), hash_value(edit_2, "metadata_hash")], hash_value(base, "metadata_hash") != hash_value(edit_2, "metadata_hash"))
        assert_relation(result, "edit_2", "body_hash_moves", exp["edit_2"]["body_hash_moves"], [hash_value(base, "body_hash"), hash_value(edit_2, "body_hash")], hash_value(base, "body_hash") != hash_value(edit_2, "body_hash"))
    return result


@binding("TV-RULE-m")
def tv_rule_m(vector: Vector, session: Any, ctx: Any):
    result = result_for(vector)
    inp = vector.data["input"]
    exp = vector.data["expect"]
    response = send(
        result,
        session,
        ctx,
        render(inp["canonical"], inp["render_target"]),
        tags={"degradation_path": "rule-gate-loss", "paired_diagnostic": exp["diagnostic"]},
    )
    assert_output_contains(result, "render", response, "emitted", exp["emitted"])
    assert_diagnostic(result, "render", response, exp["diagnostic"], exp["diagnostic_names"])
    return result


@binding("TV-RULE-n")
def tv_rule_n(vector: Vector, session: Any, ctx: Any):
    result = result_for(vector)
    exp = vector.data["expect"]
    for idx, case in enumerate(vector.data["input"]["cases"], start=1):
        response = send(result, session, ctx, ingest("rule", provider_config=provider_config("rule-activation-source", "rule", case)))
        expected = exp[f"case_{idx}"]
        assert_result_field(result, f"case_{idx}", response, "canonical.rule.activation.mode", expected["mode"])
        # DERIVATION: [ACIF-RULE] Appendix A.2 legacy interior rule 1 (from
        # vector spec) — the always branch discards globs from canonical form.
        if expected["globs"] == "absent":
            assert_present_absent(result, f"case_{idx}", response, "canonical.rule.activation.globs", "absent")
        else:
            assert_result_field(result, f"case_{idx}", response, "canonical.rule.activation.globs", expected["globs"])
    return result


@binding("TV-RULE-o")
def tv_rule_o(vector: Vector, session: Any, ctx: Any):
    result = result_for(vector)
    for idx, case in enumerate(vector.data["input"]["cases"], start=1):
        config: dict[str, Any] = {"provider": "rule-activation-source", "path": "rule"}
        if case["envelope"] != "content-absent":
            config["content"] = case["content"]
        response = send(result, session, ctx, ingest("rule", provider_config=config))
        assert_error(result, f"case_{idx}", response, vector.data["expect"][f"case_{idx}"]["error"])
    return result
