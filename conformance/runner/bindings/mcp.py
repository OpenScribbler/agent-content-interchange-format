from __future__ import annotations

import copy
from typing import Any

from . import binding
from .common import (
    ABSENT,
    assert_derived_capability,
    assert_diagnostic,
    assert_error,
    assert_ok,
    assert_result_field,
    assert_value,
    evaluate_requires,
    field,
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


def _mcp_item(mcp: dict[str, Any]) -> dict[str, Any]:
    return {"mcp": mcp}


def _transport_type(response: AdapterResponse, server: str = "demo") -> Any:
    canonical = hash_value(response, "canonical")
    observed = field(canonical, f"mcp.servers.{server}.type")
    if observed is ABSENT:
        observed = field(canonical, f"servers.{server}.type")
    return observed


def _set_edit(base: dict[str, Any], edit: dict[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(base)
    path = edit["path"]
    if path == "servers.demo.args[1]":
        out["mcp"]["servers"]["demo"]["args"][1] = edit["value"]
    elif path == "servers.demo.env.MODE":
        out["mcp"]["servers"]["demo"]["env"]["MODE"] = edit["value"]
    elif path == "servers.remote.url":
        out["mcp"]["servers"]["remote"]["url"] = edit["value"]
    else:
        raise ValueError(f"unhandled MCP edit path {path!r}")
    return out


def _all_ok(responses: list[AdapterResponse]) -> bool:
    return all(response.kind == "ok" for response in responses)


@binding("TV-MCP-a")
def tv_mcp_a(vector: Vector, session: Any, ctx: Any):
    result = result_for(vector)
    inp = vector.data["input"]
    exp = vector.data["expect"]
    stdio = send(result, session, ctx, ingest("mcp_config", sidecar=inp["source_stdio"]["mcp"]))
    assert_value(result, "source_stdio", "canonical_stdio.servers.demo.type", exp["canonical_stdio.servers.demo.type"], _transport_type(stdio), stdio)
    assert_result_field(result, "source_stdio", stdio, "body_hash", exp["body_hash_stdio"])
    http = send(result, session, ctx, ingest("mcp_config", sidecar=inp["source_http"]["mcp"]))
    assert_value(result, "source_http", "canonical_http.servers.demo.type", exp["canonical_http.servers.demo.type"], _transport_type(http), http)
    assert_result_field(result, "source_http", http, "body_hash", exp["body_hash_http"])
    return result


@binding("TV-MCP-b")
def tv_mcp_b(vector: Vector, session: Any, ctx: Any):
    result = result_for(vector)
    response = send(result, session, ctx, ingest("mcp_config", sidecar=vector.data["input"]["mcp"]))
    assert_error(result, "mcp", response, vector.data["expect"]["error"])
    return result


@binding("TV-MCP-c")
def tv_mcp_c(vector: Vector, session: Any, ctx: Any):
    result = result_for(vector)
    response = send(result, session, ctx, ingest("mcp_config", sidecar=vector.data["input"]["mcp"]))
    assert_error(result, "mcp", response, vector.data["expect"]["error"])
    return result


@binding("TV-MCP-d")
def tv_mcp_d(vector: Vector, session: Any, ctx: Any):
    result = result_for(vector)
    inp = vector.data["input"]
    exp = vector.data["expect"]
    responses = []
    for case in ("variant_explicit", "variant_defaulted"):
        response = send(result, session, ctx, ingest("mcp_config", sidecar=inp[case]["mcp"]))
        responses.append(response)
        assert_result_field(result, case, response, "body_hash", exp["body_hash"])
    if _all_ok(responses):
        result.add_check("variants", "canonical_bytes_identical", exp["canonical_bytes_identical"], [hash_value(r, "canonical_bytes") for r in responses], hash_value(responses[0], "canonical_bytes") == hash_value(responses[1], "canonical_bytes"))
        result.add_check("variants", "body_hash_identical", exp["body_hash_identical"], [hash_value(r, "body_hash") for r in responses], hash_value(responses[0], "body_hash") == hash_value(responses[1], "body_hash"))
    return result


@binding("TV-MCP-e")
def tv_mcp_e(vector: Vector, session: Any, ctx: Any):
    result = result_for(vector)
    expected = vector.data["expect"]["conformant"]
    for idx, variant in enumerate(vector.data["input"]["variants"]):
        response = send(result, session, ctx, ingest("mcp_config", sidecar=variant["mcp"]))
        assert_result_field(result, f"variants[{idx}]", response, "conformant", expected)
    return result


@binding("TV-MCP-f")
def tv_mcp_f(vector: Vector, session: Any, ctx: Any):
    result = result_for(vector)
    inp = vector.data["input"]
    exp = vector.data["expect"]
    response = send(result, session, ctx, evaluate_requires(inp["item_requires"], inp["consumer_recognizes"]))
    assert_result_field(result, "requires", response, "evaluation", exp["evaluation"])
    assert_result_field(result, "requires", response, "install", exp["install"])
    return result


@binding("TV-MCP-g")
def tv_mcp_g(vector: Vector, session: Any, ctx: Any):
    result = result_for(vector)
    inp = vector.data["input"]
    exp = vector.data["expect"]
    # PROTOCOL.md §3: reason is informative diagnostic text, never asserted.
    mcp = {"servers": {"demo": {"type": "stdio", "command": "npx"}}, "requires": inp["on_mcp_item"]["requires"]}
    response = send(result, session, ctx, ingest("mcp_config", sidecar=mcp))
    assert_result_field(result, "on_mcp_item", response, "conformant", exp["on_mcp_item"]["conformant"])
    response = send(result, session, ctx, ingest("skill", sidecar={"skill": {"requires": inp["on_skill_item"]["requires"]}}))
    assert_result_field(result, "on_skill_item", response, "conformant", exp["on_skill_item"]["conformant"])
    return result


@binding("TV-MCP-h")
def tv_mcp_h(vector: Vector, session: Any, ctx: Any):
    result = result_for(vector)
    for idx, variant in enumerate(vector.data["input"]["variants"], start=1):
        response = send(result, session, ctx, ingest("mcp_config", sidecar=variant["mcp"]))
        assert_error(result, f"variant_{idx}", response, vector.data["expect"]["error"])
    return result


@binding("TV-MCP-i")
def tv_mcp_i(vector: Vector, session: Any, ctx: Any):
    result = result_for(vector)
    for idx, variant in enumerate(vector.data["input"]["variants"], start=1):
        response = send(result, session, ctx, ingest("mcp_config", sidecar=variant["mcp"]))
        assert_error(result, f"variant_{idx}", response, vector.data["expect"]["error"])
    return result


@binding("TV-MCP-j")
def tv_mcp_j(vector: Vector, session: Any, ctx: Any):
    result = result_for(vector)
    inp = vector.data["input"]
    exp = vector.data["expect"]
    for case in ("rich", "bare"):
        response = send(result, session, ctx, project_derived_capabilities(_mcp_item(inp[case]["mcp"])))
        for key, expected in exp[case].items():
            # DERIVATION: [ACIF-MCP] §9.1 (from vector spec) maps canonical
            # server fields to each MCP D_K boolean.
            assert_derived_capability(result, case, response, key, expected)
    return result


@binding("TV-MCP-k")
def tv_mcp_k(vector: Vector, session: Any, ctx: Any):
    result = result_for(vector)
    inp = vector.data["input"]
    exp = vector.data["expect"]
    base = send(result, session, ctx, ingest("mcp_config", sidecar=inp["base"]["mcp"]))
    edits = [send(result, session, ctx, ingest("mcp_config", sidecar=_set_edit(inp["base"], edit)["mcp"])) for edit in inp["edits"]]
    if _all_ok([base, *edits]):
        observed = [hash_value(base, "body_hash"), *[hash_value(edit, "body_hash") for edit in edits]]
        result.add_check(
            "edits",
            "each_edit_moves_body_hash",
            exp["each_edit_moves_body_hash"],
            observed,
            all(hash_value(base, "body_hash") != hash_value(edit, "body_hash") for edit in edits),
        )
    return result


@binding("TV-MCP-k2")
def tv_mcp_k2(vector: Vector, session: Any, ctx: Any):
    result = result_for(vector)
    inp = vector.data["input"]
    exp = vector.data["expect"]
    responses = []
    for case in ("variant_a", "variant_b"):
        responses.append(send(result, session, ctx, ingest("mcp_config", sidecar=inp[case]["mcp"])))
    if _all_ok(responses):
        result.add_check("variants", "canonical_bytes_identical", exp["canonical_bytes_identical"], [hash_value(r, "canonical_bytes") for r in responses], hash_value(responses[0], "canonical_bytes") == hash_value(responses[1], "canonical_bytes"))
        result.add_check("variants", "body_hash_identical", exp["body_hash_identical"], [hash_value(r, "body_hash") for r in responses], hash_value(responses[0], "body_hash") == hash_value(responses[1], "body_hash"))
    return result


@binding("TV-MCP-l")
def tv_mcp_l(vector: Vector, session: Any, ctx: Any):
    result = result_for(vector)
    inp = vector.data["input"]
    exp = vector.data["expect"]
    canonical = inp["canonical"]
    before = send(result, session, ctx, ingest("mcp_config", sidecar=canonical["mcp"]))
    rendered = send(result, session, ctx, render(canonical, inp["render_target"]))
    roundtrip = send(result, session, ctx, ingest("mcp_config", provider_config=provider_config(inp["render_target"], "mcp.rendered", output_value(rendered))))
    if _all_ok([before, rendered, roundtrip]):
        result.add_check("roundtrip", "roundtrip_canonical_bytes_identical", exp["roundtrip_canonical_bytes_identical"], [hash_value(before, "canonical_bytes"), hash_value(roundtrip, "canonical_bytes")], hash_value(before, "canonical_bytes") == hash_value(roundtrip, "canonical_bytes"))
        result.add_check("roundtrip", "roundtrip_body_hash_identical", exp["roundtrip_body_hash_identical"], [hash_value(before, "body_hash"), hash_value(roundtrip, "body_hash")], hash_value(before, "body_hash") == hash_value(roundtrip, "body_hash"))
    return result


@binding("TV-MCP-m")
def tv_mcp_m(vector: Vector, session: Any, ctx: Any):
    result = result_for(vector)
    exp = vector.data["expect"]
    response = send(result, session, ctx, ingest("mcp_config", sidecar=vector.data["input"]["mcp"]))
    assert_ok(result, "mcp", response, "accept", exp["accept"])
    assert_diagnostic(result, "mcp", response, exp["diagnostic"])
    return result
