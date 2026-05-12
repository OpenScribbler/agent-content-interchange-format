# SHAPE — Current Design Snapshot

> Working document. Captures manifest design decisions made so far.
> Not a spec — a snapshot. Promote to individual spec files once stable.

---

## Common Envelope

Fields shared by all content types. Present in every manifest regardless of `kind`.

```yaml
kind: hook | skill | rule | command | agent | mcp_config  # required
id: "f47ac10b-58cc-4372-a567-0e02b2c3d479"               # required — UUID v4, generated once, never changes
display_name: "Session Start: Inject Prompt"             # required — human-readable, for display only
version: "5.1.0"                                         # optional — inherits from package if absent
description: "Injects system context at session start."  # optional
license:                                                 # optional
  spdx: MIT                                              # required if license block present
  file: LICENSE                                          # optional — relative path in repo
  url: https://example.com/license.txt                  # optional — absolute URL (for externally hosted)
```

---

## Carrier Rules

Sidecars are the universal primary artifact for every content type. Frontmatter is an optional supplementary layer for content types that support it.

| Content type | Primary carrier | Publisher frontmatter |
|---|---|---|
| hook, mcp_config | Sidecar file (always generated) | Not possible — harness owns `settings.json`/`mcp.json`; no inline surface exists |
| skill, rule, agent, command | Sidecar file (always generated) | Opt-in — hand-authored or CI-populated alongside the sidecar |

**Data flows sidecar → frontmatter, never the reverse.** The frontmatter CI reads the canonical sidecar and projects its values into the source file. Frontmatter is intentionally redundant with the sidecar; that redundancy serves portability (a copied file carries its own metadata).

For sidecars, `kind` is required — the file has no implicit type.
For frontmatter, `kind` is optional (inferred from the canonical filename, e.g., `SKILL.md` → `kind: skill`).

---

## Hook Extension Block

Appended below the common envelope when `kind: hook`.

```yaml
hook:
  event: session_start          # required — canonical HIF event name; distinct from display_name

  scripts:                      # required — what the harness executes when the hook fires
    - type: file
      path: hooks/session-start-inject-prompt
      os: [linux, darwin]       # optional — omit if OS-agnostic
      arch: [amd64, arm64]      # optional — omit if arch-agnostic (most hooks are)
    - type: file
      path: hooks/run-hook.cmd
      os: [windows]
    # inline variant:
    # - type: inline
    #   content: |
    #     #!/bin/bash
    #     echo "hello"
    #   os: [linux, darwin]

  auxiliary_files:              # optional — files a script loads at runtime (not harness-invoked)
    - path: hooks/shared-utils.sh

  blocking: false               # optional — default false

  requires:                     # optional — capability requirements (replaces provider list)
    matcher_patterns: [event_name]
    json_io_protocol: false
```

---

## Design Decisions

| # | Decision | Rationale |
|---|---|---|
| 1 | `kind` not `content_type` | Shorter; established precedent (Kubernetes); works as a discriminant |
| 2 | `id` is UUID v4, generated once | Only truly immutable option; not derived from any field that can change |
| 3 | `display_name` not `name` | Makes display-only purpose explicit; avoids conflicts with type-specific `name` fields |
| 4 | `license` is an object | `spdx` for machine-readable processing; `file` for repo-hosted text; `url` for externally hosted — both optional, either sufficient |
| 5 | `scripts` is an array | Supports OS-specific entrypoints (bash + `.cmd`) in a single manifest; supports inline scripts |
| 6 | `os` + `arch` not `platform` | "Platform" is overloaded (OS, harness, LLM, architecture). Separate fields are unambiguous. |
| 7 | `auxiliary_files` = runtime deps | Files the script loads, not what the harness invokes. Harness-invoked files belong in `scripts`. |
| 8 | `requires` not `providers` | Capability requirements are stable; provider lists are brittle and don't reflect partial support. Registry computes provider compatibility from its capability matrix. |
| 9 | `event` is distinct from `display_name` | `event` = WHEN (lifecycle trigger); `display_name` = WHAT (behavior description). A repo can have two hooks on the same event — they need distinct, meaningful names. |
| 10 | Sidecar is the universal primary carrier | Sidecar files are generated for every content type without exception. For hooks and mcp_configs the sidecar is the only input surface. For skills, rules, agents, and commands, frontmatter is an optional supplementary layer — hand-authored or CI-populated. The sidecar is always canonical; frontmatter reflects it, not the other way around. Registries MUST NOT write to source files. |
| 11 | Two-section L2 record (`publisher_section` + `registry_section`) | Structure is the provenance. No merge layer, no per-field markers. `publisher_section` = registry's faithful observation of frontmatter; `registry_section` = computed fields. |
| 12 | `body_hash` is distinct from any external integrity hash | Body hash covers content body bytes only (frontmatter stripped, LF-normalized). An external integrity system may compute its own hash over different bytes. The two are not interchangeable and the spec does not equate them. |
| 13 | No external system named in spec text | The spec defines a slot (`attestation_hash` in `registry_section`) for an external integrity/attestation hash. What fills that slot is an implementation choice. No specific system is named. |
| 14 | Sidecar binding by `body_hash` (single-file items) | The sidecar's `body_hash` uniquely identifies the content file it annotates. No naming convention required. Multi-file binding deferred (OQ-2). |
| 15 | Frontmatter CI reconciliation: block on conflict, overwrite on opt-in | When the frontmatter CI finds an ACIF field already present in a source file that conflicts with the canonical sidecar value, the default behavior is to block the build and surface the conflict — no silent overwrites. Auto-overwrite (with logging) is available via an explicit CI input (`conflict-resolution: overwrite`). Missing ACIF fields are added silently (non-destructive). Non-ACIF fields always pass through untouched regardless of setting. |

