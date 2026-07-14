#!/usr/bin/env python3
"""
ACIF conformance suite — vector value generator (Informative)

Computes the byte-exact hash values for every `<computed>` placeholder in
../vectors/*.yaml and substitutes them in place, in document order. The
fixture definitions below mirror the catalog fixtures exactly; if a catalog
fixture changes, change the matching computation here and re-run.

The published (filled) vectors are the normative authority. This script is
informative tooling.

Usage:  python3 generate_vectors.py [--check]
        --check: verify placeholders are already filled with these values.
"""
from __future__ import annotations

import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from acif_hash import (  # noqa: E402
    body_hash_multi,
    body_hash_single,
    jcs,
    metadata_hash,
    sidecar_only_body_hash,
)

VEC = Path(__file__).parent.parent / "vectors"


def hook_block(event: str, handlers: list, **extra) -> dict:
    """Canonical hook extension block with materialized defaults."""
    block = {"event": event, "handlers": handlers, "blocking": False}
    block.update(extra)
    return block


def cmd_handler(scripts: list, **extra) -> dict:
    h = {"type": "command", "scripts": sort_scripts(scripts), "async": False}
    h.update(extra)
    return h


def sort_scripts(scripts: list) -> list:
    """[ACIF-HOOK] §9.3 — scripts sorted by raw UTF-8 byte order of each
    entry's own canonical JSON serialization."""
    return sorted(scripts, key=lambda e: jcs(e))


