#!/usr/bin/env python3
"""Informative development fixture for exercising the conformance runner.

This adapter is not a reference implementation of ACIF semantics, not a
conformance claimant, and never graduation evidence.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import http.client
import json
import os
import re
import socket
import ssl
import sys
import unicodedata
import urllib.error
import urllib.request
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import urljoin, urlsplit, urlunsplit

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "reference"))

from acif_hash import (  # noqa: E402
    body_hash_frontmatter_type,
    canonical_text,
    classify,
    jcs,
    metadata_hash,
    sidecar_only_body_hash,
)


class Unsupported(Exception):
    pass


class SpecError(Exception):
    def __init__(self, error: str, diagnostics: list[dict[str, Any]] | None = None):
        super().__init__(error)
        self.error = error
        self.diagnostics = diagnostics or []


EVENT_MAP = {
    "PreToolUse": "before_tool_execute",
    "BeforeTool": "before_tool_execute",
    "tool.execute.before": "before_tool_execute",
}
CANONICAL_EVENTS = {"session_start", "before_tool_execute"}
FRONTMATTER_KINDS = {"skill", "rule", "command", "agent"}
UNRESOLVED_INSTALL = "refuse-unless-operator-opt-in"
AGENT_NATIVE_BY_PROVIDER = {
    "claude-code": "Agent",
    "copilot-cli": "task",
    "opencode": "task",
    "vs-code-copilot": "Agent",
    "zed": "spawn_agent",
    "codex": "spawn_agent",
    "kiro": "use_subagent",
    "factory-droid": "Task",
}
AGENT_NATIVE_TO_CANONICAL = {value.lower(): "agent" for value in AGENT_NATIVE_BY_PROVIDER.values()}
AGENT_NATIVE_TO_CANONICAL.update(
    {
        "read": "file_read",
        "read_file": "file_read",
        "view": "file_read",
        "write": "file_write",
        "write_file": "file_write",
        "create": "file_write",
        "edit": "file_edit",
        "edit_file": "file_edit",
        "replace": "file_edit",
    }
)
UNRESERVED = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~")
REDIRECTS = {301, 302, 303, 307, 308}
PERMANENT_REDIRECTS = {301, 308}
MAX_REDIRECTS = 10


def emit(obj: dict[str, Any]) -> None:
    print(json.dumps(obj, ensure_ascii=False, separators=(",", ":")), flush=True)


def ok(result: dict[str, Any]) -> dict[str, Any]:
    return {"ok": True, "result": result}


def main() -> int:
    for line in sys.stdin:
        try:
            request = json.loads(line)
            response = handle(request)
        except Unsupported:
            response = {"unsupported": True}
        except SpecError as exc:
            response = {"ok": False, "error": exc.error, "diagnostics": exc.diagnostics}
        except _ConformanceFalse as exc:
            response = {"ok": True, "result": {"conformant": False, "reason": exc.reason}}
        except Exception as exc:  # pragma: no cover - deliberately adapter-internal
            response = {"ok": False, "error": f"adapter: {exc}"}
        emit(response)
    return 0


def handle(request: dict[str, Any]) -> dict[str, Any]:
    op = request.get("op")
    if op == "hello":
        return ok(
            {
                "implementation": "acif-bootstrap",
                "version": "0.1",
                "adapter_protocol": 1,
                "scopes": ["core", "hook", "publisher", "registry", "install"],
            }
        )
    inp = request.get("input")
    if not isinstance(inp, dict):
        raise Unsupported()
    if op == "ingest":
        return handle_ingest(inp)
    if op == "project":
        return handle_project(inp)
    if op == "render":
        return handle_render(inp)
    if op == "evaluate_install":
        return handle_evaluate_install(inp)
    if op == "resolve_install_targets":
        return handle_resolve_install_targets(inp)
    if op == "reconcile_frontmatter":
        return handle_reconcile_frontmatter(inp)
    if op == "resolve_reference":
        return handle_resolve_reference(inp)
    if op == "normalize_uri":
        return ok({"source_uri": normalize_source_uri(_str(inp.get("uri")))})
    if op == "derive_url_name":
        return handle_derive_url_name(inp)
    if op == "evaluate_freshness":
        return handle_evaluate_freshness(inp)
    if op == "fetch_uri":
        return handle_fetch_uri(inp)
    raise Unsupported()


def handle_ingest(inp: dict[str, Any]) -> dict[str, Any]:
    kind = inp.get("kind")
    if kind == "pack" and isinstance(inp.get("manifests"), list):
        return handle_pack_manifests(inp["manifests"])
    context = inp.get("context") if isinstance(inp.get("context"), dict) else {}
    if context.get("validation_surface") == "publisher_packless_item":
        return ok({"conformant": True, "installable": True})
    if context.get("validation_surface") == "registry_emit":
        registry = inp.get("sidecar", {}).get("registry_section") if isinstance(inp.get("sidecar"), dict) else None
        if not isinstance(registry, dict) or "source_uri" not in registry:
            raise SpecError("acif.source_uri.missing")
        return ok({"conformant": True})
    if kind == "pack":
        return handle_pack_ingest(inp)
    if kind == "hook":
        return handle_hook_ingest(inp)
    if kind in FRONTMATTER_KINDS:
        return handle_frontmatter_ingest(kind, inp)
    raise Unsupported()


def handle_pack_manifests(manifests: list[dict[str, Any]]) -> dict[str, Any]:
    if not manifests:
        raise Unsupported()
    winner = manifests[0]
    result: dict[str, Any] = {
        "canonical_source": winner.get("source"),
        "canonical_display_name": winner.get("name"),
        "diagnostics": [],
    }
    names = [manifest.get("name") for manifest in manifests]
    if len(set(names)) > 1:
        result["diagnostics"].append(
            {
                "id": "acif.publisher.pack_source_conflict",
                "params": {
                    "sources": [manifest.get("source") for manifest in manifests],
                    "values": names,
                },
            }
        )
    return ok(result)


def handle_pack_ingest(inp: dict[str, Any]) -> dict[str, Any]:
    sidecar = inp.get("sidecar")
    if not isinstance(sidecar, dict):
        raise Unsupported()
    if sidecar.get("source_kind") == "inferred":
        return ok({})
    publisher_section = dict(sidecar)
    result = {"publisher_section": publisher_section, "metadata_hash": metadata_hash(publisher_section)}
    return ok(result)


def handle_hook_ingest(inp: dict[str, Any]) -> dict[str, Any]:
    hook, publisher_section = _hook_source(inp)
    body_root = inp.get("body_root")
    if body_root is not None and not isinstance(body_root, str):
        raise Unsupported()
    canonical, referenced_files = canonical_hook(hook, body_root)
    result: dict[str, Any] = {
        "canonical": canonical,
        "body_hash": sidecar_only_body_hash(canonical, referenced_files),
    }
    if publisher_section:
        result["publisher_section"] = publisher_section
        result["metadata_hash"] = metadata_hash(publisher_section)
        result["canonical_bytes"] = jcs(publisher_section).decode("utf-8")
    return ok(result)


def handle_frontmatter_ingest(kind: str, inp: dict[str, Any]) -> dict[str, Any]:
    if "provider_config" in inp:
        provider = inp["provider_config"]
        if not isinstance(provider, dict):
            raise Unsupported()
        return ok(_frontmatter_provider_result(kind, provider))

    sidecar = inp.get("sidecar")
    if isinstance(sidecar, dict) and "body_root" not in inp:
        if _looks_like_publisher_section(sidecar):
            publisher_section = dict(sidecar)
            return ok(
                {
                    "publisher_section": publisher_section,
                    "metadata_hash": metadata_hash(publisher_section),
                    "canonical_bytes": jcs(publisher_section).decode("utf-8"),
                }
            )
        return ok({"canonical": _canonical_frontmatter_block(kind, sidecar)})

    body_root = inp.get("body_root")
    entry_file = inp.get("entry_file")
    if not isinstance(body_root, str) or not isinstance(entry_file, str):
        raise Unsupported()
    files = _read_body_files(Path(body_root))
    if entry_file not in files:
        raise SpecError("acif.body.empty")
    classification = classify(files, entry_file)
    body_hash = body_hash_frontmatter_type(files, entry_file)
    frontmatter = _frontmatter_from_bytes(files[entry_file])
    result: dict[str, Any] = {
        "classification": classification,
        "body_hash": body_hash,
        "canonical": _canonical_frontmatter_block(kind, frontmatter),
    }
    if frontmatter:
        publisher_section = {"kind": kind, kind: frontmatter}
        result["publisher_section"] = publisher_section
        result["metadata_hash"] = metadata_hash(publisher_section)
        result["canonical_bytes"] = jcs(publisher_section).decode("utf-8")
    return ok(result)


def _frontmatter_provider_result(kind: str, provider: dict[str, Any]) -> dict[str, Any]:
    tag = provider.get("provider")
    content = provider.get("content")
    if kind != "agent":
        raise Unsupported()
    if isinstance(content, str):
        parsed = _parse_structured(content)
        if not isinstance(parsed, dict):
            raise Unsupported()
        block = parsed.get("agent", parsed)
        tools = block.get("tools", []) if isinstance(block, dict) else []
        canonical = {"agent": {"tools": [_canonical_agent_tool(tool) for tool in tools]}}
        return {"canonical": canonical}
    if not isinstance(content, dict):
        raise Unsupported()
    frontmatter = content.get("frontmatter", content)
    if not isinstance(frontmatter, dict):
        raise Unsupported()
    publisher_section = {"kind": "agent", "agent": dict(frontmatter)}
    canonical = _canonical_frontmatter_block("agent", frontmatter, provider=str(tag))
    return {
        "canonical": canonical,
        "publisher_section": publisher_section,
        "metadata_hash": metadata_hash(publisher_section),
        "canonical_bytes": jcs(publisher_section).decode("utf-8"),
    }


def _looks_like_publisher_section(value: dict[str, Any]) -> bool:
    return any(key in value for key in ("kind", "id", "display_name", "version", "license", "pack_id"))


def _canonical_frontmatter_block(kind: str, frontmatter: dict[str, Any], provider: str | None = None) -> dict[str, Any]:
    if kind == "agent":
        block = dict(frontmatter)
        if "tools" in block and isinstance(block["tools"], list):
            block["tools"] = [_canonical_agent_tool(tool, provider) for tool in block["tools"]]
        return {"agent": block}
    return {kind: dict(frontmatter)}


def _canonical_agent_tool(tool: Any, provider: str | None = None) -> str:
    del provider
    if not isinstance(tool, str):
        raise Unsupported()
    return AGENT_NATIVE_TO_CANONICAL.get(tool.lower(), tool)


def _hook_source(inp: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    if "sidecar" in inp and isinstance(inp["sidecar"], dict):
        sidecar = inp["sidecar"]
        if isinstance(sidecar.get("hook"), dict):
            return sidecar["hook"], {key: value for key, value in sidecar.items() if key != "hook"}
        return sidecar, {}
    provider = inp.get("provider_config")
    if isinstance(provider, dict) and isinstance(provider.get("content"), dict):
        if provider.get("provider") == "per-os-key-map":
            return _hook_from_per_os_map(provider["content"]), {}
        return provider["content"], {}
    raise Unsupported()


def _hook_from_per_os_map(source: dict[str, Any]) -> dict[str, Any]:
    scripts: list[dict[str, Any]] = []
    passthrough = {key: value for key, value in source.items() if key not in {"command", "windows", "linux", "osx"}}
    if isinstance(source.get("command"), str):
        script = {"type": "file", "path": source["command"]}
        script.update(passthrough)
        scripts.append(script)
    # [ACIF-HOOK] §7.4 — after the key mapping, constrained entries with
    # identical executable identity merge into one entry, os set sorted union.
    constrained: dict[str, dict[str, Any]] = {}
    for key, os_values in (("osx", ["darwin"]), ("linux", ["linux"]), ("windows", ["windows"])):
        if isinstance(source.get(key), str):
            path = source[key]
            if path in constrained:
                constrained[path]["os"] = sorted(set(constrained[path]["os"]) | set(os_values))
            else:
                constrained[path] = {"type": "file", "path": path, "os": list(os_values)}
    scripts.extend(constrained.values())
    return {"event": "before_tool_execute", "handlers": [{"type": "command", "scripts": scripts}], "blocking": False}


def canonical_hook(hook: dict[str, Any], body_root: str | None) -> tuple[dict[str, Any], dict[str, bytes]]:
    event = hook.get("event")
    if event in EVENT_MAP:
        event = EVENT_MAP[event]
    elif event not in CANONICAL_EVENTS:
        raise SpecError("acif.hook.event_unrecognized")

    handlers = hook.get("handlers")
    if not isinstance(handlers, list) or not handlers:
        raise SpecError("acif.hook.handlers_missing")

    referenced_files: dict[str, bytes] = {}
    canonical_handlers = []
    for handler in handlers:
        if not isinstance(handler, dict):
            raise Unsupported()
        handler_type = handler.get("type", "command")
        if handler_type != "command":
            raise SpecError("acif.hook.handler_type_unrecognized")
        scripts = handler.get("scripts", [])
        if not isinstance(scripts, list):
            raise Unsupported()
        canonical_scripts = [canonicalize_script(script, body_root, referenced_files) for script in scripts]
        canonical_scripts.sort(key=jcs)
        canonical_handlers.append(
            {
                "type": "command",
                "scripts": canonical_scripts,
                "async": bool(handler.get("async", False)),
            }
        )

    block: dict[str, Any] = {
        "event": event,
        "handlers": canonical_handlers,
        "blocking": bool(hook.get("blocking", False)),
    }
    if "matcher" in hook:
        block["matcher"] = hook["matcher"]
    return block, referenced_files


def canonicalize_script(script: Any, body_root: str | None, referenced_files: dict[str, bytes]) -> dict[str, Any]:
    if not isinstance(script, dict):
        raise Unsupported()
    script_type = script.get("type")
    if script_type == "inline":
        content = script.get("content")
        if not isinstance(content, str):
            raise Unsupported()
        canonical: dict[str, Any] = {
            "type": "inline",
            "content": canonical_text(content.encode("utf-8")).decode("utf-8"),
        }
    elif script_type == "file":
        rel = script.get("path")
        if not isinstance(rel, str):
            raise Unsupported()
        _validate_relpath(rel)
        if body_root is not None:
            path = Path(body_root).joinpath(*PurePosixPath(rel).parts)
            try:
                referenced_files[rel] = path.read_bytes()
            except OSError:
                raise SpecError("acif.hook.script_file_missing") from None
        canonical = {"type": "file", "path": rel}
    else:
        raise Unsupported()

    for key, value in script.items():
        if key in {"type", "content", "path"}:
            continue
        canonical[key] = value
    return canonical


def _validate_relpath(rel: str) -> None:
    if "\\" in rel:
        raise SpecError("acif.hook.script_path_invalid")
    if rel.startswith("//") or rel.startswith("\\\\"):
        raise SpecError("acif.hook.script_path_invalid")
    if len(rel) >= 2 and rel[1] == ":" and rel[0].isalpha():
        raise SpecError("acif.hook.script_path_invalid")
    if any(part in {"", ".", ".."} for part in rel.split("/")):
        raise SpecError("acif.hook.script_path_invalid")
    p = PurePosixPath(rel)
    if p.is_absolute():
        raise SpecError("acif.hook.script_path_invalid")


def handle_project(inp: dict[str, Any]) -> dict[str, Any]:
    projection = inp.get("projection")
    if projection == "script_selection":
        item = inp.get("item")
        targets = inp.get("targets")
        if not isinstance(targets, list):
            raise Unsupported()
        hook = _extract_hook(item)
        selection, diagnostics = _script_selection(hook, targets)
        return ok({"selection": selection, "diagnostics": diagnostics})
    if projection == "os_coverage":
        hook = _extract_hook(inp.get("item"))
        return ok({"projection": _os_coverage(hook)})
    raise Unsupported()


def _extract_hook(item: Any) -> dict[str, Any]:
    if isinstance(item, dict) and isinstance(item.get("hook"), dict):
        return item["hook"]
    if isinstance(item, dict) and isinstance(item.get("event"), str):
        return item
    raise Unsupported()


def _first_handler_scripts(hook: dict[str, Any]) -> list[dict[str, Any]]:
    handlers = hook.get("handlers")
    if not isinstance(handlers, list) or not handlers or not isinstance(handlers[0], dict):
        raise Unsupported()
    scripts = handlers[0].get("scripts")
    if not isinstance(scripts, list):
        raise Unsupported()
    return [script for script in scripts if isinstance(script, dict)]


def _script_selection(hook: dict[str, Any], targets: list[str]) -> tuple[dict[str, str], list[dict[str, Any]]]:
    scripts = _first_handler_scripts(hook)
    selection: dict[str, str] = {}
    diagnostics: list[dict[str, Any]] = []
    for target in targets:
        selected = _select_script(scripts, target)
        if selected is None:
            selection[target] = "none"
            diagnostics.append({"id": "acif.hook.script_no_platform_match", "params": {"os": target}})
        else:
            selection[target] = str(selected.get("path", selected.get("content", "")))
    return selection, diagnostics


def _select_script(scripts: list[dict[str, Any]], target: str) -> dict[str, Any] | None:
    default: dict[str, Any] | None = None
    for script in scripts:
        os_values = script.get("os")
        if isinstance(os_values, list) and target in os_values:
            return script
        if "os" not in script and default is None:
            default = script
    return default


def _os_coverage(hook: dict[str, Any]) -> dict[str, Any]:
    scripts = _first_handler_scripts(hook)
    os_values: set[str] = set()
    constrained_count = 0
    for script in scripts:
        if isinstance(script.get("os"), list):
            constrained_count += 1
            os_values.update(str(value) for value in script["os"])
    if not os_values:
        os_values.update(["darwin", "linux", "windows"])
    return {"os": sorted(os_values), "os_divergent": constrained_count > 1}


INSTALL_MATRIX_PATH = ROOT / "install-entry-points.yaml"
_install_matrix_cache: dict[tuple[str, str], list[dict[str, Any]]] | None = None


def _install_matrix() -> dict[tuple[str, str], list[dict[str, Any]]]:
    global _install_matrix_cache
    if _install_matrix_cache is not None:
        return _install_matrix_cache
    document = yaml.safe_load(INSTALL_MATRIX_PATH.read_text(encoding="utf-8"))
    matrix: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for provider, types in (document.get("install_entry_points") or {}).items():
        for ctype, entries in (types or {}).items():
            matrix[(provider, ctype)] = [dict(entry) for entry in entries or []]
    _install_matrix_cache = matrix
    return matrix


def handle_resolve_install_targets(inp: dict[str, Any]) -> dict[str, Any]:
    content_name = inp.get("content_name")
    if (
        not isinstance(content_name, str)
        or not content_name
        or "/" in content_name
        or "\\" in content_name
        or "\x00" in content_name
        or content_name in {".", ".."}
    ):
        raise SpecError("acif.install.content_name_invalid")
    entry = inp.get("entry")
    if isinstance(entry, dict):
        rows = [dict(entry)]
    else:
        rows = [dict(row) for row in _install_matrix().get((_str(inp.get("provider")), _str(inp.get("content_type"))), [])]
    if not rows:
        raise SpecError("acif.install.no_entry_point")
    requested_scope = inp.get("scope")
    if isinstance(requested_scope, str):
        available = sorted({row["scope"] for row in rows})
        rows = [row for row in rows if row["scope"] == requested_scope]
        if not rows:
            raise SpecError(
                "acif.install.scope_unavailable",
                [{"id": "acif.install.scope_unavailable", "params": {"available_scopes": available}}],
            )
    targets: list[dict[str, Any]] = []
    diagnostics: list[dict[str, Any]] = []
    write_scopes: set[str] = set()
    superseded_scopes: set[str] = set()
    for row in rows:
        template = str(row["path_template"])
        for token in re.findall(r"<[^>]*>", template):
            if token != "<content-name>":
                raise SpecError("acif.install.placeholder_unrecognized")
        substituted = template.replace("<content-name>", content_name)
        if substituted.startswith("~/"):
            path = _str(inp.get("home_dir")).rstrip("/") + substituted[1:]
        elif substituted.startswith("/"):
            path = substituted
        else:
            path = _str(inp.get("project_root")).rstrip("/") + "/" + substituted
        write_target = row["status"] == "current" and row["scope"] not in write_scopes
        if write_target:
            write_scopes.add(row["scope"])
        if row["status"] == "superseded":
            superseded_scopes.add(row["scope"])
        targets.append(
            {"scope": row["scope"], "path": path, "layout": row["layout"], "status": row["status"], "write_target": write_target}
        )
    for scope in sorted(superseded_scopes - write_scopes):
        diagnostics.append({"id": "acif.install.entry_point_superseded", "params": {"scope": scope}})
    return ok({"targets": targets, "diagnostics": diagnostics})


def handle_evaluate_install(inp: dict[str, Any]) -> dict[str, Any]:
    item = inp.get("item")
    if isinstance(item, dict) and isinstance(item.get("cross_references"), list):
        for ref in item["cross_references"]:
            if isinstance(ref, dict) and ref.get("resolution") in {"unresolved", "revoked"}:
                return ok({"install": UNRESOLVED_INSTALL, "diagnostics": []})
    if isinstance(item, dict) and ("hook" in item or "event" in item):
        hook = _extract_hook(item)
        target = inp.get("install_target_os")
        if not isinstance(target, str):
            raise Unsupported()
        selection, diagnostics = _script_selection(hook, [target])
        if selection.get(target) == "none":
            install = UNRESOLVED_INSTALL if hook.get("blocking") is True else "proceed"
            return ok({"install": install, "diagnostics": diagnostics})
        return ok({"install": "proceed", "diagnostics": []})
    raise Unsupported()


def handle_reconcile_frontmatter(inp: dict[str, Any]) -> dict[str, Any]:
    sidecar_value = inp.get("sidecar_value")
    source_frontmatter = inp.get("source_frontmatter")
    mode = inp.get("mode")
    if not isinstance(sidecar_value, dict) or not isinstance(source_frontmatter, dict) or not isinstance(mode, str):
        raise Unsupported()
    diagnostics: list[dict[str, Any]] = []
    for key, value in sidecar_value.items():
        if key not in source_frontmatter:
            return ok({"action": "add-silently", "diagnostics": diagnostics})
        if source_frontmatter[key] != value:
            diagnostics.append({"id": "acif.publisher.frontmatter_conflict", "params": {"field": key}})
            return ok({"action": "overwrite" if mode == "overwrite" else "block", "diagnostics": diagnostics})
    return ok({"action": "leave-untouched", "diagnostics": diagnostics})


def handle_resolve_reference(inp: dict[str, Any]) -> dict[str, Any]:
    item = inp.get("item")
    state = inp.get("registry_state")
    if not isinstance(item, dict) or not isinstance(state, dict):
        raise Unsupported()
    agent = item.get("agent")
    if not isinstance(agent, dict) or not isinstance(agent.get("mcp_servers"), list):
        raise Unsupported()
    declared = agent["mcp_servers"][0]
    known = state.get("known_mcp_items_with_server")
    if not isinstance(declared, str) or not isinstance(known, dict):
        raise Unsupported()
    cross_reference = {
        "source_path": "agent.mcp_servers[0]",
        "declared_name": declared,
        "target_kind": "mcp_config",
        "resolution": "resolved" if declared in known else "unresolved",
    }
    diagnostics: list[dict[str, Any]] = []
    result: dict[str, Any] = {"cross_reference": cross_reference, "diagnostics": diagnostics}
    if declared in known:
        cross_reference["target_id"] = known[declared]
    else:
        diagnostics.append({"id": "acif.registry.reference_unresolved", "params": {"declared_name": declared}})
        result["install"] = UNRESOLVED_INSTALL
    return ok(result)


def handle_render(inp: dict[str, Any]) -> dict[str, Any]:
    canonical = inp.get("canonical")
    target = inp.get("target")
    if not isinstance(canonical, dict) or not isinstance(target, str):
        raise Unsupported()
    if isinstance(canonical.get("agent"), dict):
        tools = canonical["agent"].get("tools", [])
        native = [AGENT_NATIVE_BY_PROVIDER.get(target, str(tool)) if tool == "agent" else str(tool) for tool in tools]
        return ok({"output": json.dumps({"agent": {"tools": native}}, separators=(",", ":")), "diagnostics": [], "lossy": []})
    if isinstance(canonical.get("hook"), dict) or isinstance(canonical.get("event"), str):
        hook = _extract_hook(canonical)
        scripts = _first_handler_scripts(hook)
        output: dict[str, Any] = {"event": hook.get("event"), "scripts": []}
        for script in scripts:
            rendered = dict(script)
            output["scripts"].append(rendered)
            if "os" not in script and "path" in script:
                output["command"] = script["path"]
                for key, value in script.items():
                    if key not in {"type", "path", "content", "os"}:
                        output[key] = value
        return ok({"output": json.dumps(output, separators=(",", ":")), "diagnostics": [], "lossy": []})
    raise Unsupported()


def normalize_source_uri(uri: str) -> str:
    parts = urlsplit(uri)
    scheme = parts.scheme.lower()
    if scheme != "https":
        if scheme:
            raise SpecError("acif.source_uri.scheme_forbidden")
        raise SpecError("acif.source_uri.malformed")
    if not parts.netloc or parts.hostname is None:
        raise SpecError("acif.source_uri.malformed")
    if parts.username is not None or parts.password is not None:
        raise SpecError("acif.source_uri.userinfo_present")
    if parts.query:
        raise SpecError("acif.source_uri.query_present")
    try:
        host = parts.hostname.encode("idna").decode("ascii").lower()
    except UnicodeError:
        raise SpecError("acif.source_uri.malformed") from None
    try:
        port = parts.port
    except ValueError:
        raise SpecError("acif.source_uri.malformed") from None
    netloc = host if port in (None, 443) else f"{host}:{port}"
    path = _remove_dot_segments(_percent_normalize_path(parts.path or ""))
    if not path:
        path = "/"
    return urlunsplit(("https", netloc, path, "", ""))


def _percent_normalize_path(path: str) -> str:
    out: list[str] = []
    i = 0
    while i < len(path):
        if path[i] == "%" and i + 2 < len(path) and re.fullmatch(r"[0-9A-Fa-f]{2}", path[i + 1 : i + 3]):
            byte = int(path[i + 1 : i + 3], 16)
            char = chr(byte)
            if char in UNRESERVED:
                out.append(char)
            else:
                out.append("%" + path[i + 1 : i + 3].upper())
            i += 3
        else:
            out.append(path[i])
            i += 1
    return "".join(out)


def _remove_dot_segments(path: str) -> str:
    leading = path.startswith("/")
    trailing = path.endswith("/")
    out: list[str] = []
    for segment in path.split("/"):
        if segment in {"", "."}:
            continue
        if segment == "..":
            if out:
                out.pop()
            continue
        out.append(segment)
    result = ("/" if leading else "") + "/".join(out)
    if trailing and result != "/":
        result += "/"
    return result or "/"


def handle_derive_url_name(inp: dict[str, Any]) -> dict[str, Any]:
    source_uri = normalize_source_uri(_str(inp.get("uri")))
    classification = inp.get("body_classification")
    path = urlsplit(source_uri).path
    if classification == "single-file":
        if path.endswith("/"):
            raise SpecError("acif.source_uri.direct_file_trailing_slash")
        last = path.rsplit("/", 1)[-1]
        derived = last.rsplit(".", 1)[0] if "." in last else last
        result: dict[str, Any] = {"url_derived_name": derived, "diagnostics": []}
        declared = inp.get("frontmatter_name")
        if isinstance(declared, str) and declared != derived:
            result["diagnostics"].append(
                {
                    "id": "acif.source_uri.filename_conflict",
                    "params": {"url_derived_name": derived, "declared_name": declared},
                }
            )
        return ok(result)
    if classification == "multi-file":
        return ok({"conformant": True, "url_derived_name": "none", "diagnostics": []})
    raise Unsupported()


def handle_evaluate_freshness(inp: dict[str, Any]) -> dict[str, Any]:
    record = inp.get("record")
    if not isinstance(record, dict):
        raise Unsupported()
    fetched_at = _parse_rfc3339(record.get("fetched_at"))
    expires = _parse_rfc3339(record["expires"]) if "expires" in record else fetched_at + dt.timedelta(hours=72)
    if expires < fetched_at:
        raise SpecError("acif.registry.expires_before_fetched_at")
    consumer_clock = _parse_rfc3339(inp.get("consumer_clock")) if "consumer_clock" in inp else fetched_at
    tolerance = inp.get("declared_tolerance_seconds")
    stale_threshold = expires
    if isinstance(tolerance, int):
        stale = consumer_clock > expires - dt.timedelta(seconds=tolerance)
    else:
        stale = consumer_clock > stale_threshold
    staleness = "stale" if stale else "fresh"
    attestation_eval = inp.get("attestation_evaluation")
    trust_tier = "attested" if attestation_eval == "valid" else "unattested"
    policies = inp.get("policies") if isinstance(inp.get("policies"), list) else ["default"]
    install = "refuse" if stale and "freshness-enforcement-opt-in" in policies else "proceed"
    warnings = (
        [{"id": "acif.registry.stale", "params": {"expires": expires.isoformat().replace("+00:00", "Z")}}]
        if stale and "default" in policies
        else []
    )
    response_bytes = jcs({"record": record})
    return ok(
        {
            "conformant": True,
            "staleness": staleness,
            "trust_tier": trust_tier,
            "warnings": warnings,
            "install": install,
            "response_hash": hashlib.sha256(response_bytes).hexdigest(),
        }
    )


def _parse_rfc3339(value: Any) -> dt.datetime:
    if not isinstance(value, str):
        raise Unsupported()
    if not (value.endswith("Z") or re.search(r"[+-]\d\d:\d\d$", value)):
        raise _ConformanceFalse("rfc3339-explicit-offset-required")
    parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise _ConformanceFalse("rfc3339-explicit-offset-required")
    return parsed.astimezone(dt.timezone.utc)


class _ConformanceFalse(Exception):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def handle_fetch_uri(inp: dict[str, Any]) -> dict[str, Any]:
    url = _str(inp.get("url"))
    trust_ca = _str(inp.get("trust_ca"))
    resolve = inp.get("resolve")
    if not isinstance(resolve, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in resolve.items()):
        raise Unsupported()
    requested_record = normalize_source_uri(url)
    current = url
    recorded = requested_record
    seen = {current}
    redirects = 0
    temporary_seen = False
    while True:
        if urlsplit(current).scheme != "https":
            raise SpecError("acif.source_uri.redirect_downgrade")
        response = _open_no_redirect(current, trust_ca, resolve)
        code = response["status"]
        if code in REDIRECTS:
            location = response["headers"].get("Location")
            if not location:
                raise Unsupported()
            next_url = urljoin(current, location)
            if urlsplit(next_url).scheme != "https":
                raise SpecError("acif.source_uri.redirect_downgrade")
            if redirects >= MAX_REDIRECTS or next_url in seen:
                raise SpecError("acif.source_uri.redirect_limit")
            if code in PERMANENT_REDIRECTS:
                # Registry §10.4 composition rule: the permanent prefix
                # advances the recorded value; the first temporary redirect
                # freezes it for the rest of the chain.
                if not temporary_seen:
                    recorded = normalize_source_uri(next_url)
            else:
                temporary_seen = True
            redirects += 1
            seen.add(next_url)
            current = next_url
            continue
        return ok({"source_uri": recorded})


def _open_no_redirect(url: str, trust_ca: str, resolve: dict[str, str]) -> dict[str, Any]:
    context = ssl.create_default_context(cafile=trust_ca)

    class ResolvedHTTPSConnection(http.client.HTTPSConnection):
        def __init__(self, host: str, port: int | None = None, **kwargs: Any) -> None:
            super().__init__(host, port=port, context=context, **kwargs)

        def connect(self) -> None:
            target = resolve.get(self.host)
            if target is None:
                raise OSError(f"no resolve entry for {self.host}")
            target_host, target_port = target.rsplit(":", 1)
            if target_host != "127.0.0.1":
                raise OSError("reference adapter fetch_uri is restricted to loopback")
            sock = socket.create_connection((target_host, int(target_port)), self.timeout, self.source_address)
            self.sock = self._context.wrap_socket(sock, server_hostname=self.host)

    class ResolvedHTTPSHandler(urllib.request.HTTPSHandler):
        def https_open(self, req: urllib.request.Request) -> Any:
            return self.do_open(ResolvedHTTPSConnection, req)

    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req: Any, fp: Any, code: int, msg: str, headers: Any, newurl: str) -> None:
            return None

    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect, ResolvedHTTPSHandler)
    request = urllib.request.Request(url, method="GET")
    try:
        with opener.open(request, timeout=10) as response:
            response.read()
            return {"status": response.status, "headers": response.headers}
    except urllib.error.HTTPError as exc:
        exc.read()
        return {"status": exc.code, "headers": exc.headers}


def _read_body_files(root: Path) -> dict[str, bytes]:
    files: dict[str, bytes] = {}
    normalized_paths: set[str] = set()
    for dirpath, dirnames, filenames in os.walk(root):
        current = Path(dirpath)
        for dirname in list(dirnames):
            if (current / dirname).is_symlink():
                raise SpecError("acif.body.symlink")
        for filename in filenames:
            path = current / filename
            if path.is_symlink():
                raise SpecError("acif.body.symlink")
            rel = path.relative_to(root).as_posix()
            nfc = unicodedata.normalize("NFC", rel)
            if nfc in normalized_paths:
                raise SpecError("acif.body.path_collision")
            normalized_paths.add(nfc)
            files[rel] = path.read_bytes()
    publishable = [rel for rel in files if _publishable_body_path(rel)]
    if not publishable:
        raise SpecError("acif.body.empty")
    return files


def _publishable_body_path(rel: str) -> bool:
    parts = rel.split("/")
    if any(part in {".git", ".svn", ".hg", ".bzr", "_darcs", ".fossil"} for part in parts):
        return False
    if len(parts) == 1:
        upper = parts[0].upper()
        if upper.startswith("LICENSE") or upper.startswith("README") or parts[0] == "acif-sidecar.yaml":
            return False
    return True


def _frontmatter_from_bytes(data: bytes) -> dict[str, Any]:
    text = canonical_text(data).decode("utf-8")
    if not text.startswith("---\n"):
        return {}
    end = text.find("\n---\n", 4)
    if end == -1:
        return {}
    parsed = yaml.safe_load(text[4:end]) or {}
    return parsed if isinstance(parsed, dict) else {}


def _parse_structured(value: str) -> Any:
    for parser in (json.loads, yaml.safe_load):
        try:
            return parser(value)
        except Exception:
            pass
    raise Unsupported()


def _str(value: Any) -> str:
    if not isinstance(value, str):
        raise Unsupported()
    return value


if __name__ == "__main__":
    raise SystemExit(main())
