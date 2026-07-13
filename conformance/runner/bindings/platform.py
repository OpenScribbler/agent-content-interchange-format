from __future__ import annotations

import copy
import json
from typing import Any

import yaml

from . import binding
from .common import (
    ABSENT,
    assert_diagnostic,
    assert_error,
    assert_ok,
    assert_output_contains,
    assert_output_excludes,
    assert_relation,
    assert_result_field,
    assert_value,
    evaluate_install,
    hash_value,
    ingest,
    output_value,
    project,
    project_script_selection,
    provider_config,
    render,
    result_for,
    send,
)
from ..protocol import AdapterResponse
from ..vectors import Vector


def _hook(scripts: list[dict[str, Any]], *, blocking: bool = False) -> dict[str, Any]:
    return {
        "event": "before_tool_execute",
        "handlers": [{"type": "command", "scripts": scripts}],
        "blocking": blocking,
    }


def _canonical_hook(scripts: list[dict[str, Any]], *, blocking: bool = False) -> dict[str, Any]:
    return {"hook": _hook(scripts, blocking=blocking)}


def _default_file_content(path: str) -> str:
    if path.endswith((".cmd", ".bat")):
        return "@echo off\r\necho ok\r\n"
    if path.endswith(".ps1") or "pwsh" in path:
        return "#!/usr/bin/env pwsh\nWrite-Output ok\n"
    return "#!/bin/sh\necho ok\n"


def _files_for_scripts(scripts: list[dict[str, Any]], referenced_files: dict[str, Any] | None = None) -> dict[str, Any]:
    files = dict(referenced_files or {})
    for script in scripts:
        if script.get("type") == "file" and script.get("path") not in files:
            files[script["path"]] = _default_file_content(script["path"])
    return files


def _ingest_scripts(ctx: Any, scripts: list[dict[str, Any]], *, referenced_files: dict[str, Any] | None = None, blocking: bool = False) -> dict[str, Any]:
    root = ctx.materialize(_files_for_scripts(scripts, referenced_files))
    return ingest("hook", sidecar=_hook(scripts, blocking=blocking), body_root=root)


def _ingest_provider(
    ctx: Any,
    provider: str,
    content: Any,
    *,
    files: dict[str, Any] | None = None,
) -> dict[str, Any]:
    root = ctx.materialize(files or {})
    return ingest("hook", body_root=root, provider_config=provider_config(provider, "hooks.json", content))


def _hook_block(response: AdapterResponse) -> Any:
    canonical = hash_value(response, "canonical")
    if isinstance(canonical, dict) and isinstance(canonical.get("hook"), dict):
        return canonical["hook"]
    return canonical


def _scripts(response: AdapterResponse) -> Any:
    block = _hook_block(response)
    handlers = block.get("handlers") if isinstance(block, dict) else None
    if isinstance(handlers, list) and handlers and isinstance(handlers[0], dict):
        return handlers[0].get("scripts", ABSENT)
    return ABSENT


def _first_script(response: AdapterResponse) -> Any:
    scripts = _scripts(response)
    if isinstance(scripts, list) and scripts:
        return scripts[0]
    return ABSENT


def _all_ok(responses: list[AdapterResponse]) -> bool:
    return all(response.kind == "ok" for response in responses)


def _parse_structured_output(output: Any) -> Any:
    if not isinstance(output, str):
        return ABSENT
    for parser in (json.loads, yaml.safe_load):
        try:
            return parser(output)
        except Exception:
            pass
    return ABSENT


def _structured_value_only(value: Any, expected: str) -> tuple[bool, list[str]]:
    exact_paths: list[str] = []
    spliced_paths: list[str] = []

    def walk(node: Any, path: str) -> None:
        if isinstance(node, dict):
            for key, child in node.items():
                walk(child, f"{path}.{key}" if path else str(key))
        elif isinstance(node, list):
            for idx, child in enumerate(node):
                walk(child, f"{path}[{idx}]")
        elif isinstance(node, str):
            if node == expected:
                exact_paths.append(path)
            elif expected in node:
                spliced_paths.append(path)

    walk(value, "")
    return bool(exact_paths) and not spliced_paths, exact_paths + spliced_paths


