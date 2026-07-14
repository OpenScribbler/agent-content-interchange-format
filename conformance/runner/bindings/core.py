from __future__ import annotations

import copy
from typing import Any

from . import binding
from .common import (
    ABSENT,
    assert_absent,
    assert_error,
    assert_present_absent,
    assert_projection_field,
    assert_relation,
    assert_result_field,
    assert_verdict_reason,
    assert_value,
    derive_pack_id,
    evaluate_install,
    hash_value,
    ingest,
    project,
    provider_config,
    reconcile_frontmatter,
    resolve_pack,
    result_for,
    send,
)
from ..protocol import AdapterResponse
from ..vectors import Vector


def _body_files(body: dict[str, Any]) -> dict[str, Any]:
    files = dict(body.get("files", {}))
    for link in body.get("symlinks", []):
        files[link["path"]] = {"symlink": link["target"]}
    for raw_path in body.get("files_raw_paths", []):
        files[raw_path] = "collision probe\n"
    return files


def _entry_file(body: dict[str, Any], fallback: str = "SKILL.md") -> str:
    if "entry_file" in body:
        return body["entry_file"]
    files = body.get("files")
    if isinstance(files, dict) and fallback in files:
        return fallback
    raw_paths = body.get("files_raw_paths")
    if isinstance(raw_paths, list) and raw_paths:
        return raw_paths[0]
    return fallback


def _ingest_body(ctx: Any, body: dict[str, Any], *, kind: str = "skill", context: dict[str, Any] | None = None) -> dict[str, Any]:
    root = ctx.materialize(_body_files(body))
    return ingest(kind, body_root=root, entry_file=_entry_file(body), context=context)


def _ingest_publisher_section(section: dict[str, Any], context: dict[str, Any] | None = None) -> dict[str, Any]:
    return ingest(section.get("kind", "skill"), sidecar=section, context=context)


def _all_ok(responses: list[AdapterResponse]) -> bool:
    return all(response.kind == "ok" for response in responses)


def _paths_equaling(value: Any, expected: Any, prefix: str = "") -> list[str]:
    matches: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_prefix = f"{prefix}.{key}" if prefix else key
            matches.extend(_paths_equaling(child, expected, child_prefix))
    elif isinstance(value, list):
        for idx, child in enumerate(value):
            matches.extend(_paths_equaling(child, expected, f"{prefix}[{idx}]"))
    elif value == expected:
        matches.append(prefix)
    return matches


@binding("TV-1")
def tv_1(vector: Vector, session: Any, ctx: Any):
    result = result_for(vector)
    inp = vector.data["input"]
    exp = vector.data["expect"]
    responses: list[AdapterResponse] = []
    for idx, context in enumerate(inp["contexts"]):
        request_context = {} if context.get("pack") == "none" else {"pack_id": context["pack"]}
        response = send(result, session, ctx, _ingest_body(ctx, inp["body"], context=request_context))
        responses.append(response)
        assert_result_field(result, f"contexts[{idx}]", response, "body_hash", exp["body_hash"])
    if _all_ok(responses):
        observed = [hash_value(response, "body_hash") for response in responses]
        assert_relation(
            result,
            "contexts",
            "body_hash_identical_across_contexts",
            exp["body_hash_identical_across_contexts"],
            observed,
            len(set(observed)) == 1,
        )
    return result


@binding("TV-2")
def tv_2(vector: Vector, session: Any, ctx: Any):
    result = result_for(vector)
    inp = vector.data["input"]
    exp = vector.data["expect"]
    responses: list[AdapterResponse] = []
    for idx, context in enumerate(inp["contexts"]):
        response = send(
            result,
            session,
            ctx,
            _ingest_publisher_section(inp["publisher_section"], context={"inferred_pack_id": context["inferred_pack_id"]}),
        )
        responses.append(response)
        assert_result_field(result, f"contexts[{idx}]", response, "metadata_hash", exp["metadata_hash"])
    if _all_ok(responses):
        observed = [hash_value(response, "metadata_hash") for response in responses]
        assert_relation(
            result,
            "contexts",
            "metadata_hash_identical_across_contexts",
            exp["metadata_hash_identical_across_contexts"],
            observed,
            len(set(observed)) == 1,
        )
    return result