def compute() -> dict[str, list[str]]:
    """Return {catalog filename: [computed values in document order]}."""
    out: dict[str, list[str]] = {}

    # ── core.yaml ────────────────────────────────────────────────────────────
    tv1 = body_hash_single(b"---\ndescription: demo\n---\nUse this skill to demo hashing.\n")
    tv2 = metadata_hash({
        "kind": "skill",
        "id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
        "display_name": "Demo Skill",
    })
    tv9_section = {
        "kind": "command",
        "id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
        "display_name": "Review PR",
        "version": "1.2.0",
    }
    tv9_bytes = jcs(tv9_section).decode("utf-8")
    tv9_hash = metadata_hash(tv9_section)
    # TV-3 sanity check (already literal in the catalog)
    ns = uuid.UUID("93516344-00e5-419b-a230-6e8b1d02f87d")
    ref = uuid.uuid5(ns, "https://github.com/obra/superpowers\nsuperpowers")
    assert str(ref) == "d932cd6d-1c14-527d-b2e7-185c717b7a0d", f"TV-3 mismatch: {ref}"
    # TV-12 — root-only sidecar exclusion in bytes
    tv12_base = {"SKILL.md": b"Body prose.\n", "sub/acif-sidecar.yaml": b"kind: skill\n"}
    tv12_a = body_hash_multi(tv12_base, "SKILL.md")
    tv12_b = body_hash_multi({**tv12_base, "acif-sidecar.yaml": b"kind: skill\n"}, "SKILL.md")
    assert tv12_a == tv12_b, "root sidecar must not enter body_hash"
    tv12_c = body_hash_multi({
        "SKILL.md": b"Body prose.\n",
        "sub/acif-sidecar.yaml": b"kind: skill\nid: f47ac10b\n",
    }, "SKILL.md")
    assert tv12_c != tv12_a, "subdirectory sidecar must enter body_hash"
    out["core.yaml"] = [tv1, tv2, tv9_bytes, tv9_hash, tv12_a, tv12_c]

    # ── mcp.yaml ─────────────────────────────────────────────────────────────
    mcp_stdio = {"servers": {"demo": {
        "type": "stdio", "command": "npx", "args": ["-y", "@demo/mcp-server"],
    }}}
    mcp_http = {"servers": {"demo": {
        "type": "streamable-http", "url": "https://mcp.example.com/sse-endpoint",
    }}}
    h_stdio = sidecar_only_body_hash(mcp_stdio, {})
    h_http = sidecar_only_body_hash(mcp_http, {})
    out["mcp.yaml"] = [h_stdio, h_http, h_stdio]   # TV-MCP-a (x2), TV-MCP-d

    # ── platform.yaml ────────────────────────────────────────────────────────
    files_i = {
        "hooks/base.sh": b"#!/bin/sh\necho base\n",
        "hooks/win.cmd": b"@echo off\r\necho win\r\n",
        "hooks/lin.sh": b"#!/bin/sh\necho lin\n",
        "hooks/mac.sh": b"#!/bin/sh\necho mac\n",
    }
    block_i = hook_block("before_tool_execute", [cmd_handler([
        {"type": "file", "path": "hooks/base.sh"},
        {"type": "file", "path": "hooks/win.cmd", "os": ["windows"]},
        {"type": "file", "path": "hooks/lin.sh", "os": ["linux"]},
        {"type": "file", "path": "hooks/mac.sh", "os": ["darwin"]},
    ])])
    h_i = sidecar_only_body_hash(block_i, files_i)

    # TV-PLATFORM-i2 — linux + osx keys share one path; §7.4 identity-merge
    # yields a single constrained entry with the sorted os union.
    files_i2 = {
        "hooks/base.sh": b"#!/bin/sh\necho base\n",
        "hooks/win.cmd": b"@echo off\r\necho win\r\n",
        "hooks/unix.sh": b"#!/bin/sh\necho unix\n",
    }
    block_i2 = hook_block("before_tool_execute", [cmd_handler([
        {"type": "file", "path": "hooks/base.sh"},
        {"type": "file", "path": "hooks/unix.sh", "os": ["darwin", "linux"]},
        {"type": "file", "path": "hooks/win.cmd", "os": ["windows"]},
    ])])
    h_i2 = sidecar_only_body_hash(block_i2, files_i2)

    files_q = {"hooks/run.sh": b"#!/bin/sh\necho ok\n"}
    block_q_base = hook_block("before_tool_execute", [cmd_handler([
        {"type": "file", "path": "hooks/run.sh", "os": ["linux"]},
    ])])
    block_q_flip = hook_block("before_tool_execute", [cmd_handler([
        {"type": "file", "path": "hooks/run.sh", "os": ["windows"]},
    ])])
    h_q_base = sidecar_only_body_hash(block_q_base, files_q)
    h_q_flip = sidecar_only_body_hash(block_q_flip, files_q)
    assert h_q_base != h_q_flip

    files_q2 = {"hooks/win.cmd": b"@echo off\r\necho hi\r\n"}
    block_q2 = hook_block("before_tool_execute", [cmd_handler([
        {"type": "inline", "content": "#!/bin/sh\necho hi\n", "os": ["darwin", "linux"]},
        {"type": "file", "path": "hooks/win.cmd", "os": ["windows"]},
    ])])
    h_q2 = sidecar_only_body_hash(block_q2, files_q2)
    out["platform.yaml"] = [h_i, h_i2, h_q_base, h_q_flip, h_q2]

    # ── hook.yaml ────────────────────────────────────────────────────────────
    block_g = hook_block("before_tool_execute", [cmd_handler([
        {"type": "inline", "content": "#!/bin/sh\nexit 0\n"},
    ])])
    out["hook.yaml"] = [sidecar_only_body_hash(block_g, {})]

    # ── skill.yaml ───────────────────────────────────────────────────────────
    single = body_hash_single(b"Use this to demo classification.\n")
    multi = body_hash_multi({
        "SKILL.md": b"Use this to demo classification.\n",
        "scripts/run.sh": b"#!/bin/sh\necho hi\n",
    }, "SKILL.md")
    # TV-SKILL-n — multi-file entry-file frontmatter strip
    n1 = body_hash_multi({
        "SKILL.md": b"---\ndescription: one\n---\nProse body.\n",
        "scripts/run.sh": b"#!/bin/sh\necho hi\n",
    }, "SKILL.md")
    n2 = body_hash_multi({
        "SKILL.md": b"---\ndescription: two\n---\nProse body.\n",
        "scripts/run.sh": b"#!/bin/sh\necho hi\n",
    }, "SKILL.md")
    assert n1 == n2, "frontmatter must not move a multi-file body_hash"
    out["skill.yaml"] = [single, multi, n1]

    # ── rule.yaml ────────────────────────────────────────────────────────────
    out["rule.yaml"] = [
        body_hash_single(b"Prefer functional patterns.\n"),
        body_hash_single(b"Follow @security.md and @~/company-standards.md.\n"),
    ]

    # ── command.yaml ─────────────────────────────────────────────────────────
    out["command.yaml"] = [
        body_hash_single(b"Review PR $ARGUMENTS carefully.\n"),
        body_hash_single(b"Open $ARGUMENTS now.\n"),
        body_hash_single(b"Do the task with $ARGUMENTS.\n"),
    ]

    return out


def main() -> int:
    check = "--check" in sys.argv
    values = compute()
    failures = 0
    for fname, vals in values.items():
        path = VEC / fname
        text = path.read_text(encoding="utf-8")
        if check:
            for v in vals:
                if v not in text:
                    print(f"MISSING in {fname}: {v[:48]}...")
                    failures += 1
            if '"<computed>"' in text:
                print(f"UNFILLED placeholder remains in {fname}")
                failures += 1
            continue
        for v in vals:
            # Quoted form only: bare <computed> also appears in catalog
            # header comments, which must not mask a value/placeholder
            # count mismatch.
            if '"<computed>"' not in text:
                print(f"ERROR: more values than placeholders in {fname}")
                return 1
            # YAML quoting: single-quote values containing double quotes
            quoted = f"'{v}'" if '"' in v else f'"{v}"'
            text = text.replace('"<computed>"', quoted, 1)
        if '"<computed>"' in text:
            print(f"ERROR: unfilled placeholders remain in {fname}")
            return 1
        path.write_text(text, encoding="utf-8")
        print(f"filled {fname}: {len(vals)} value(s)")
    if check and failures == 0:
        print("check OK: all computed values present, no placeholders remain")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
