"""Differential mode — DESIGN.md §8 graduation evidence.

Generates randomized equivalence-preserving inputs (fresh bodies through
`ingest`, fresh URI strings through `normalize_uri`) and requires two
independent implementations to agree with each other. The pair is its own
oracle: every generated input lives in an equivalence class where the spec
pins a deterministic answer, so the harness never needs to know the answer
itself. This kills the lookup-table adapter class — you cannot pre-compute
answers to inputs that did not exist yesterday.

Trials are generated deterministically from --seed before any adapter is
spawned; the same seed and count reproduce the same run byte-for-byte
(modulo fixture paths).

Family discipline:
- required families (body, sidecar, envelope, pack_id, and the four
  hook_* families) mirror request forms the static vectors already force
  both adapters to serve; an `unsupported` there breaks the run. The
  hook_* families became required when both implementations declared the
  hook scope (acif-5lk).
- the normalize_uri family is informative until both implementations
  claim registry scope: either side answering `unsupported` marks the
  trial uncomparable, never a disagreement.

Hook-family equivalence discipline ([ACIF-HOOK]):
- hook_sidecar / hook_body generate only inputs whose answer the spec
  pins: §7.2-disjoint os partitions, §7.1 rejects (empty/invalid os,
  ambiguity), §8.2 absent-type materialization, §9 preimage inputs.
- hook_provider_event exercises the Appendix A.1 provider event-name
  mappings (including the copilot-cli `errorOccurred` multi-match, whose
  §8.1 lexicographic tiebreak is pinned) and unrecognized spellings.
- hook_mechanism exercises the §7.4 shape predicates. The canonical
  EVENT of a mechanism-only ingest is deliberately NOT compared: the
  synthesized-envelope event is an identified spec-precision gap, so the
  family compares `canonical.handlers`, provenance, and diagnostic ids
  instead of whole canonical bytes.
"""

from __future__ import annotations

import argparse
import random
import shutil
from typing import Any

from . import RUNNER_PROTOCOL, RUNNER_VERSION
from .fixtures import EnvBlocked, FixtureContext, probe_environment
from .protocol import AdapterSession
from .report import write_report

ABSENT = "<absent>"

# TV-3's pinned inference namespace ([ACIF-PUBLISHER] §9.4).
PINNED_NAMESPACE = "93516344-00e5-419b-a230-6e8b1d02f87d"

KINDS = ["hook", "skill", "rule", "command", "agent", "mcp_config", "pack"]
FRONTMATTER_KINDS = ["skill", "rule", "command", "agent"]
FORBIDDEN_FIELDS = [
    "effective_version",
    "derived_version",
    "pack_inherited_version",
    "resolved_version",
]

REQUIRED_FAMILIES = {
    "body", "sidecar", "envelope", "pack_id",
    "hook_sidecar", "hook_provider_event", "hook_mechanism", "hook_body",
}
FAMILY_WEIGHTS = [
    ("body", 35),
    ("sidecar", 25),
    ("envelope", 20),
    ("pack_id", 10),
    ("normalize_uri", 10),
    ("hook_sidecar", 15),
    ("hook_provider_event", 10),
    ("hook_mechanism", 15),
    ("hook_body", 10),
]

_WORDS = [
    "hash", "canonical", "sidecar", "registry", "publisher", "envelope",
    "conformance", "vector", "adapter", "fixture", "scope", "record",
    "café", "naïve", "Zürich", "日本語", "emoji ☕", "tab\tstop",
    "quote \"inner\"", "back\\slash", "trailing space ",
]

_FILE_NAMES = [
    "notes.md", "README.md", "docs/guide.md", "docs/deep/ref.md",
    "scripts/run.sh", "data/values.json", "sub/acif-sidecar.yaml",
    "LICENSE", "assets/café.txt",
]

_DISPLAY_NAMES = [
    "Demo Skill", "Review PR", "café ☕ tool", "quote\"back\\slash",
    "line\nbreak name", "tab\tname", "Ünïcodé Nàme", "日本語ツール",
    "  padded  ", "0", "a" * 80,
]

_SPDX_VALID = ["MIT", "Apache-2.0", "BSD-3-Clause", "ISC", "MPL-2.0"]
_SPDX_INVALID = ["MIT License", "Apache 2.0", "GPL v3", ""]