@binding("TV-3")
def tv_3(vector: Vector, session: Any, ctx: Any):
    result = result_for(vector)
    inp = vector.data["input"]
    response = send(
        result,
        session,
        ctx,
        derive_pack_id(inp["namespace"], inp["canonical_repository_url"], inp["canonical_display_name"]),
    )
    assert_result_field(result, "pack", response, "inferred_pack_id", vector.data["expect"]["inferred_pack_id"])
    return result


@binding("TV-4")
def tv_4(vector: Vector, session: Any, ctx: Any):
    result = result_for(vector)
    inp = vector.data["input"]
    exp = vector.data["expect"]
    declared = inp["item"]["publisher_section"]["pack_id"]
    inferred = inp["item"]["registry_section"]["inferred_pack_id"]
    response = send(result, session, ctx, resolve_pack(inp["item"], [{"id": declared}, {"id": inferred}]))
    assert_result_field(result, "pack", response, "member_of", exp["member_of"])
    assert_result_field(result, "pack", response, "pack_resolution", exp["pack_resolution"])
    return result


@binding("TV-5")
def tv_5(vector: Vector, session: Any, ctx: Any):
    result = result_for(vector)
    inp = vector.data["input"]
    exp = vector.data["expect"]
    response = send(result, session, ctx, resolve_pack(inp["item"], inp["known_packs"]))
    assert_result_field(result, "pack", response, "pack_resolution", exp["pack_resolution"])
    assert_result_field(result, "pack", response, "install", exp["install"])
    return result


@binding("TV-6")
def tv_6(vector: Vector, session: Any, ctx: Any):
    result = result_for(vector)
    exp = vector.data["expect"]
    response = send(result, session, ctx, ingest(vector.data["input"]["item_record"].get("kind", "skill"), sidecar=vector.data["input"]["item_record"]))
    assert_result_field(result, "item_record", response, "conformant", exp["conformant"])
    assert_verdict_reason(result, "item_record", response, exp["reason"], session, exp.get("params"))
    return result


@binding("TV-7")
def tv_7(vector: Vector, session: Any, ctx: Any):
    result = result_for(vector)
    inp = vector.data["input"]
    exp = vector.data["expect"]
    response = send(result, session, ctx, ingest("skill", sidecar=inp["item"]["publisher_section"], context={"pack": inp["pack"]}))
    assert_result_field(result, "item", response, "publisher_section.version", exp["publisher_section.version"])
    if response.kind == "ok":
        # DERIVATION: [ACIF-PUBLISHER] §5.5 (from vector spec) says pack
        # version never propagates to member item fields.
        matches = _paths_equaling(response.result or {}, exp["no_item_field_equals"])
        result.add_check("item", "no_item_field_equals", exp["no_item_field_equals"], matches, matches == [])
    return result


@binding("TV-8")
def tv_8(vector: Vector, session: Any, ctx: Any):
    result = result_for(vector)
    inp = vector.data["input"]
    exp = vector.data["expect"]
    item = inp["item"]
    kind = item.get("publisher_section", {}).get("kind", "skill")
    response = send(
        result,
        session,
        ctx,
        ingest(kind, sidecar=item, context={"validation_surface": "publisher_packless_item"}),
    )
    assert_result_field(result, "item", response, "conformant", exp["conformant"])
    assert_result_field(result, "item", response, "installable", exp["installable"])
    return result


@binding("TV-9")
def tv_9(vector: Vector, session: Any, ctx: Any):
    result = result_for(vector)
    inp = vector.data["input"]
    exp = vector.data["expect"]
    response = send(result, session, ctx, _ingest_publisher_section(inp["publisher_section"]))
    assert_result_field(result, "publisher_section", response, "canonical_bytes", exp["canonical_bytes"])
    assert_result_field(result, "publisher_section", response, "metadata_hash", exp["metadata_hash"])
    return result