@binding("TV-PLATFORM-a")
def tv_platform_a(vector: Vector, session: Any, ctx: Any):
    result = result_for(vector)
    inp = vector.data["input"]
    response = send(result, session, ctx, project_script_selection(_canonical_hook(inp["scripts"]), inp["targets"]))
    assert_result_field(result, "scripts", response, "selection", vector.data["expect"]["selection"])
    return result


@binding("TV-PLATFORM-b")
def tv_platform_b(vector: Vector, session: Any, ctx: Any):
    result = result_for(vector)
    inp = vector.data["input"]
    response = send(result, session, ctx, project_script_selection(_canonical_hook(inp["scripts"]), inp["targets"]))
    assert_result_field(result, "scripts", response, "selection", vector.data["expect"]["selection"])
    return result


@binding("TV-PLATFORM-c")
def tv_platform_c(vector: Vector, session: Any, ctx: Any):
    result = result_for(vector)
    inp = vector.data["input"]
    exp = vector.data["expect"]
    for idx, variant in enumerate(inp["variants"], start=1):
        response = send(result, session, ctx, _ingest_scripts(ctx, variant["scripts"]))
        assert_error(result, f"variant_{idx}", response, exp[f"variant_{idx}"]["error"])
    return result


@binding("TV-PLATFORM-d")
def tv_platform_d(vector: Vector, session: Any, ctx: Any):
    result = result_for(vector)
    for idx, variant in enumerate(vector.data["input"]["variants"], start=1):
        response = send(result, session, ctx, _ingest_scripts(ctx, variant["scripts"]))
        assert_error(result, f"variant_{idx}", response, vector.data["expect"]["error"])
    return result


@binding("TV-PLATFORM-e")
def tv_platform_e(vector: Vector, session: Any, ctx: Any):
    result = result_for(vector)
    response = send(result, session, ctx, _ingest_scripts(ctx, vector.data["input"]["scripts"]))
    assert_error(result, "scripts", response, vector.data["expect"]["error"])
    return result


@binding("TV-PLATFORM-f")
def tv_platform_f(vector: Vector, session: Any, ctx: Any):
    result = result_for(vector)
    exp = vector.data["expect"]
    response = send(result, session, ctx, _ingest_scripts(ctx, vector.data["input"]["scripts"]))
    assert_error(result, "scripts", response, exp["error"])
    assert_diagnostic(result, "scripts", response, exp["error"], exp["diagnostic_names"])
    return result


@binding("TV-PLATFORM-g")
def tv_platform_g(vector: Vector, session: Any, ctx: Any):
    result = result_for(vector)
    response = send(result, session, ctx, _ingest_scripts(ctx, vector.data["input"]["scripts"]))
    assert_ok(result, "scripts", response, "accept", vector.data["expect"]["accept"])
    return result


@binding("TV-PLATFORM-g2")
def tv_platform_g2(vector: Vector, session: Any, ctx: Any):
    result = result_for(vector)
    inp = vector.data["input"]
    exp = vector.data["expect"]
    response = send(result, session, ctx, _ingest_scripts(ctx, inp["scripts"]))
    assert_ok(result, "scripts", response, "accept", exp["accept"])
    projection_response = send(result, session, ctx, project(_canonical_hook(inp["scripts"]), "os_coverage"))
    assert_result_field(result, "scripts", projection_response, "projection.os_divergent", exp["os_divergent"])
    return result


@binding("TV-PLATFORM-h")
def tv_platform_h(vector: Vector, session: Any, ctx: Any):
    result = result_for(vector)
    inp = vector.data["input"]
    exp = vector.data["expect"]
    response = send(result, session, ctx, project_script_selection(_canonical_hook(inp["scripts"]), inp["targets"]))
    assert_result_field(result, "scripts", response, "selection", exp["selection"])
    assert_diagnostic(result, "scripts", response, exp["diagnostic"])
    return result