_SEMVER_VALID = ["1.2.3", "0.1.0", "10.20.30", "1.0.0-rc.1", "2.3.4-alpha.7", "1.2.3+build.5"]
_SEMVER_INVALID = ["1.0", "v1.0.0", "1.0.0.0", "01.2.3", "1.2", "1.2.3 "]

_KIND_INVALID = ["Skill", "SKILL", "skills", "plugin", "mcp", "Rule"]

# Canonical hook event names ([ACIF-HOOK] Appendix A.1, representative
# subset). Any canonical name is a conforming sidecar `event` value.
_HOOK_EVENTS = [
    "before_tool_execute", "after_tool_execute", "before_prompt",
    "agent_stop", "session_start", "session_end", "before_compact",
    "notification", "subagent_start", "subagent_stop", "error_occurred",
    "permission_request", "file_changed", "before_model", "turn_start",
]

# (provider tag, provider-native spelling, canonical) rows transcribed
# from Appendix A.1. The canonical member is documentation for the reader
# only — trials never compare against it (the pair is its own oracle).
_HOOK_EVENT_ALIASES = [
    ("claude-code", "PreToolUse", "before_tool_execute"),
    ("gemini-cli", "BeforeTool", "before_tool_execute"),
    ("opencode", "tool.execute.before", "before_tool_execute"),
    ("cursor", "PostToolUse", "after_tool_execute"),
    ("kiro", "postToolUse", "after_tool_execute"),
    ("pi", "tool_result", "after_tool_execute"),
    ("claude-code", "UserPromptSubmit", "before_prompt"),
    ("windsurf", "pre_user_prompt", "before_prompt"),
    ("factory-droid", "Stop", "agent_stop"),
    ("opencode", "session.idle", "agent_stop"),
    ("kiro", "agentSpawn", "session_start"),
    ("windsurf", "session_start", "session_start"),
    ("pi", "session_shutdown", "session_end"),
    ("gemini-cli", "PreCompress", "before_compact"),
    ("vs-code-copilot", "SubagentStart", "subagent_start"),
    ("copilot-cli", "subagentStop", "subagent_stop"),
    ("opencode", "session.error", "error_occurred"),
    # copilot-cli errorOccurred is a multi-match (error_occurred and
    # tool_use_failure); §8.1 pins the lexicographically smaller name.
    ("copilot-cli", "errorOccurred", "error_occurred"),
    ("opencode", "permission.asked", "permission_request"),
    ("cursor", "afterFileEdit", "file_changed"),
    ("kiro", "File Save", "file_changed"),
    ("gemini-cli", "BeforeModel", "before_model"),
    ("pi", "turn_start", "turn_start"),
]

_HOOK_OS_ENUM = ["darwin", "linux", "windows"]
_HOOK_ARCHES = ["arm64", "x86_64"]

_HOOK_SCRIPT_PATHS = [
    "hooks/run.sh", "hooks/win.cmd", "hooks/base.sh", "hooks/check.ps1",
    "scripts/deep/audit.sh", "hooks/café.sh", "hooks/a b.sh",
]

_URI_POOL = [
    "https://example.com/skills/demo",
    "HTTPS://Example.COM/Skills/Demo",
    "https://example.com:443/skills/demo",
    "https://example.com/a/../b/./c",
    "https://example.com/a%2Fb/c%20d",
    "https://example.com/skills/demo/",
    "https://example.com//double//slash",
    "https://example.com/skills/demo?tag=v1#frag",
    "https://user@example.com/skills/demo",
    "http://example.com/skills/demo",
    "file:///opt/skills/demo",
    "https://example.com/%C3%A9clair",
    "https://xn--caf-dma.example/menu",
]


def _rand_uuid4(rng: random.Random) -> str:
    hexd = "0123456789abcdef"
    s = "".join(rng.choice(hexd) for _ in range(32))
    return f"{s[0:8]}-{s[8:12]}-4{s[13:16]}-{rng.choice('89ab')}{s[17:20]}-{s[20:32]}"


def _bad_uuid(rng: random.Random) -> str:
    choice = rng.randrange(4)
    if choice == 0:
        return "not-a-uuid"
    if choice == 1:
        return _rand_uuid4(rng).replace("-", "", 1)
    if choice == 2:
        # version nibble 1, not 4
        u = _rand_uuid4(rng)
        return u[:14] + "1" + u[15:]
    return _rand_uuid4(rng)[:-1]