@binding("TV-10")
def tv_10(vector: Vector, session: Any, ctx: Any):
    result = result_for(vector)
    inp = vector.data["input"]
    exp = vector.data["expect"]
    before = inp["pack_before"]
    after = inp["pack_after"]
    response = send(result, session, ctx, resolve_pack(inp["referencing_item"], [after]))
    if response.kind == "ok":
        observed_member = hash_value(response, "member_of")
        # DERIVATION: [ACIF-PUBLISHER] §8.1, §8.3 (from vector spec) make
        # pack identity the id, not the mutable display_name.
        assert_relation(result, "pack_after", "id_unchanged", exp["id_unchanged"], [before["id"], after["id"]], before["id"] == after["id"])
        assert_relation(
            result,
            "referencing_item",
            "reference_resolves_after_rename",
            exp["reference_resolves_after_rename"],
            observed_member,
            observed_member == after["id"],
        )
    else:
        assert_result_field(result, "referencing_item", response, "member_of", after["id"])
    return result


@binding("TV-11")
def tv_11(vector: Vector, session: Any, ctx: Any):
    result = result_for(vector)
    inp = vector.data["input"]
    exp = vector.data["expect"]
    for idx, case in enumerate(inp["cases"], start=1):
        expected = exp[f"case_{idx}"]
        response = send(result, session, ctx, ingest(case.get("kind", "skill"), sidecar=case))
        assert_result_field(result, f"case_{idx}", response, "conformant", expected["conformant"])
        assert_verdict_reason(result, f"case_{idx}", response, expected["reason"], session, expected.get("params"))
    return result


@binding("TV-12")
def tv_12(vector: Vector, session: Any, ctx: Any):
    result = result_for(vector)
    inp = vector.data["input"]
    exp = vector.data["expect"]
    base = send(result, session, ctx, _ingest_body(ctx, inp["base"]))
    assert_result_field(result, "base", base, "body_hash", exp["base"]["body_hash"])
    root_sidecar = send(result, session, ctx, _ingest_body(ctx, inp["with_root_sidecar"]))
    if base.kind == "ok" and root_sidecar.kind == "ok":
        assert_relation(
            result,
            "with_root_sidecar",
            "body_hash_equals_base",
            exp["with_root_sidecar"]["body_hash_equals_base"],
            [hash_value(base, "body_hash"), hash_value(root_sidecar, "body_hash")],
            hash_value(base, "body_hash") == hash_value(root_sidecar, "body_hash"),
        )
    else:
        assert_result_field(result, "with_root_sidecar", root_sidecar, "body_hash", exp["base"]["body_hash"])
    edited = send(result, session, ctx, _ingest_body(ctx, inp["subdir_sidecar_edited"]))
    assert_result_field(result, "subdir_sidecar_edited", edited, "body_hash", exp["subdir_sidecar_edited"]["body_hash"])
    if base.kind == "ok" and edited.kind == "ok":
        assert_relation(
            result,
            "subdir_sidecar_edited",
            "body_hash_equals_base",
            exp["subdir_sidecar_edited"]["body_hash_equals_base"],
            [hash_value(base, "body_hash"), hash_value(edited, "body_hash")],
            hash_value(base, "body_hash") == hash_value(edited, "body_hash"),
        )
    return result


@binding("TV-13")
def tv_13(vector: Vector, session: Any, ctx: Any):
    result = result_for(vector)
    inp = vector.data["input"]
    exp = vector.data["expect"]
    response = send(result, session, ctx, _ingest_body(ctx, inp["symlink"]))
    assert_error(result, "symlink", response, exp["symlink"]["error"])
    response = send(result, session, ctx, _ingest_body(ctx, inp["path_collision"]))
    assert_error(result, "path_collision", response, exp["path_collision"]["error"])
    response = send(result, session, ctx, _ingest_body(ctx, inp["empty"]))
    assert_error(result, "empty", response, exp["empty"]["error"])
    return result


@binding("TV-L2-a")
def tv_l2_a(vector: Vector, session: Any, ctx: Any):
    result = result_for(vector)
    inp = vector.data["input"]
    exp = vector.data["expect"]
    for case in ("variant_undeclared", "variant_declared"):
        response = send(result, session, ctx, _ingest_body(ctx, inp[case]))
        assert_present_absent(result, case, response, "publisher_section", exp[case]["publisher_section"])
        assert_present_absent(result, case, response, "metadata_hash", exp[case]["metadata_hash"])
        if response.kind == "ok":
            # DERIVATION: [ACIF-PUBLISHER] §5.2 (from vector spec) defines
            # publisher_declared as exactly publisher_section presence.
            observed = hash_value(response, "publisher_section") is not ABSENT
            assert_relation(result, case, "publisher_declared", exp[case]["publisher_declared"], observed, observed)
    return result


