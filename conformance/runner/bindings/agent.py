from __future__ import annotations
from typing import Any

import yaml

from . import binding
from .common import (
    assert_derived_capability,
    assert_result_field,
    evaluate_requires,
    hash_value,
    ingest,
    output_value,
    project_derived_capabilities,
    provider_config,
    render,
    result_for,
    send,
)
from ..protocol import AdapterResponse
from ..vectors import Vector


def _agent_item(agent: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"agent": {} if agent is None else agent}


def _ingest_agent_files(ctx: Any, files: dict[str, str]) -> dict[str, Any]:
    entry_file = next(iter(files))
    return ingest("agent", body_root=ctx.materialize(files), entry_file=entry_file)


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


@binding("TV-AGENT-a")
def tv_agent_a(vector: Vector, session: Any, ctx: Any):
    result = result_for(vector)
    expected = vector.data["expect"]["conformant"]
    for idx, variant in enumerate(vector.data["input"]["variants"]):
        response = send(result, session, ctx, ingest("agent", sidecar=_agent_item(variant["agent"])))
        assert_result_field(result, f"variants[{idx}]", response, "conformant", expected)
    return result


@binding("TV-AGENT-b")
def tv_agent_b(vector: Vector, session: Any, ctx: Any):
    result = result_for(vector)
    inp = vector.data["input"]
    exp = vector.data["expect"]
    response = send(result, session, ctx, evaluate_requires(inp["item_requires"], inp["consumer_recognizes"]))
    assert_result_field(result, "requires", response, "evaluation", exp["evaluation"])
    assert_result_field(result, "requires", response, "install", exp["install"])
    return result


@binding("TV-AGENT-c")
def tv_agent_c(vector: Vector, session: Any, ctx: Any):
    result = result_for(vector)
    inp = vector.data["input"]
    exp = vector.data["expect"]
    # PROTOCOL.md §3: reason is informative diagnostic text, never asserted.
    response = send(result, session, ctx, ingest("agent", sidecar=_agent_item(inp["on_agent"]["agent"])))
    assert_result_field(result, "on_agent", response, "conformant", exp["on_agent"]["conformant"])
    response = send(result, session, ctx, ingest("rule", sidecar={"rule": inp["on_rule"]["rule"]}))
    assert_result_field(result, "on_rule", response, "conformant", exp["on_rule"]["conformant"])
    return result


@binding("TV-AGENT-d")
def tv_agent_d(vector: Vector, session: Any, ctx: Any):
    result = result_for(vector)
    for idx, case in enumerate(vector.data["input"]["cases"], start=1):
        response = send(result, session, ctx, project_derived_capabilities(_agent_item(case["agent"])))
        # DERIVATION: [ACIF-AGENT] §9.1 (from vector spec) maps tools and
        # disallowed_tools presence to tool_restrictions.
        assert_derived_capability(result, f"case_{idx}", response, "tool_restrictions", vector.data["expect"][f"case_{idx}"])
    return result


@binding("TV-AGENT-e")
def tv_agent_e(vector: Vector, session: Any, ctx: Any):
    result = result_for(vector)
    for idx, case in enumerate(vector.data["input"]["cases"], start=1):
        response = send(result, session, ctx, project_derived_capabilities(_agent_item(case["agent"])))
        # DERIVATION: [ACIF-AGENT] §9.1 (from vector spec) defines
        # model_selection by strict model emptiness.
        assert_derived_capability(result, f"case_{idx}", response, "model_selection", vector.data["expect"][f"case_{idx}"])
    return result


@binding("TV-AGENT-f")
def tv_agent_f(vector: Vector, session: Any, ctx: Any):
    result = result_for(vector)
    for idx, case in enumerate(vector.data["input"]["cases"], start=1):
        response = send(result, session, ctx, project_derived_capabilities(_agent_item(case["agent"])))
        # DERIVATION: [ACIF-AGENT] §9.1 (from vector spec) maps mcp_servers
        # presence to per_agent_mcp.
        assert_derived_capability(result, f"case_{idx}", response, "per_agent_mcp", vector.data["expect"][f"case_{idx}"])
    return result


@binding("TV-AGENT-g")
def tv_agent_g(vector: Vector, session: Any, ctx: Any):
    result = result_for(vector)
    for idx, case in enumerate(vector.data["input"]["cases"], start=1):
        response = send(result, session, ctx, project_derived_capabilities(_agent_item(case["agent"])))
        # DERIVATION: [ACIF-AGENT] §9.1 (from vector spec) pins the
        # canonical agent tool name for subagent_spawning.
        assert_derived_capability(result, f"case_{idx}", response, "subagent_spawning", vector.data["expect"][f"case_{idx}"])
    return result


@binding("TV-AGENT-i")
def tv_agent_i(vector: Vector, session: Any, ctx: Any):
    result = result_for(vector)
    inp = vector.data["input"]
    exp = vector.data["expect"]
    base_files = inp["base"]["files"]
    entry_file = next(iter(base_files))
    base = send(result, session, ctx, _ingest_agent_files(ctx, base_files))
    edit_1_files = _with_frontmatter(base_files, entry_file, inp["edits"][0]["frontmatter"])
    edit_1 = send(result, session, ctx, _ingest_agent_files(ctx, edit_1_files))
    edit_2_files = _with_body(base_files, entry_file, inp["edits"][1]["prose"])
    edit_2 = send(result, session, ctx, _ingest_agent_files(ctx, edit_2_files))
    if _all_ok([base, edit_1, edit_2]):
        result.add_check("edit_1", "metadata_hash_moves", exp["edit_1"]["metadata_hash_moves"], [hash_value(base, "metadata_hash"), hash_value(edit_1, "metadata_hash")], hash_value(base, "metadata_hash") != hash_value(edit_1, "metadata_hash"))
        result.add_check("edit_1", "body_hash_moves", exp["edit_1"]["body_hash_moves"], [hash_value(base, "body_hash"), hash_value(edit_1, "body_hash")], hash_value(base, "body_hash") != hash_value(edit_1, "body_hash"))
        result.add_check("edit_2", "metadata_hash_moves", exp["edit_2"]["metadata_hash_moves"], [hash_value(base, "metadata_hash"), hash_value(edit_2, "metadata_hash")], hash_value(base, "metadata_hash") != hash_value(edit_2, "metadata_hash"))
        result.add_check("edit_2", "body_hash_moves", exp["edit_2"]["body_hash_moves"], [hash_value(base, "body_hash"), hash_value(edit_2, "body_hash")], hash_value(base, "body_hash") != hash_value(edit_2, "body_hash"))
    return result


@binding("TV-AGENT-k")
def tv_agent_k(vector: Vector, session: Any, ctx: Any):
    result = result_for(vector)
    inp = vector.data["input"]
    exp = vector.data["expect"]
    rendered = send(result, session, ctx, render(inp["canonical"], inp["roundtrip_provider"]))
    roundtrip = send(
        result,
        session,
        ctx,
        ingest("agent", provider_config=provider_config(inp["roundtrip_provider"], "agent.rendered", output_value(rendered))),
    )
    assert_result_field(result, "roundtrip", roundtrip, "canonical.agent.tools", exp["roundtrip_tools"])
    assert_result_field(result, "roundtrip", rendered, "lossy", [exp["documented_lossy"]])
    # DERIVATION: [ACIF-CORE] Appendix A.2 (from vector spec) defines the
    # reverse translation preference when write/edit names collapse.
    result.add_check_equivalent(exp["reverse_translation_prefers"])
    return result