def _rand_text(rng: random.Random, max_lines: int = 5) -> str:
    lines = [" ".join(rng.sample(_WORDS, rng.randrange(1, 4))) for _ in range(rng.randrange(0, max_lines))]
    text = "\n".join(lines)
    if rng.random() < 0.8:
        text += "\n"
    return text


def _gen_body(rng: random.Random) -> dict[str, Any]:
    files: dict[str, str] = {}
    entry = "SKILL.md"
    if rng.random() < 0.3:
        files[entry] = "---\ndescription: " + rng.choice(_WORDS) + "\n---\n" + _rand_text(rng)
    else:
        files[entry] = _rand_text(rng)
    for name in rng.sample(_FILE_NAMES, rng.randrange(0, 5)):
        files[name] = _rand_text(rng)
    if rng.random() < 0.25:
        files["acif-sidecar.yaml"] = "kind: skill\nid: " + _rand_uuid4(rng) + "\n"
    return {
        "family": "body",
        "input": {"kind": "skill", "files": files, "entry_file": entry},
        "compare": ["body_hash", "classification"],
    }


def _gen_sidecar(rng: random.Random) -> dict[str, Any]:
    kind = rng.choice(FRONTMATTER_KINDS)
    section: dict[str, Any] = {
        "kind": kind,
        "id": _rand_uuid4(rng),
        "display_name": rng.choice(_DISPLAY_NAMES),
    }
    if rng.random() < 0.6:
        section["version"] = rng.choice(_SEMVER_VALID)
    if rng.random() < 0.4:
        section["description"] = " ".join(rng.sample(_WORDS, rng.randrange(1, 5)))
    if rng.random() < 0.3:
        section["license"] = {"spdx": rng.choice(_SPDX_VALID)}
    if rng.random() < 0.2:
        section["pack_id"] = _rand_uuid4(rng)
    items = list(section.items())
    rng.shuffle(items)
    return {
        "family": "sidecar",
        "input": {"kind": kind, "sidecar": dict(items)},
        "compare": ["metadata_hash", "canonical_bytes"],
    }


def _gen_envelope(rng: random.Random) -> dict[str, Any]:
    kind = rng.choice(FRONTMATTER_KINDS)
    record: dict[str, Any] = {
        "kind": kind,
        "id": _rand_uuid4(rng),
        "display_name": rng.choice(_DISPLAY_NAMES),
    }
    defect = rng.choice(["kind", "id", "version", "spdx", "forbidden"])
    if defect == "kind":
        record["kind"] = rng.choice(_KIND_INVALID)
    elif defect == "id":
        record["id"] = _bad_uuid(rng)
    elif defect == "version":
        record["version"] = rng.choice(_SEMVER_INVALID)
    elif defect == "spdx":
        record["license"] = {"spdx": rng.choice(_SPDX_INVALID)}
    else:
        record[rng.choice(FORBIDDEN_FIELDS)] = rng.choice(_SEMVER_VALID)
    # Mirrors the TV-11 binding: input.kind carries the record's kind
    # verbatim, even when the defect under test is the kind itself.
    return {
        "family": "envelope",
        "input": {"kind": record["kind"], "sidecar": record},
        "compare": ["conformant", "reason", "params.field"],
    }


def _gen_pack_id(rng: random.Random) -> dict[str, Any]:
    org = "".join(rng.choice("abcdefghijklmnopqrstuvwxyz") for _ in range(rng.randrange(3, 10)))
    repo = "-".join(rng.sample(["agent", "skills", "tools", "pack", "acif", "demo"], rng.randrange(1, 3)))
    return {
        "family": "pack_id",
        "input": {
            "namespace": PINNED_NAMESPACE,
            "repository_url": f"https://github.com/{org}/{repo}",
            "display_name": rng.choice(_DISPLAY_NAMES),
        },
        "compare": ["inferred_pack_id"],
    }


def _gen_normalize_uri(rng: random.Random) -> dict[str, Any]:
    return {
        "family": "normalize_uri",
        "input": {"uri": rng.choice(_URI_POOL)},
        "compare": ["source_uri"],
    }