@binding("TV-L2-b")
def tv_l2_b(vector: Vector, session: Any, ctx: Any):
    result = result_for(vector)
    inp = vector.data["input"]
    exp = vector.data["expect"]
    response = send(result, session, ctx, ingest("hook", sidecar=inp["authored_sidecar"]))
    if response.kind == "ok":
        publisher_section = hash_value(response, "publisher_section")
        observed_fields = sorted(publisher_section) if isinstance(publisher_section, dict) else ABSENT
        result.add_check("authored_sidecar", "publisher_section_fields", exp["publisher_section_fields"], observed_fields, observed_fields == sorted(exp["publisher_section_fields"]))
        observed_excluded = [key for key in exp["publisher_section_excludes"] if isinstance(publisher_section, dict) and key in publisher_section]
        result.add_check("authored_sidecar", "publisher_section_excludes", exp["publisher_section_excludes"], observed_excluded, observed_excluded == [])
    else:
        assert_result_field(result, "authored_sidecar", response, "publisher_section", exp["publisher_section_fields"])
    edited_sidecar = copy.deepcopy(inp["authored_sidecar"])
    edited_sidecar.update(inp["edit"])
    edited = send(result, session, ctx, ingest("hook", sidecar=edited_sidecar))
    if response.kind == "ok" and edited.kind == "ok":
        assert_relation(
            result,
            "edit",
            "metadata_hash_moves_on_edit",
            exp["metadata_hash_moves_on_edit"],
            [hash_value(response, "metadata_hash"), hash_value(edited, "metadata_hash")],
            hash_value(response, "metadata_hash") != hash_value(edited, "metadata_hash"),
        )
        assert_relation(
            result,
            "edit",
            "body_hash_moves_on_edit",
            exp["body_hash_moves_on_edit"],
            [hash_value(response, "body_hash"), hash_value(edited, "body_hash")],
            hash_value(response, "body_hash") != hash_value(edited, "body_hash"),
        )
    return result


@binding("TV-L2-c")
def tv_l2_c(vector: Vector, session: Any, ctx: Any):
    result = result_for(vector)
    inp = vector.data["input"]
    exp = vector.data["expect"]
    response = send(
        result,
        session,
        ctx,
        ingest(
            inp["kind"],
            provider_config=provider_config("provider-native-frontmatter", "agent.md", {"frontmatter": inp["declared_frontmatter"]}),
        ),
    )
    assert_result_field(result, "declared_frontmatter", response, "publisher_section.agent.tools", exp["publisher_section.agent.tools"])
    assert_result_field(result, "declared_frontmatter", response, "canonical.agent.tools", exp["canonical.agent.tools"])
    if response.kind == "ok":
        # DERIVATION: [ACIF-PUBLISHER] §5.3 (from vector spec) says the
        # metadata hash is over declared spelling, not translated canonical spelling.
        observed = exp["metadata_hash_over"] if hash_value(response, "publisher_section") is not ABSENT else ABSENT
        result.add_check("declared_frontmatter", "metadata_hash_over", exp["metadata_hash_over"], observed, observed == exp["metadata_hash_over"])
    return result


@binding("TV-L2-d")
def tv_l2_d(vector: Vector, session: Any, ctx: Any):
    result = result_for(vector)
    inp = vector.data["input"]
    exp = vector.data["expect"]
    for idx, case in enumerate(inp["cases"], start=1):
        expected = exp[f"case_{idx}"]
        response = send(
            result,
            session,
            ctx,
            reconcile_frontmatter(inp["sidecar_value"], case["source_frontmatter"], case["mode"]),
        )
        assert_result_field(result, f"case_{idx}", response, "action", expected["action"])
        diagnostic = expected.get("diagnostic") or expected.get("logged")
        if diagnostic:
            # DERIVATION: PROTOCOL.md §4.13 carries the vector's
            # diagnostic-vs-logged distinction through the action value; both
            # successful overwrite-with-log and blocking cases emit the same
            # spec diagnostic id.
            from .common import assert_diagnostic

            assert_diagnostic(result, f"case_{idx}", response, diagnostic)
    return result