---

## Registry Section Schema

The `registry_section` of every L2 record. Always present; never sourced from publisher frontmatter.

```yaml
registry_section:
  body_hash:                          # REQUIRED — SHA-256 over content body, frontmatter stripped, LF-normalized
    algorithm: sha256                 # single-file items only (see OQ-2)
    value: "abc123..."
  metadata_hash:                      # REQUIRED when publisher_section is present
    algorithm: sha256                 # SHA-256 over canonical frontmatter (keys sorted, comments stripped)
    value: "def456..."
  attestation_hash:                   # OPTIONAL — hash from an external integrity/attestation system
    algorithm: sha256                 # populated by that system; distinct algorithm and byte sequence from body_hash
    value: "ghi789..."                # what system produced this is an implementation detail, not named here
  fetched_at: "2026-05-11T18:00:00Z" # REQUIRED — RFC 3339 UTC, set at crawl time (not sidecar generation time)
  expires: "2026-05-14T18:00:00Z"    # OPTIONAL — default staleness: 72 hours from fetched_at if absent
  source_uri: "https://..."          # REQUIRED — canonical fetch URL; used to override copy-invalidated frontmatter fields
  publisher_declared: true           # REQUIRED — true iff publisher_section was populated from observed frontmatter
  publisher_metadata: "declared"     # OPTIONAL INFORMATIVE — declared | auto-generated | unknown
                                     # NOTE: "declared" means the registry observed frontmatter at crawl time.
                                     # It does NOT mean the publisher cryptographically attested these fields.
```

**Registries MUST NOT write to source files.** All registry-generated metadata lives in sidecars only.

---

## Open Questions

| # | Status | Question |
|---|---|---|
| OQ-1 | **Resolved (single-file only)** | Sidecar binding uses `body_hash` as the identity key. The sidecar's `body_hash` matches the hash of the content file it annotates — no naming convention required. Two hooks on the same event have different script bodies → different hashes → unambiguous binding. Multi-file binding deferred to OQ-2. |
| OQ-2 | **Explicitly deferred** | Content hash boundary for multi-file items: which files are in scope for `body_hash`? Until resolved, `body_hash` is normative for single-file items only. Implementations MUST NOT self-derive a multi-file algorithm. |
| OQ-3 | **Open** | Package/bundle concept — individual registry entries need a way to reference their parent package so install tools can group them. Not yet modeled. |
| OQ-4 | **Open** | Version inheritance — when does an item use its own `version` vs. inherit from the package? |
| OQ-5 | **Addressed** | Registry transparency: `publisher_declared` (bool, REQUIRED) + `publisher_metadata` (enum, OPTIONAL INFORMATIVE). See registry section schema above. |
| OQ-6 | **Open** | `os`/`arch` defaults — when `os` is absent from a script entry, does it mean "all OS" or "unspecified"? |
| OQ-7 | **Open** | `requires` vocabulary — complete canonical list of hook capability keys. Not yet formally mapped to the `requires` block. |
| OQ-8 | **Open** | Skill `supplementary_files` — skills can cross-reference other files. No mechanism declared yet. |
| OQ-9 | **Open** | Two-tier freshness interop — when an external attestation manifest has its own expiry and the sidecar `expires` differ, which takes precedence for staleness determination? |