def _inline_script(rng: random.Random) -> dict[str, Any]:
    content = "#!/bin/sh\n" + _rand_text(rng, max_lines=3)
    if rng.random() < 0.25:
        # [ACIF-HOOK] TV-PLATFORM-q′ pins line-ending-variant convergence.
        content = content.replace("\n", "\r\n")
    return {"type": "inline", "content": content}


def _disjoint_os_sets(rng: random.Random, n: int) -> list[list[str]]:
    """Random pairwise-disjoint non-empty subsets of the §7.1 OS enum."""
    members = list(_HOOK_OS_ENUM)
    rng.shuffle(members)
    sets: list[list[str]] = []
    for _ in range(n):
        if not members:
            break
        take = rng.randrange(1, len(members) + 1)
        sets.append(members[:take])
        members = members[take:]
    return sets


def _gen_hook_sidecar(rng: random.Random) -> dict[str, Any]:
    hook: dict[str, Any] = {"event": rng.choice(_HOOK_EVENTS)}
    if rng.random() < 0.4:
        hook["blocking"] = rng.random() < 0.5

    if rng.random() < 0.25:
        # One spec-pinned §7.1/§7.2 reject per trial — exactly one
        # violation, so the diagnostic identity is unambiguous.
        kind = rng.choice(["os_empty", "os_invalid", "default_ambiguous", "platform_ambiguous"])
        if kind == "os_empty":
            entry = _inline_script(rng)
            entry["os"] = []
            scripts = [entry]
        elif kind == "os_invalid":
            entry = _inline_script(rng)
            entry["os"] = [rng.choice(["freebsd", "Linux", "macos", "win32"])]
            scripts = [entry]
        elif kind == "default_ambiguous":
            scripts = [_inline_script(rng), _inline_script(rng)]
        else:
            member = rng.choice(_HOOK_OS_ENUM)
            first, second = _inline_script(rng), _inline_script(rng)
            first["os"] = [member]
            second["os"] = [member]
            scripts = [first, second]
        hook["handlers"] = [{"type": "command", "scripts": scripts}]
        return {
            "family": "hook_sidecar",
            "input": {"kind": "hook", "sidecar": hook},
            "compare": ["conformant", "body_hash", "canonical_bytes"],
        }

    def conforming_handler() -> dict[str, Any]:
        scripts: list[dict[str, Any]] = []
        for os_set in _disjoint_os_sets(rng, rng.randrange(0, 3)):
            entry = _inline_script(rng)
            shuffled = list(os_set)
            rng.shuffle(shuffled)
            entry["os"] = shuffled
            if rng.random() < 0.2:
                arches = list(_HOOK_ARCHES)
                rng.shuffle(arches)
                entry["arch"] = arches[: rng.randrange(1, len(arches) + 1)]
            scripts.append(entry)
        if not scripts or rng.random() < 0.6:
            scripts.append(_inline_script(rng))  # at most one default entry
        rng.shuffle(scripts)
        handler: dict[str, Any] = {"scripts": scripts}
        if rng.random() < 0.75:
            handler["type"] = "command"  # absent type pins to command (§8.2)
        if rng.random() < 0.3:
            handler["async"] = rng.random() < 0.5
        if rng.random() < 0.2:
            handler["timeout"] = rng.randrange(5, 300)
        return handler

    handlers = [conforming_handler()]
    if rng.random() < 0.25:
        handlers.append(conforming_handler())  # order is significant and preserved
    hook["handlers"] = handlers
    return {
        "family": "hook_sidecar",
        "input": {"kind": "hook", "sidecar": hook},
        "compare": ["conformant", "body_hash", "canonical_bytes"],
    }


def _gen_hook_provider_event(rng: random.Random) -> dict[str, Any]:
    if rng.random() < 0.15:
        provider = "unknown-provider"
        native = rng.choice(["onToolStart", "beforeEverything", "toolWillRun"])
    else:
        provider, native, _ = rng.choice(_HOOK_EVENT_ALIASES)
    content = {
        "event": native,
        "handlers": [{"type": "command", "scripts": [_inline_script(rng)]}],
    }
    return {
        "family": "hook_provider_event",
        "input": {
            "kind": "hook",
            "provider_config": {"provider": provider, "path": "hooks.json", "content": content},
        },
        # No `conformant` on provider_config forms: PROTOCOL §4.1 scopes
        # the verdict fields to record-validation forms and makes every
        # result field optional, so presence asymmetry on this form is
        # adapter plumbing, not a semantic disagreement (syllago emits
        # `conformant: true` here; acif-ts omits it — both conforming).
        "compare": ["body_hash", "canonical_bytes"],
    }


