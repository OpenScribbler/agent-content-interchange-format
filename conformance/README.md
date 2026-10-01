# ACIF Conformance Suite

**Status:** Draft, tracks the ACIF 0.1.x specification set.

This directory publishes the ACIF conformance test vectors. Per every ACIF
specification's conformance clause: **the vectors are normatively
authoritative over prose** — an implementation that contradicts a published
vector is non-conformant regardless of any prose reading. The scripts under
`reference/` are informative; when a script and a vector disagree, the vector
is correct and the script has a bug.

## Layout

```
conformance/
  vectors/           # normative — one YAML catalog per family
    core.yaml        # TV-1..TV-13 + TV-L2-* + TV-L3-* (record, envelope & pack layer)
    hook.yaml        # TV-HOOK-*   ([ACIF-HOOK] Appendix C)
    platform.yaml    # TV-PLATFORM-* ([ACIF-HOOK] Appendix C; type-general)
    skill.yaml       # TV-SKILL-*  ([ACIF-SKILL] Appendix B)
    rule.yaml        # TV-RULE-*   ([ACIF-RULE] Appendix B)
    command.yaml     # TV-COMMAND-* ([ACIF-COMMAND] Appendix B)
    agent.yaml       # TV-AGENT-*  ([ACIF-AGENT] Appendix A)
    mcp.yaml         # TV-MCP-*    ([ACIF-MCP] Appendix A)
    uri.yaml         # TV-URI-*    ([ACIF-REGISTRY] Appendix A)
    fresh.yaml       # TV-FRESH-*  ([ACIF-REGISTRY] Appendix A)
    render.yaml      # TV-RENDER-* ([ACIF-RENDER] Appendix A)
    install.yaml     # TV-INSTALL-* ([ACIF-INSTALL] Appendix B)
  reference/         # informative — reference implementation + generator
    acif_hash.py     # body_hash / metadata_hash / sidecar-only preimage reference
    generate_vectors.py  # fills computed hash values into the catalogs
  runner/            # conformance runner; DESIGN.md + PROTOCOL.md
  adapters/          # development adapters
  evidence/          # published implementation runs and differential reports
  suite-manifest.yaml        # suite number, catalog hashes, change history
  capability-vocabulary.yaml # export: capability keys per content type
  diagnostic-ids.yaml        # export: each L1 spec's diagnostic identifiers by class
  install-entry-points.yaml  # export: [ACIF-INSTALL] Appendix A.2 matrix
  source-mechanisms.yaml     # export: hook and rule source-mechanism tokens
```

The exports are derived from spec sections and kept in sync by the runner
selftest; downstream tools diff against them rather than parsing spec prose.

## Quickstart

The runner needs Python 3 with PyYAML. Run it from the repository root.

```bash
# Check the suite itself: catalog hashes, export sync, runner self-tests.
python3 -m conformance.runner selftest

# Run the vectors against an implementation's adapter.
python3 -m conformance.runner --adapter "<command that starts your adapter>" \
  --report report.json

# Limit the run to some scopes or vectors.
python3 -m conformance.runner --adapter "<cmd>" --scope core --scope hook
python3 -m conformance.runner --adapter "<cmd>" --only TV-HOOK-k

# Compare two implementations on generated inputs.
python3 -m conformance.runner differential --adapter-a "<cmd A>" \
  --adapter-b "<cmd B>" --report differential.json
```

An adapter speaks the line protocol in [`runner/PROTOCOL.md`](runner/PROTOCOL.md):
a `hello` handshake that claims scopes, then one JSON request per line.
`adapters/reference.py` is a partial development fixture that exercises the
harness (`--adapter "python3 -m conformance.adapters.reference"`); it is not
an implementation and fails some vectors by design.

## Vector format

Each catalog is a YAML list. Every vector carries:

| Field | Meaning |
|---|---|
| `id` | Stable vector ID (`TV-<FAMILY>-<letter>`, matching the owning spec appendix) |
| `spec` | Owning spec section(s) the vector enforces |
| `harness` | `static` \| `mock-transport` \| `mock-crawl` — which harness family runs it |
| `description` | What the vector proves |
| `input` | The fixture: inline file trees (`files: {path: content}`), source blocks, URIs, timestamps, or render contexts |
| `expect` | The required outcome: canonical form assertions, `error` (a named `acif.*` identifier), `evaluation` results, hash equalities/inequalities, or byte-exact hash values |

Hash-bearing `expect` values are computed by `reference/generate_vectors.py`
and committed into the catalogs; a value of `"<computed>"` marks a slot the
generator has not yet filled and is a defect in the suite, not a free pass.

Inline file-tree fixtures use literal block scalars; content is written with
`\n` line endings unless the vector is explicitly about line-ending
normalization, in which case escaped byte sequences are spelled out in the
description and encoded with YAML double-quoted escapes.

## Harness families

Three harness families exist, and conformance MUST NOT be claimed on the static
family alone where a spec requires more ([ACIF-REGISTRY] §5):

- **static** — pure-function vectors: bytes in, canonical form / hash /
  identifier out. No I/O beyond the fixture.
- **mock-transport** — vectors that require an HTTP double (redirect chains,
  downgrade detection, chain limits) for the `source_uri` pipeline.
- **mock-crawl** — vectors that require two crawl passes over changing
  registry state (re-crawl stability, freshness re-stamping).

## ID stability

Vector IDs are stable once published. The lettered IDs correspond one-to-one
with the family definitions in the owning spec appendices; a future vector
added to a family takes the next unused letter (or a `-2` suffix once letters
exhaust) and never renumbers existing vectors.