@binding("TV-PLATFORM-i")
def tv_platform_i(vector: Vector, session: Any, ctx: Any):
    result = result_for(vector)
    inp = vector.data["input"]
    exp = vector.data["expect"]
    response = send(
        result,
        session,
        ctx,
        _ingest_provider(ctx, inp["source_mechanism"], inp["source"], files=inp["referenced_files"]),
    )
    assert_value(result, "source", "canonical_scripts", exp["canonical_scripts"], _scripts(response), response)
    assert_result_field(result, "source", response, "provenance", exp["provenance"])
    assert_result_field(result, "source", response, "body_hash", exp["body_hash"])
    return result


@binding("TV-PLATFORM-j")
def tv_platform_j(vector: Vector, session: Any, ctx: Any):
    result = result_for(vector)
    exp = vector.data["expect"]
    source = vector.data["input"]["source"]
    files = {path: _default_file_content(path) for path in source.values()}
    response = send(result, session, ctx, _ingest_provider(ctx, "per-os-key-map", source, files=files))
    scripts = _scripts(response)
    observed_values = []
    if isinstance(scripts, list):
        for script in scripts:
            if isinstance(script, dict) and isinstance(script.get("os"), list):
                observed_values.extend(script["os"])
    assert_value(result, "source", "canonical_contains_os_value", exp["canonical_contains_os_value"], exp["canonical_contains_os_value"] if exp["canonical_contains_os_value"] in observed_values else observed_values, response)
    result.add_check(
        "source",
        "canonical_never_contains",
        exp["canonical_never_contains"],
        observed_values,
        exp["canonical_never_contains"] not in observed_values,
    )
    return result


@binding("TV-PLATFORM-k")
def tv_platform_k(vector: Vector, session: Any, ctx: Any):
    result = result_for(vector)
    inp = vector.data["input"]
    exp = vector.data["expect"]
    files = {path: _default_file_content(path) for path in inp["source"].values()}
    response = send(
        result,
        session,
        ctx,
        _ingest_provider(ctx, inp["source_mechanism"], inp["source"], files=files),
    )
    assert_value(result, "source", "canonical_scripts", exp["canonical_scripts"], _scripts(response), response)
    assert_diagnostic(result, "source", response, exp["diagnostic"])
    assert_result_field(result, "source", response, "provenance", exp["provenance"])
    return result


@binding("TV-PLATFORM-l")
def tv_platform_l(vector: Vector, session: Any, ctx: Any):
    result = result_for(vector)
    inp = vector.data["input"]
    exp = vector.data["expect"]
    for idx, case in enumerate(inp["cases"], start=1):
        file = case["file"]
        content = _default_file_content(file)
        response = send(result, session, ctx, _ingest_provider(ctx, "filename-extension-convention", case, files={file: content}))
        expected = exp[f"case_{idx}"]
        first_script = _first_script(response)
        observed_os = first_script.get("os", ABSENT) if isinstance(first_script, dict) else ABSENT
        assert_value(result, f"case_{idx}", "os", expected["os"], observed_os, response)
        if "diagnostic" in expected:
            assert_diagnostic(result, f"case_{idx}", response, expected["diagnostic"])
        if "note" in expected:
            # DERIVATION: [ACIF-HOOK] §7.4 (from vector spec) marks this
            # case as an informative disclosed false mapping, not a wire field.
            result.add_check_equivalent(expected["note"])
    if "provenance" in exp:
        result.add_check_equivalent(exp["provenance"])
    return result