def _gen_hook_mechanism(rng: random.Random) -> dict[str, Any]:
    token = rng.choice([
        "per-os-key-map", "per-os-key-map",
        "dual-shell-fields", "filename-extension-convention", "unknown",
    ])
    provider = token
    content: dict[str, Any] = {}
    if token == "per-os-key-map":
        if rng.random() < 0.4:
            provider = "per-os-key-map-provider"  # accepted §7.4 alias
        keys = [k for k in ["windows", "linux", "osx"] if rng.random() < 0.6]
        for key in keys:
            content[key] = rng.choice(_HOOK_SCRIPT_PATHS)
        if rng.random() < 0.25 and len(keys) >= 2:
            content[keys[1]] = content[keys[0]]  # §7.4 executable-identity merge
        has_base = rng.random() < 0.7
        if has_base:
            content["command"] = rng.choice(_HOOK_SCRIPT_PATHS)
        roll = rng.random()
        if roll < 0.15:
            content[rng.choice(keys) if keys else "command"] = rng.randrange(100)  # malformed
        elif roll < 0.3:
            content["timeout"] = "30"  # passthrough; malformed iff no base command
        if not content:
            content["command"] = rng.choice(_HOOK_SCRIPT_PATHS)
    elif token == "dual-shell-fields":
        roll = rng.random()
        if roll < 0.15:
            pass  # empty object → malformed
        elif roll < 0.3:
            content["bash"] = rng.choice(_HOOK_SCRIPT_PATHS)
            content["python"] = "x.py"  # closed-set violation → malformed
        else:
            for key in rng.sample(["bash", "powershell"], rng.randrange(1, 3)):
                content[key] = rng.choice(_HOOK_SCRIPT_PATHS)
    elif token == "filename-extension-convention":
        roll = rng.random()
        if roll < 0.15:
            content["notfile"] = "hooks/run.sh"  # missing `file` → malformed
        elif roll < 0.25:
            content["file"] = 7  # non-string → malformed
        else:
            content["file"] = rng.choice([
                "hooks/run.sh", "hooks/run.ps1", "hooks/run.cmd",
                "hooks/run.bat", "hooks/run", "hooks/run.xyz",
            ])
    else:
        provider = "unknown-" + rng.choice(["gadget", "mech", "layout"])  # totality net
        content["command"] = rng.choice(_HOOK_SCRIPT_PATHS)
    return {
        "family": "hook_mechanism",
        "input": {
            "kind": "hook",
            "provider_config": {"provider": provider, "path": "hooks.json", "content": content},
        },
        # No canonical_bytes here: the synthesized-envelope event of a
        # mechanism-only ingest is an identified spec-precision gap. No
        # `conformant` either — same provider_config field-optionality
        # rationale as hook_provider_event.
        "compare": ["canonical.handlers", "provenance", "diagnostics_ids"],
    }


def _gen_hook_body(rng: random.Random) -> dict[str, Any]:
    pool = list(_HOOK_SCRIPT_PATHS)
    rng.shuffle(pool)
    scripts: list[dict[str, Any]] = []
    for os_set in _disjoint_os_sets(rng, rng.randrange(0, 3)):
        shuffled = list(os_set)
        rng.shuffle(shuffled)
        scripts.append({"type": "file", "path": pool.pop(), "os": shuffled})
    if not scripts or rng.random() < 0.7:
        scripts.append({"type": "file", "path": pool.pop()})  # single default entry

    hook: dict[str, Any] = {
        "event": rng.choice(_HOOK_EVENTS),
        "handlers": [{"type": "command", "scripts": scripts}],
    }
    files: dict[str, str] = {
        entry["path"]: "#!/bin/sh\n" + _rand_text(rng) for entry in scripts
    }
    if rng.random() < 0.25:
        hook["auxiliary_files"] = [{"path": "assets/shared-utils.sh"}]
        files["assets/shared-utils.sh"] = "#!/bin/sh\n" + _rand_text(rng)
    if rng.random() < 0.3:
        files["docs/notes.md"] = _rand_text(rng)  # unreferenced: outside the §9.2 manifest
    if rng.random() < 0.15 and files:
        # Drop one referenced file: both sides must reject identically.
        referenced = sorted(p for p in files if p != "docs/notes.md")
        files.pop(rng.choice(referenced))
    return {
        "family": "hook_body",
        "input": {"kind": "hook", "hook": hook, "files": files},
        "compare": ["conformant", "body_hash", "canonical_bytes"],
    }