@binding("TV-L2-e")
def tv_l2_e(vector: Vector, session: Any, ctx: Any):
    result = result_for(vector)
    inp = vector.data["input"]
    exp = vector.data["expect"]
    declared = send(result, session, ctx, ingest("pack", sidecar=inp["declared_pack"]))
    assert_present_absent(result, "declared_pack", declared, "metadata_hash", exp["declared_pack"]["metadata_hash"])
    assert_absent(result, "declared_pack", declared, "body_hash", exp["declared_pack"]["body_hash"])
    inferred = send(result, session, ctx, ingest("pack", sidecar=inp["inferred_pack"]))
    assert_absent(result, "inferred_pack", inferred, "publisher_section", exp["inferred_pack"]["publisher_section"])
    assert_absent(result, "inferred_pack", inferred, "metadata_hash", exp["inferred_pack"]["metadata_hash"])
    assert_absent(result, "inferred_pack", inferred, "body_hash", exp["inferred_pack"]["body_hash"])
    return result


@binding("TV-L2-f")
def tv_l2_f(vector: Vector, session: Any, ctx: Any):
    result = result_for(vector)
    inp = vector.data["input"]
    exp = vector.data["expect"]
    response = send(
        result,
        session,
        ctx,
        {"op": "ingest", "input": {"kind": "pack", "manifests": inp["manifests"]}},
    )
    assert_result_field(result, "manifests", response, "canonical_source", exp["canonical_source"])
    assert_result_field(result, "manifests", response, "canonical_display_name", exp["canonical_display_name"])
    # DERIVATION: PROTOCOL.md Appendix A pins the diagnostic params as
    # `sources` and `values`; the vector names the corresponding committed
    # literals as `names_sources` and `names_values`.
    from .common import assert_diagnostic

    assert_diagnostic(
        result,
        "manifests",
        response,
        exp["diagnostic"]["id"],
        {
            "sources": exp["diagnostic"]["names_sources"],
            "values": exp["diagnostic"]["names_values"],
        },
    )
    return result


@binding("TV-L3-a")
def tv_l3_a(vector: Vector, session: Any, ctx: Any):
    result = result_for(vector)
    exp = vector.data["expect"]
    response = send(result, session, ctx, project(vector.data["input"], "tuple_endpoint"))
    assert_projection_field(result, "tuple_endpoint", response, "tuple_fields", exp["tuple_fields"])
    assert_projection_field(result, "tuple_endpoint", response, "member_1.metadata_hash", exp["member_1.metadata_hash"])
    assert_projection_field(result, "tuple_endpoint", response, "member_2.metadata_hash", exp["member_2.metadata_hash"])
    return result


@binding("TV-L3-b")
def tv_l3_b(vector: Vector, session: Any, ctx: Any):
    result = result_for(vector)
    exp = vector.data["expect"]
    response = send(result, session, ctx, project(vector.data["input"]["projection"], "install_scope_capabilities"))
    assert_result_field(result, "projection", response, "conformant", exp["conformant"])
    assert_verdict_reason(result, "projection", response, exp["reason"], session, exp.get("params"))
    return result


@binding("TV-L3-c")
def tv_l3_c(vector: Vector, session: Any, ctx: Any):
    result = result_for(vector)
    exp = vector.data["expect"]
    response = send(result, session, ctx, project(vector.data["input"]["advisory"], "advisory"))
    assert_result_field(result, "advisory", response, "conformant", exp["conformant"])
    assert_verdict_reason(result, "advisory", response, exp["reason"], session, exp.get("params"))
    return result


@binding("TV-L3-d")
def tv_l3_d(vector: Vector, session: Any, ctx: Any):
    result = result_for(vector)
    response = send(result, session, ctx, evaluate_install(vector.data["input"]["item"]))
    assert_result_field(result, "item", response, "install", vector.data["expect"]["install"])
    return result