@binding("TV-PLATFORM-m")
def tv_platform_m(vector: Vector, session: Any, ctx: Any):
    result = result_for(vector)
    inp = vector.data["input"]
    exp = vector.data["expect"]
    response = send(
        result,
        session,
        ctx,
        _ingest_provider(ctx, "per-os-key-map", inp["source"], files={"hooks/run": _default_file_content("hooks/run")}),
    )
    scripts = _scripts(response)
    comparable_scripts = scripts
    if isinstance(scripts, list):
        comparable_scripts = [
            {key: script[key] for key in ("type", "path", "os", "arch") if isinstance(script, dict) and key in script}
            for script in scripts
        ]
    assert_value(result, "source", "canonical_scripts", exp["canonical_scripts"], comparable_scripts, response)
    if response.kind == "ok":
        observed_no_os = isinstance(scripts, list) and all(
            not (isinstance(script, dict) and "os" in script) for script in scripts
        )
        assert_relation(result, "source", "no_os_synthesized", exp["no_os_synthesized"], observed_no_os, observed_no_os)
        observed_passthrough = isinstance(scripts, list) and any(
            isinstance(script, dict) and exp["passthrough_carried"] in script for script in scripts
        )
        result.add_check("source", "passthrough_carried", exp["passthrough_carried"], exp["passthrough_carried"] if observed_passthrough else scripts, observed_passthrough)
        canonical = hash_value(response, "canonical")
        rendered = send(result, session, ctx, render(canonical, "per-os-key-map-provider"))
        parsed = _parse_structured_output(output_value(rendered))
        value = inp["source"]["shell"]
        structured, paths = _structured_value_only(parsed, value) if parsed is not ABSENT else (False, [ABSENT])
        # DERIVATION: [ACIF-HOOK] §12.3 and [ACIF-CORE] §8.5 require opaque
        # passthrough values to be emitted through the target structured
        # encoder; an injection-shaped value must appear only as a parsed field
        # value, never as part of a command string.
        result.add_check("render", "render_back", exp["render_back"], paths, structured)
    return result


@binding("TV-PLATFORM-n")
def tv_platform_n(vector: Vector, session: Any, ctx: Any):
    result = result_for(vector)
    inp = vector.data["input"]
    response = send(result, session, ctx, _ingest_provider(ctx, inp["source_mechanism"], inp["source"]))
    assert_error(result, "source", response, vector.data["expect"]["error"])
    return result


@binding("TV-PLATFORM-o")
def tv_platform_o(vector: Vector, session: Any, ctx: Any):
    result = result_for(vector)
    inp = vector.data["input"]
    exp = vector.data["expect"]
    response = send(
        result,
        session,
        ctx,
        render(_canonical_hook(inp["canonical_scripts"]), inp["render_target"]),
        tags={"degradation_path": "hook-os-drop", "paired_diagnostic": exp["diagnostic"]},
    )
    assert_output_contains(result, "render", response, "emitted", exp["emitted"])
    assert_output_excludes(result, "render", response, "dropped", exp["dropped"])
    assert_diagnostic(result, "render", response, exp["diagnostic"])
    return result


@binding("TV-PLATFORM-p")
def tv_platform_p(vector: Vector, session: Any, ctx: Any):
    result = result_for(vector)
    inp = vector.data["input"]
    exp = vector.data["expect"]
    for idx, case in enumerate(inp["cases"], start=1):
        expected = exp[f"case_{idx}"]
        invocation = {"target_os": case["target_os"]} if "target_os" in case else None
        response = send(result, session, ctx, render(_canonical_hook(inp["canonical_scripts"]), case["render_target"], invocation))
        if "emitted" in expected:
            assert_output_contains(result, f"case_{idx}", response, "emitted", expected["emitted"])
        else:
            assert_error(result, f"case_{idx}", response, expected["error"])
    return result


@binding("TV-PLATFORM-q")
def tv_platform_q(vector: Vector, session: Any, ctx: Any):
    result = result_for(vector)
    inp = vector.data["input"]
    exp = vector.data["expect"]
    base = send(result, session, ctx, ingest("hook", sidecar=inp["base"]["hook"], body_root=ctx.materialize(inp["referenced_files"])))
    assert_result_field(result, "base", base, "body_hash", exp["body_hash_base"])

    flipped_hook = copy.deepcopy(inp["base"]["hook"])
    flipped_hook["handlers"][0]["scripts"][0]["os"] = inp["edits"][0]["value"]
    flipped = send(result, session, ctx, ingest("hook", sidecar=flipped_hook, body_root=ctx.materialize(inp["referenced_files"])))
    assert_result_field(result, "os_flipped", flipped, "body_hash", exp["body_hash_os_flipped"])

    passthrough_hook = copy.deepcopy(inp["base"]["hook"])
    passthrough_hook["handlers"][0]["scripts"][0].update(inp["edits"][1]["add_passthrough"])
    passthrough = send(result, session, ctx, ingest("hook", sidecar=passthrough_hook, body_root=ctx.materialize(inp["referenced_files"])))

    if _all_ok([base, flipped, passthrough]):
        observed = [hash_value(base, "body_hash"), hash_value(flipped, "body_hash"), hash_value(passthrough, "body_hash")]
        assert_relation(
            result,
            "edits",
            "each_edit_moves_body_hash",
            exp["each_edit_moves_body_hash"],
            observed,
            hash_value(base, "body_hash") != hash_value(flipped, "body_hash")
            and hash_value(base, "body_hash") != hash_value(passthrough, "body_hash"),
        )
    return result