_GENERATORS = {
    "body": _gen_body,
    "sidecar": _gen_sidecar,
    "envelope": _gen_envelope,
    "pack_id": _gen_pack_id,
    "normalize_uri": _gen_normalize_uri,
    "hook_sidecar": _gen_hook_sidecar,
    "hook_provider_event": _gen_hook_provider_event,
    "hook_mechanism": _gen_hook_mechanism,
    "hook_body": _gen_hook_body,
}


def generate_trials(seed: int, count: int) -> list[dict[str, Any]]:
    rng = random.Random(seed)
    families = [name for name, weight in FAMILY_WEIGHTS for _ in range(weight)]
    trials = []
    for index in range(count):
        family = rng.choice(families)
        trial = _GENERATORS[family](rng)
        trial["index"] = index
        trials.append(trial)
    return trials


def _build_request(trial: dict[str, Any], ctx: FixtureContext) -> dict[str, Any]:
    family = trial["family"]
    inp = trial["input"]
    if family == "body":
        root = ctx.materialize(inp["files"])
        return {
            "op": "ingest",
            "input": {"kind": inp["kind"], "body_root": root, "entry_file": inp["entry_file"]},
        }
    if family in {"sidecar", "envelope", "hook_sidecar"}:
        return {"op": "ingest", "input": {"kind": inp["kind"], "sidecar": inp["sidecar"]}}
    if family in {"hook_provider_event", "hook_mechanism"}:
        return {"op": "ingest", "input": {"kind": inp["kind"], "provider_config": inp["provider_config"]}}
    if family == "hook_body":
        root = ctx.materialize(inp["files"])
        return {"op": "ingest", "input": {"kind": "hook", "sidecar": inp["hook"], "body_root": root}}
    if family == "pack_id":
        return {"op": "derive_pack_id", "input": dict(inp)}
    if family == "normalize_uri":
        return {"op": "normalize_uri", "input": {"uri": inp["uri"]}}
    raise ValueError(f"unknown trial family {family!r}")


def _lookup(result: dict[str, Any], path: str) -> Any:
    current: Any = result
    for part in path.split("."):
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return ABSENT
    return current


def _observe(response: Any, fields: list[str]) -> dict[str, Any]:
    if response.kind == "harness-error":
        return {"class": "harness-error", "detail": response.harness_error}
    if response.kind == "unsupported":
        return {"class": "unsupported"}
    if response.kind == "spec-error":
        return {"class": "error", "error": response.error}
    result = response.result or {}
    observed: dict[str, Any] = {}
    for f in fields:
        if f == "diagnostics_ids":
            # Order- and prose-insensitive diagnostic identity: absent
            # and empty diagnostics compare equal.
            diags = result.get("diagnostics") or []
            observed[f] = sorted({d["id"] for d in diags if isinstance(d, dict) and isinstance(d.get("id"), str)})
        else:
            observed[f] = _lookup(result, f)
    return {"class": "ok", "fields": observed}


def _trial_status(a: dict[str, Any], b: dict[str, Any], family: str) -> str:
    if a["class"] == "harness-error" or b["class"] == "harness-error":
        return "harness-error"
    if a["class"] == "unsupported" or b["class"] == "unsupported":
        if family in REQUIRED_FAMILIES:
            return "disagree" if a["class"] != b["class"] else "unsupported"
        return "uncomparable"
    return "agree" if a == b else "disagree"


