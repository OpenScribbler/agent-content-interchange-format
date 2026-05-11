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

Where the manifest fields live depends on the content type:

| Content type | Carrier | Reason |
|---|---|---|
| hook, mcp_config | Sidecar file (e.g., `session-start.hook.yaml`) | Harness owns the top-level config schema (`settings.json`, `mcp.json`) — inline metadata isn't possible |
| skill, rule, agent, command | YAML frontmatter in the content file | Publisher authors the file directly — frontmatter is the natural carrier |

For frontmatter, `kind` is optional (inferred from the canonical filename, e.g., `SKILL.md` → `kind: skill`).
For sidecars, `kind` is required — the file has no implicit type.

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

---

## Open Questions

Issues the obra exercise surfaced that the spec hasn't resolved yet.

| # | Question | Where it surfaced |
|---|---|---|
| OQ-1 | **Sidecar binding** — how does a sidecar declare which specific hook it annotates in a multi-hook repo? (naming convention? explicit `annotates:` field? path co-location?) | hook trace |
| OQ-2 | **Content hash boundary** — which files are included in the hash? The script only? All files in `scripts` + `auxiliary_files`? The whole `hooks/` directory? | hook + skill trace |
| OQ-3 | **Package/bundle concept** — individual registry entries need a way to reference their parent package so install tools can group them. Not yet modeled. | obra (14 skills + 1 hook in one package) |
| OQ-4 | **Version inheritance** — when does an item use its own `version` vs. inherit from the package? | obra (package version only; no per-item versions) |
| OQ-5 | **`publisher_metadata_source`** — registry transparency: was L2 metadata publisher-supplied or auto-generated? Install tools making trust decisions need to know. | registry trace |
| OQ-6 | **`os`/`arch` defaults** — when `os` is absent from a script entry, does it mean "all OS" or "unspecified"? | `run-hook.cmd` platform handling |
| OQ-7 | **`requires` vocabulary** — complete canonical list of hook capability keys (from HIF / syllago `recognize_hooks.go`). Not yet formally mapped to the `requires` block. | requires block |
| OQ-8 | **Skill `supplementary_files`** — skills can cross-reference other files (`@testing-anti-patterns.md` in TDD skill). No mechanism declared yet. | skill trace |