@binding("TV-PLATFORM-q2")
def tv_platform_q2(vector: Vector, session: Any, ctx: Any):
    result = result_for(vector)
    inp = vector.data["input"]
    exp = vector.data["expect"]
    responses = []
    for case in ("variant_a", "variant_b"):
        response = send(result, session, ctx, ingest("hook", sidecar=inp[case]["hook"], body_root=ctx.materialize(inp["referenced_files"])))
        responses.append(response)
        assert_result_field(result, case, response, "body_hash", exp["body_hash"])
    if _all_ok(responses):
        assert_relation(
            result,
            "variants",
            "canonical_bytes_identical",
            exp["canonical_bytes_identical"],
            [hash_value(response, "canonical_bytes") for response in responses],
            hash_value(responses[0], "canonical_bytes") == hash_value(responses[1], "canonical_bytes"),
        )
        assert_relation(
            result,
            "variants",
            "body_hash_identical",
            exp["body_hash_identical"],
            [hash_value(response, "body_hash") for response in responses],
            hash_value(responses[0], "body_hash") == hash_value(responses[1], "body_hash"),
        )
    return result


@binding("TV-PLATFORM-r")
def tv_platform_r(vector: Vector, session: Any, ctx: Any):
    result = result_for(vector)
    inp = vector.data["input"]
    exp = vector.data["expect"]
    canonical = _canonical_hook(inp["canonical_scripts"])
    rendered = send(result, session, ctx, render(canonical, inp["render_target"]))
    rendered_output = output_value(rendered)
    roundtrip = send(
        result,
        session,
        ctx,
        ingest("hook", provider_config=provider_config(inp["render_target"], "hooks.rendered", rendered_output)),
    )
    if rendered.kind == "ok" and roundtrip.kind == "ok":
        observed_scripts = _scripts(roundtrip)
        assert_relation(result, "roundtrip", "roundtrip_identity", exp["roundtrip_identity"], observed_scripts, observed_scripts == inp["canonical_scripts"])
        dead_default = isinstance(observed_scripts, list) and inp["canonical_scripts"][0] in observed_scripts
        assert_relation(result, "roundtrip", "dead_default_preserved", exp["dead_default_preserved"], dead_default, dead_default)
    else:
        assert_result_field(result, "roundtrip", roundtrip, "canonical", canonical)
    return result


@binding("TV-PLATFORM-s")
def tv_platform_s(vector: Vector, session: Any, ctx: Any):
    result = result_for(vector)
    inp = vector.data["input"]
    exp = vector.data["expect"]
    for case in ("portable", "divergent"):
        response = send(result, session, ctx, project(_canonical_hook(inp[case]["scripts"]), "os_coverage"))
        assert_result_field(result, case, response, "projection.os", exp[case]["os"])
        assert_result_field(result, case, response, "projection.os_divergent", exp[case]["os_divergent"])
    return result


@binding("TV-PLATFORM-t")
def tv_platform_t(vector: Vector, session: Any, ctx: Any):
    result = result_for(vector)
    inp = vector.data["input"]
    exp = vector.data["expect"]
    for idx, case in enumerate(inp["cases"], start=1):
        hook = _canonical_hook(inp["scripts"], blocking=case["blocking"])
        response = send(result, session, ctx, evaluate_install(hook, inp["install_target_os"]))
        expected = exp[f"case_{idx}"]
        assert_result_field(result, f"case_{idx}", response, "install", expected["install"])
        if "diagnostic" in expected:
            assert_diagnostic(result, f"case_{idx}", response, expected["diagnostic"])
    return result