def run_differential(
    *,
    adapter_a: str,
    adapter_b: str,
    seed: int,
    count: int,
    keep_fixtures: bool = False,
) -> dict[str, Any]:
    trials = generate_trials(seed, count)
    env = probe_environment()
    ctx = FixtureContext(env, keep_fixtures=keep_fixtures)

    rows: list[dict[str, Any]] = []
    counts = {"agree": 0, "disagree": 0, "uncomparable": 0, "unsupported": 0, "harness-error": 0, "env-skipped": 0}
    family_counts: dict[str, dict[str, int]] = {}

    with AdapterSession(adapter_a) as session_a, AdapterSession(adapter_b) as session_b:
        for trial in trials:
            row: dict[str, Any] = {
                "index": trial["index"],
                "family": trial["family"],
                "input": trial["input"],
            }
            try:
                request = _build_request(trial, ctx)
            except EnvBlocked as exc:
                row["status"] = "env-skipped"
                row["detail"] = str(exc)
            else:
                row["request_op"] = request["op"]
                response_a = session_a.request(request)
                response_b = session_b.request(request)
                a = _observe(response_a, trial["compare"])
                b = _observe(response_b, trial["compare"])
                row["a"] = a
                row["b"] = b
                row["status"] = _trial_status(a, b, trial["family"])
            counts[row["status"]] += 1
            fam = family_counts.setdefault(trial["family"], {})
            fam[row["status"]] = fam.get(row["status"], 0) + 1
            rows.append(row)

        hello_a = dict(session_a.hello or {})
        hello_b = dict(session_b.hello or {})

    kept = []
    if keep_fixtures:
        kept = [str(root) for root in ctx.roots]
    else:
        for root in ctx.roots:
            shutil.rmtree(root, ignore_errors=True)

    clean = (
        counts["disagree"] == 0
        and counts["harness-error"] == 0
        and counts["unsupported"] == 0
    )
    return {
        "differential": {
            "design": "DESIGN.md §8 differential pass (graduation evidence)",
            "seed": seed,
            "count": count,
            "clean": clean,
            "summary": counts,
            "families": family_counts,
        },
        "runner": {"version": RUNNER_VERSION, "runner_protocol": RUNNER_PROTOCOL},
        "adapters": {
            "a": {"invocation": adapter_a, "hello": hello_a},
            "b": {"invocation": adapter_b, "hello": hello_b},
        },
        "env_probes": env,
        "fixture_paths": kept,
        "trials": rows,
    }


def human_summary(report: dict[str, Any]) -> str:
    diff = report["differential"]
    a = report["adapters"]["a"]["hello"]
    b = report["adapters"]["b"]["hello"]
    lines = [
        f"Differential pass — seed {diff['seed']}, {diff['count']} trials",
        f"  A: {a.get('implementation')} {a.get('version')} (protocol {a.get('adapter_protocol')})",
        f"  B: {b.get('implementation')} {b.get('version')} (protocol {b.get('adapter_protocol')})",
        "  " + ", ".join(f"{k}={v}" for k, v in diff["summary"].items() if v),
        f"  clean: {diff['clean']}",
    ]
    for family, statuses in sorted(diff["families"].items()):
        detail = ", ".join(f"{k}={v}" for k, v in sorted(statuses.items()))
        lines.append(f"    {family}: {detail}")
    problems = [row for row in report["trials"] if row["status"] in {"disagree", "harness-error", "unsupported"}]
    if problems:
        lines.append("  Problem trials:")
        for row in problems:
            lines.append(f"    #{row['index']} [{row['family']}] {row['status']}: a={row.get('a')} b={row.get('b')}")
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="python -m runner differential")
    parser.add_argument("--adapter-a", required=True, help="first adapter command")
    parser.add_argument("--adapter-b", required=True, help="second adapter command")
    parser.add_argument("--seed", type=int, default=0, help="deterministic generator seed")
    parser.add_argument("--count", type=int, default=200, help="number of generated trials")
    parser.add_argument("--report", help="write machine-readable report JSON")
    parser.add_argument("--keep-fixtures", action="store_true", help="keep materialized fixtures")
    args = parser.parse_args(argv)

    report = run_differential(
        adapter_a=args.adapter_a,
        adapter_b=args.adapter_b,
        seed=args.seed,
        count=args.count,
        keep_fixtures=args.keep_fixtures,
    )
    if args.report:
        write_report(args.report, report)
    print(human_summary(report))
    return 0 if report["differential"]["clean"] else 1
