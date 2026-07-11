# SHAPE — Current Design Snapshot

> Working document. Captures manifest design decisions made so far.
> Not a spec — a snapshot. Promote to individual spec files once stable.

---

## Common Envelope

Fields shared by all content types. Present in every manifest regardless of `kind`.

```yaml
kind: hook | skill | rule | command | agent | mcp_config | pack  # required
id: "f47ac10b-58cc-4372-a567-0e02b2c3d479"               # required — UUID v4, generated once, never changes
display_name: "Session Start: Inject Prompt"             # required — human-readable, for display only
version: "5.1.0"                                         # OPTIONAL — literal-or-absent. When declared, MUST be valid SemVer 2.0.0 (Decision #20). NO inheritance (Decision #16). Pack version lives on the pack record only.
description: "Injects system context at session start."  # optional
license:                                                 # optional
  spdx: MIT                                              # required if license block present
  file: LICENSE                                          # optional — relative path in repo
  url: https://example.com/license.txt                  # optional — absolute URL (for externally hosted)
pack_id: "a1b2c3d4-..."                                  # OPTIONAL — UUIDv4 publisher-declared pack membership. See Decision #18. Lives in publisher_section.
```

**Forbidden item fields** (Decision #16, enforceable by lint): `effective_version`, `derived_version`, `pack_inherited_version`, `resolved_version`. The presence of any of these on an item record is a conformance error.

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

  requires: {}                  # OPTIONAL — empty/absent for v0.1 (Decision #23).
                                # Of nine Syllago canonical hook capability keys, three are
                                # DERIVABLE via per-key D_K predicates (handler_types over
                                # Hooks[*].Type with closed enum {command, http, prompt, agent}
                                # pinned per Decision #29; matcher_patterns over Matcher with
                                # canonical event vocab pinned per Decision #29; async_execution
                                # over Hooks[*].Async). Six are OUT-OF-SCOPE-AT-L1: hook_scopes
                                # (install-location), and decision_control / input_modification /
                                # json_io_protocol / context_injection / permission_control (all
                                # under script-body opacity — capability semantics live in script
                                # body bytes that the canonical wiring carries opaquely).
                                # Runtime hints (python, node, powershell) deferred to roadmap.
                                # See panel/hooks-requires-consensus.md.

  activation_target:            # optional — present when this hook activates a skill (Decision #21)
    skill:
      id: "550e8400-..."        # required — item UUIDv4 of the target skill; load-bearing cross-reference key
      name: "tdd-workflow"      # optional — human-readable advisory only; renames don't break the UUID reference
```

---

## Skill Extension Block

Appended below the common envelope when `kind: skill`.

```yaml
skill:
  activation:                   # optional — defaults MATERIALIZED at canonicalization (Decision #21,
                                # as amended): type: auto and user_invocable: true when absent.
                                # body_hash is computed post-materialization; validators MUST NOT
                                # re-apply defaults (parallel to Decision #24).
    type: manual | auto | hook  # required when activation block present
                                # manual: user explicitly invokes (e.g., /skillname)
                                # auto:   model decides based on description (current default behavior)
                                # hook:   a hook makes the activation decision; see activation_target on hook side
    user_invocable: true        # OPTIONAL — default true; orthogonal to type (Decision #21 amendment).
                                # false removes the skill from user-invocation surfaces (e.g., /menus)
                                # without affecting model invocation. The post-materialization
                                # resolves-to-false state is the installer-side filtering signal.
    hook_ref:                   # required when type: hook; absent for manual/auto
      id: "f47ac10b-..."        # required — item UUIDv4 of the activating hook
      name: "skill-activator"   # optional — human-readable advisory only

  requires: {}                  # OPTIONAL — empty/absent for v0.1 (Decision #23).
                                # Of fifteen Syllago canonical skill capability keys, four are
                                # DERIVABLE via per-key D_K predicates — auto_invocable,
                                # disable_model_invocation, and user_invocable (all over the
                                # post-materialization activation block), plus
                                # skill_bundled_resources (via Decision #19's single/multi-file
                                # classification predicate, exclusion-list form). Eleven are
                                # OUT-OF-SCOPE-AT-L1: five meta-property (display_name,
                                # description, license, compatibility, metadata_map), one
                                # common-envelope (version), three install-location
                                # (project/global/shared scope → install_scope_capabilities),
                                # two discovery (canonical_filename, custom_filename —
                                # Decision #22). Latent SkillMeta fields (allowed-tools /
                                # model / bundled hooks) are OQ-10 candidates, not requires keys.
                                # See panel/skills-requires-consensus.md.
```

**Canonical truth for hook → skill activation lives on the hook** (`activation_target`). The skill's `activation.type: hook` is a discovery convenience; the `hook_ref` on the skill is optional (the registry can resolve the reverse mapping from hook records).

**Skill discovery** (Decision #22): publishers SHOULD ship skills as `SKILL.md` inside a skill-named directory. Three discovery tiers apply:

1. **Publisher-declared** — pack manifest declares `skill_paths: ["./skills/", "./advanced/"]`. Registry uses these.
2. **Heuristic + filename fallback** — registry scans known dirs; accepts `SKILL.md` (canonical), `*.md` with `kind: skill` frontmatter (heuristic), or bare `.md` with filename → `name` (fallback).
3. **Non-conformant** — arbitrary layouts with no manifest and no frontmatter are out of scope; publisher must conform.

---

## Rule Extension Block

Appended below the common envelope when `kind: rule`.

```yaml
rule:
  activation:                   # optional — default MATERIALIZED at canonicalization (Decision #30):
                                # mode: always when the block is absent. body_hash is computed
                                # post-materialization; validators MUST NOT re-apply defaults
                                # (parallel to Decisions #24/#21).
    mode: always | glob | model_decision | manual
                                # required when activation block present — Decision #30 closed enum
                                # (ACIF-originated vocabulary; block present without mode →
                                # acif.rule.activation_mode_missing; unknown/whitespace value →
                                # acif.rule.activation_mode_invalid; exact byte match, no trim/fold)
    globs: ["src/**/*.ts"]      # required iff mode: glob (else acif.rule.glob_mode_without_globs);
                                # forbidden otherwise (acif.rule.globs_without_glob_mode)

  requires: {}                  # OPTIONAL — empty/absent for v0.1 (Decision #23).
                                # Of five Syllago canonical rule capability keys, one is DERIVABLE
                                # (activation_mode via D_K: activation.mode ∈ {glob, model_decision,
                                # manual}, positive-set form, post-materialization). Four are
                                # OUT-OF-SCOPE-AT-L1: file_imports (prose-body opacity; the
                                # strongest requires-candidate the OQ-7 walks surfaced — rejected
                                # 2:2→Holden under the out-of-band guardrail; coupled to unified
                                # OQ-8, becomes DERIVABLE if a reference grammar is ever pinned),
                                # cross_provider_recognition (provider-side format recognition),
                                # auto_memory (provider-runtime feature), hierarchical_loading
                                # (provider-matrix fact → provider_capability_coverage projection).
                                # See panel/rules-requires-consensus.md.
```

---

## Pack Extension Block

Appended below the common envelope when `kind: pack`. Pack records MAY be publisher-declared (authored sidecar at repo root) or registry-inferred (generated from inference algorithm v0.1).

```yaml
kind: pack
id: "f47ac10b-58cc-4372-a567-0e02b2c3d479"   # UUIDv4 if publisher-declared; UUIDv5 if registry-inferred
display_name: "superpowers"                  # required — mutable; not the stable identifier
version: "5.1.0"                             # OPTIONAL — pack's own version. Lives ONLY on the pack record, never propagates to items.
description: "Skills and hooks for AI coding tools"
license:
  spdx: MIT
repository_url: "https://github.com/obra/superpowers"  # required — canonical fetch URL

pack:
  source_kind: declared | inferred           # required — declared (publisher authored) or inferred (registry computed)
  canonical_address: "obra/superpowers"      # required — <owner>/<display_name> form for user-facing URLs
  inference_version: "v0.1"                  # required iff source_kind=inferred — which algorithm produced this record
```

**Pack `items` list lives in `registry_section`, not here.** The items list is OUTPUT of the pack-membership predicate (Decision #18), computed by the registry on every relevant change. Publishers do not author it.

**Pack-membership predicate:**

```
item M ∈ pack P  iff
    M.publisher_section.pack_id == P.id
  OR
    (M.publisher_section.pack_id absent AND M.registry_section.inferred_pack_id == P.id)
```

Declared wins over inferred when both exist and differ.

---

## MCP Extension Block

Appended below the common envelope when `kind: mcp_config`. The block carries the canonical MCP wiring (server definitions) plus any author-declared non-derivable capabilities in `requires`.

```yaml
mcp:
  servers:                              # required when block has content — map: server name → wiring
    figma:
      command: "npx"                    # stdio transport (mutex with url; see Decision #24)
      args: ["-y", "@figma/mcp-server"]
      env: {FIGMA_TOKEN: "${FIGMA_TOKEN}"}
      type: stdio                       # required in canonical form; materialized at canonicalization (Decision #24)
                                        # permitted values: stdio | sse | streamable-http
      # Additional fields per the canonical mcpServerConfig: oauth (opaque), cwd, headers, url,
      # includeTools, excludeTools, disabledTools, autoApprove, disabled, ...
      # ACIF carries the canonical envelope 1:1 to preserve round-trip with the canonicalizer.

  requires: {}                          # OPTIONAL — empty/absent for v0.1 (Decision #23).
                                        # All eight Syllago canonical MCP capability keys are
                                        # DERIVABLE per per-key predicates D_K over servers.* fields;
                                        # nothing goes in requires until a key lacks a D_K
                                        # (empty-as-steady-state, not a gap to fill).
```

**Server names** are within-item identifiers and SHOULD match `^[a-zA-Z][a-zA-Z0-9_-]*$`. Implementations MUST treat server names as opaque strings for cross-reference resolution within an item. The MCP protocol specification (2025-06-18) is silent on config-level server names; this constraint fills the gap without contradicting future MCP working-group decisions. If a future MCP revision defines server-name constraints at the configuration layer, those constraints take precedence over this recommendation.

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
| 12 | `body_hash` is distinct from any external integrity hash | Body hash covers content body bytes only (single-file: frontmatter stripped + LF-normalized; multi-file: MOAT v0.4.0 directory hash per Decision #19). An external integrity system may compute its own hash over different bytes. The two are not interchangeable and the spec does not equate them. |
| 13 | No external system named in spec text | The spec defines a slot (`attestation_hash` in `registry_section`) for an external integrity/attestation hash. What fills that slot is an implementation choice. No specific system is named. |
| 14 | Sidecar binding by `body_hash` | The sidecar's `body_hash` uniquely identifies the content (single file or directory) it annotates. No naming convention required. Multi-file binding resolved via Decision #19 (MOAT directory hash). |
| 15 | Frontmatter CI reconciliation: block on conflict, overwrite on opt-in | When the frontmatter CI finds an ACIF field already present in a source file that conflicts with the canonical sidecar value, the default behavior is to block the build and surface the conflict — no silent overwrites. Auto-overwrite (with logging) is available via an explicit CI input (`conflict-resolution: overwrite`). Missing ACIF fields are added silently (non-destructive). Non-ACIF fields always pass through untouched regardless of setting. |
| 16 | No version inheritance into item records | Item `version` is literal-or-absent. Pack `version` lives on the pack record only. Forbidden item fields: `effective_version`, `derived_version`, `pack_inherited_version`, `resolved_version`. Enforceable by lint and conformance test (TV-6, TV-7). Rationale: per-item version inheritance via derived fields is mostly UI text dressed up as a sync primitive — `body_hash` already serves the change-detection use case at zero author cost. Closes the silent-staleness regression path. |
| 17 | `body_hash` is the canonical per-item change signal, surfaced to all consumers | Sync, update, and discovery tools rely on `body_hash` as the canonical change signal. `version` is advisory; `body_hash` is dispositive. Registries MUST expose `body_hash` in all consumer-facing item responses and MUST provide a per-pack tuple-set endpoint returning `(item_id, body_hash, version_if_declared)` so sync tools poll one pack with one request instead of N item requests. Reinforces Decision #12 with a consumer-surface requirement. |
| 18 | Pack records are `kind: pack` L2 records with stable UUID identity | Pack membership predicate: an item belongs to pack P iff `publisher_section.pack_id == P.id` OR (`publisher_section.pack_id` absent AND `registry_section.inferred_pack_id == P.id`). `pack.registry_section.items` is OUTPUT of the predicate, not input. `pack_resolution` states: `declared | inferred | unresolved`. `display_name` is mutable; `id` (UUID) is immutable. Two paths: publisher-declared (`pack.id` is UUIDv4) and registry-inferred (`inferred_pack_id` is UUIDv5 over canonicalized `repository_url` + `display_name` with a spec-pinned namespace constant). Declared wins over inferred. Pack-less items are first-class. See `panel/pack-model-consensus.md` and Inference Algorithm v0.1 appendix. |
| 19 | `body_hash` algorithm is the MOAT v0.4.0 content-hash algorithm | ACIF adopts MOAT v0.4.0's content-hash algorithm verbatim as the canonical `body_hash` algorithm for both single-file and multi-file items. Key properties: per-file text/binary classification (closed `TEXT_EXTENSIONS` set + 8KB NUL-byte scan), UTF-8 BOM strip + CRLF→LF normalization for text files, raw bytes for binary, directory-level combine, VCS directories excluded, symlinks rejected at ingestion. **ACIF analog of MOAT's `moat-attestation.json` exclusion:** any registry-generated sidecar file stored inside the content directory is excluded from `body_hash` at root-only (circular-dependency guard). **Spec text:** the algorithm is defined inline (or by reference to a published algorithm document); MOAT is credited in informative text only — Decision #13's no-naming rule applies to the `attestation_hash` slot, not to ACIF's own `body_hash` algorithm. **Resolves OQ-2.** Reference impl: `../moat/reference/moat_hash.py`. Test vector generator: `../moat/reference/generate_test_vectors.py` (the test vectors are normatively authoritative; the reference script is informative). **Single/multi-file classification predicate (amended by skills walk):** an item's canonical body is **multi-file** iff, after excluding `{LICENSE*, README*, VCS directories, registry-generated sidecars}` (the root-only exclusion above, extended with `LICENSE*` and `README*`), the body directory contains at least one content file beyond the canonical entry file (e.g., `SKILL.md`); otherwise it is **single-file**. The `body_hash` algorithm is then applied to the classified body. The predicate is **content-type-general**: skill co-located resources AND bundled hook scripts (a command-type hook shipping `my_hook.py` beside the sidecar) are covered cases — editing a bundled hook script moves the change signal, as it must. Opacity-for-derivation (Decision #23 script-body opacity) and inclusion-in-hash are orthogonal; the predicate reinforces the hooks walk rather than reopening it. Without this predicate, two conformant registries could disagree on whether a skill directory's body is `SKILL.md` alone or the whole directory → non-deterministic `body_hash` (same defect class Decision #24 fixed for MCP transport defaults). Test vector: TV-SKILL-body-classification (general). See `panel/skills-requires-consensus.md` §5. |
| 20 | When `version` is declared, it MUST be valid SemVer 2.0.0 | Item `version` remains literal-or-absent (Decision #16). When present, the value MUST conform to SemVer 2.0.0. Patch level is permitted but not required — publishers MAY bump minor for any meaningful content change and effectively leave patch as `0`. Rationale: SemVer is the convention the surrounding tooling ecosystem already speaks (npm-style ranges, dependabot-style alerts). CalVer's same-day-edit ambiguity and MAJOR.MINOR's lack of independent value over "SemVer with patch unused" tip the balance. `body_hash` (Decision #17) remains the canonical change signal; `version` is the optional semantic-ordering and human-readability layer. Empirical grounding: [`research/repo-survey/round2-findings.md`](research/repo-survey/round2-findings.md) Versioning section. |
| 21 | Hook → skill activation cross-references use item UUIDv4 | A hook MAY declare `activation_target.skill.id` (UUIDv4 from SHAPE.md line 14) pointing to a skill whose injection it controls. A skill MAY declare `activation.type: manual | auto | hook` with an optional `hook_ref.id` when type is `hook`. Canonical truth lives on the hook (`activation_target`); the skill's `activation` block is a discovery convenience. Cross-references use item UUIDv4 — not `(pack_id, name)` — because UUIDv4 is globally unique by construction, renames don't break references, and no name-stability lint check is required. The `name` field on both sides is human-readable advisory only. This is the first cross-content-type relationship in ACIF; resolving it cleanly with item UUIDs sets the pattern for any future cross-references. Empirical grounding: `diet103/claude-code-infrastructure-showcase` `skill-rules.json` pattern. **Amended (skills walk):** the skill `activation` block adds `user_invocable: bool` (OPTIONAL, default `true`, orthogonal to `type`). The canonicalizer MUST materialize activation defaults at canonicalization time — `type: auto` when the activation block is absent; `user_invocable: true` when absent — and `body_hash` is computed **post-materialization**. Direct parallel of Decision #24's transport-type materialization: one rule, one place, applied before hashing, never re-applied at validation time. This makes the skills-walk `D_K` predicates well-defined on the absent-activation case without three-valued ambiguity; `user_invocable` uses *resolves-to-false* semantics (the signal an installer needs to filter user-invocable skills). Adopted over Remy's adoption-data objection (of surveyed providers, 6 support an equivalent, 7 explicitly don't, and only Claude Code carries an explicit frontmatter key) — preserved as informative caution in `panel/skills-requires-consensus.md` §4. |
| 22 | Three-tier skill discovery: publisher-declared > heuristic+frontmatter > non-conformant | Registries discover skill items via three tiers, in order: (1) **Publisher-declared** — pack manifest declares `skill_paths: ["./skills/", "./advanced/"]`; registry uses those. (2) **Heuristic + filename fallback** — registry scans known directories; accepts `SKILL.md` (canonical filename), any `*.md` with `kind: skill` frontmatter (heuristic), or bare `.md` with the filename used as `name` (fallback). (3) **Non-conformant** — arbitrary layouts with no manifest and no frontmatter are out of scope; publisher action required. Round 1 finding #8 showed ~⅓ of high-star repos ship no manifest at all — tier 2 is essential for adoption. Tier 1 is the "manual pointer" mechanism for publishers with non-standard layouts. Empirical grounding: [`research/repo-survey/round2-findings.md`](research/repo-survey/round2-findings.md) finding #17. |
| 23 | `requires` vocabulary is per-content-type; derivability via predicate `D_K` is the gating test | The `requires` block declares **author-declared capabilities** the harness must support to run the content. **Three-way disposition** for each candidate `requires` key K in a content type's canonical vocabulary: **DERIVABLE** — the spec specifies an explicit derivation predicate `D_K` over the canonical body; a conformance test applies `D_K` directly and asserts the result is one of `{derivable-true, derivable-false}`; K is dropped from `requires` because the predicate provides the signal. **D_K boolean discipline:** set-valued projections (e.g., the distinct values produced by a key, such as the set of transport types or hook event names) are NOT `D_K` outputs; they are computed projections surfaced via Decision #26's `derived_capabilities`. **OUT-OF-SCOPE-AT-L1** — K names a capability concern not author-declared at the L1 canonical layer (harness UX, install-context, meta-property, or **script-body opacity** — where the canonical wiring carries the capability-bearing artifact as opaque bytes, so the field-presence tiebreaker degenerates); recorded in informative rationale; NOT validator-testable. **`requires`-ELIGIBLE** — no `D_K` exists AND the capability IS author-declared; K is admitted to the content type's `requires` vocabulary. **Tiebreaker rule:** canonical field present → DERIVABLE (cite the field). Canonical field absent + capability would be authored if present → spec gap (add the field or admit to `requires`). Canonical field absent + capability is harness-decided or install-context-determined → OUT-OF-SCOPE-AT-L1. **Empty-as-steady-state:** the structural slot exists per content type (preserves cross-type uniformity), but empty `requires` is the EXPECTED steady state when canonical wiring fully exposes capability. Empty slots are NOT gaps to fill; the slot exists for the unauthored-but-required case (runtime hints, version pins, capabilities not yet expressed in any canonical field). **MCP application:** all eight Syllago canonical capability keys (`transport_types`, `oauth_support`, `env_var_expansion`, `tool_filtering`, `auto_approve`, `marketplace`, `enterprise_management`, `resource_referencing`) are DERIVABLE per per-key predicates over `servers.*` fields. `mcp.requires` is therefore empty/absent for v0.1. **Agents application:** all seven Syllago canonical agent capability keys resolve to DERIVABLE — `tool_restrictions` (`D_K: len(B.Tools)>0 OR len(B.DisallowedTools)>0`); `model_selection` (`D_K: B.Model != ""`); `per_agent_mcp` (`D_K: len(B.MCPServers)>0`); `subagent_spawning` (`D_K: contains(B.Tools, "agent")` — depends on Decision #25 canonical-tool-name pinning) — or OUT-OF-SCOPE-AT-L1 — `definition_format` (meta-property: canonical body IS the format); `invocation_patterns` (harness UX picker concern); `agent_scopes` (install-location-determined at L3/L4). `agents.requires` is therefore empty/absent for v0.1. **Hooks application:** Of nine Syllago canonical hook capability keys, three resolve to DERIVABLE — `handler_types` (`D_K: exists i. B.Hooks[i].Type != ""` with closed enum `{command, http, prompt, agent}` pinned per Decision #29; the set of distinct types is registry-projected to `derived_capabilities`); `matcher_patterns` (`D_K: B.Matcher != ""` with canonical event vocabulary pinned per Decision #29); `async_execution` (`D_K: exists i. B.Hooks[i].Async == true`). Six resolve to OUT-OF-SCOPE-AT-L1 — `hook_scopes` (install-location, parallel to agents' `agent_scopes`); `decision_control`, `input_modification`, `json_io_protocol`, `context_injection`, `permission_control` (all under script-body opacity — capability semantics live in script body bytes that the canonical wiring carries opaquely). Runtime hints (`python: ">=3.10"`, `node: ">=18"`, `powershell: true`) deferred to the ACIF roadmap. `hooks.requires` is therefore empty/absent for v0.1; three content types now resolve empty under Decision #23 (empty-as-steady-state holds three-for-three). **Skills application:** Of fifteen Syllago canonical skill capability keys, four resolve to DERIVABLE — `auto_invocable` (`D_K: B.activation absent OR B.activation.type == "auto"` — single-clause, post-default-materialization; the strawman's `description != ""` conjunct was dropped after three reviewers independently rejected it: description quality is a lint/moderation concern, not a derivability input); `disable_model_invocation` (`D_K: B.activation.type ∈ {manual, hook}` — activation-absent → materialized `auto` → derivable-false); `user_invocable` (`D_K: B.activation.user_invocable == false` — *resolves-to-false* semantics post-materialization; gated on the Decision #21 amendment, adopted); `skill_bundled_resources` (`D_K:` the canonical body classifies as multi-file under Decision #19's classification predicate — the exclusion list resolves the `LICENSE`+`README` false positive). Eleven resolve to OUT-OF-SCOPE-AT-L1 — `display_name`, `description`, `license`, `compatibility`, `metadata_map` (meta-property; `description` is load-bearing as a moderation/injection surface, not as a `requires` signal); `version` (common envelope, Decisions #16/#20); `project_scope`, `global_scope`, `shared_scope` (install-location → `install_scope_capabilities` projection); `canonical_filename`, `custom_filename` (discovery/filename meta — Decision #22). `skills.requires` is therefore empty/absent for v0.1 — four content types now resolve empty (empty-as-steady-state holds **four-for-four**, with the recorded caveat that the streak is "credible, getting thin"; rules — the prose-purest content type — is the load-bearing test of the principle). Latent `SkillMeta` fields (`AllowedTools` / `DisallowedTools` / `Model` / bundled `Hooks`) are named out-of-scope pending OQ-10 — and latent-field presence MUST NOT soften the orphan-key reject (a `requires.tool_restrictions` on a skill is non-conformant even though a matching latent field exists). **Rules application:** Of five Syllago canonical rule capability keys, one resolves to DERIVABLE — `activation_mode` (`D_K: B.activation.mode ∈ {glob, model_decision, manual}` — positive-set form (a future enum member is derivable-false until explicitly added), post-materialization per Decision #30; canonicalization rejects malformed inputs before `D_K` runs, so the predicate only ever sees validated enum members; the declared mode and globs are set-valued → `derived_capabilities`). Four resolve to OUT-OF-SCOPE-AT-L1 — `file_imports` (prose-body opacity under the out-of-band guardrail below; **recorded as the strongest `requires`-candidate the OQ-7 walks have surfaced** — non-derivable, author-created, real silent-failure class (an unresolved `@path` import degrades to literal text on the 5/10 non-supporting providers); first 2:2 panel split of the series, resolved by Holden to REJECT on reversibility asymmetry (adding a `requires` key later is additive; removing a shipped one is breaking), adoption empirics (the npm-engines-without-enforcement precedent — an undeclared majority yields installer false-all-clears), and cross-type coherence with OQ-8; coupled to unified OQ-8 — becomes DERIVABLE, never `requires`-eligible, if a reference grammar is pinned); `cross_provider_recognition` (provider-side format recognition — capability-matrix/L4); `auto_memory` (provider-runtime feature, outside the publish pipeline); `hierarchical_loading` (provider-matrix fact → `provider_capability_coverage` projection, NOT `install_scope_capabilities` — none of its three provenance tags can honestly source a provider-capability fact). `rules.requires` is therefore empty/absent for v0.1 — **empty-as-steady-state holds five-for-five**, via the hard route: the strawman deliberately proposed the first eligible key (honoring "do not force empty"), the panel split 2:2, and the resolution was on the merits. **Out-of-band eligibility guardrail (rules walk, standing normative test):** `requires`-eligibility requires an out-of-band dependency. A capability is `requires`-eligible only when the artifact depends on something it does not contain — an environmental assumption external to the body (runtime version, host service capability). Any capability whose evidence lives *in the body* — structured field, prose, or script bytes — is resolved by the body: DERIVABLE if a canonical field carries it, OUT-OF-SCOPE-AT-L1 under body opacity if only the opaque bytes carry it. A body-carried capability is never `requires`-eligible, regardless of whether a canonical field for it is missing. "The body mentions/uses X" (an `@import`, a referenced MCP tool, a spawned hook) is a body-content fact → derivable-or-opaque, never `requires`. This unifies the hooks walk's two rationales (runtime hints: out-of-band → roadmap-eligible; `decision_control`: in-body-opaque → OOS) and pre-empts shoehorn-by-analogy for the commands walk. The works-fine-without-it test is retained as the **severity** test (grades how badly an OOS capability's absence bites — moderation priority, OQ-8 urgency), not the eligibility test. The `requires` bucket's reserved tenant is out-of-band environmental pins (runtime hints, roadmap). **D_K string discipline (skills walk):** predicates over string fields treat whitespace-only strings as non-empty — Strict `len(s) > 0` — uniformly across all `D_K` predicates, all content types. **Compound-predicate discipline (standing):** if a future `D_K` compounds, every conjunct MUST cite a single canonical field with explicit edge-case definition (empty/absent/null/whitespace). **Three-valued unknown-key logic:** when a `requires` key exists but the consumer doesn't recognize it, the evaluation is `unknown` — distinct from `satisfied` and `unsatisfied`. Two-valued semantics (silent fail-open or silent fail-closed on unknown keys) are non-conformant; installers MUST refuse items with `unknown` capability status unless the operator has explicitly opted into ignore-unknown semantics. **Cross-content-type scoping:** each content type defines its own recognized `requires` vocabulary; an item with a `requires.<key>` not defined for its content type is non-conformant (orphan-key reject). **Sub-blocks rejected by panel review** (MCP walk): `marketplace_listings` (publisher is wrong source of truth — aggregator-pulls-not-publisher-pushes), `enterprise` (no honest equilibrium for `managed_default_candidate`; `notes` is unmoderable free-text at registry scale), `advisory` (silent-failure shape; works-fine-without-it test fails). **Misclassified candidates dropped** (MCP walk): `sandbox` and `interactive_inputs` are harness UX/policy (runtime/IDE concerns), not author-declared capabilities — they do not belong in `requires` regardless of adoption. **Roadmap entries:** `env_file_reference`, `path_variable_expansion` as candidate MCP `requires` keys if they ever become genuinely non-derivable (today both are observable in `servers.*` string values via predicate). Panel: Remy / Karpathy / spec-purist / registry-operator (see `panel/mcp-requires-consensus.md` for the MCP deliberation, `panel/agents-requires-consensus.md` for the agents deliberation and the three-way-disposition amendment, `panel/hooks-requires-consensus.md` for the hooks deliberation including the script-body opacity sub-rationale, D_K boolean discipline, and the 3:1 Position A selection, `panel/skills-requires-consensus.md` for the skills deliberation — unanimous-result-with-amendment-menu shape, the Decision #19/#21 amendments, and the OP-COND-SKILLS dispositions — and `panel/rules-requires-consensus.md` for the rules deliberation: first 2:2 split, the out-of-band guardrail, Decision #30, and the OP-COND-RULES dispositions). **Resolves the principle layer of OQ-7;** the remaining per-content-type vocabulary walk (commands) applies the same derivability test under the three-way disposition and the out-of-band guardrail. |
| 24 | MCP wiring canonicalization: defaults at canonicalization, ambiguous and undetermined rejected | The canonicalizer MUST materialize the explicit `type` field on each MCP server before `body_hash` is computed. Default application rules: `type` absent + `command` present + `url` absent → materialize `type: stdio`; `type` absent + `url` present + `command` absent → materialize `type: streamable-http`; `type` absent + both `command` and `url` present → REJECT (`acif.mcp.transport_default_ambiguous`); `type` absent + neither → REJECT (`acif.mcp.transport_default_undetermined`). `body_hash` is computed over the post-default canonical form. Renderers to provider-specific formats MAY strip explicit `type` for ergonomic output; round-trip back to canonical form is deterministic via the same single-source default rule. **Rationale:** prevents drift between the canonicalizer's default application and any consumer's default application — one rule, one place to update. Validators consume the post-default canonical form and MUST NOT re-apply defaults at validation time. Test vectors TV-MCP-* exercise the default-application boundary; the ambiguous and undetermined cases produce conformance errors with named error codes for tooling interop. |
| 25 | Canonical neutral tool vocabulary anchored to Syllago | ACIF pins canonical neutral tool names by frozen-snapshot reference to Syllago's `cli/internal/converter/toolmap.go` vocabulary. The spawn-subagent tool is the canonical neutral name `agent` (mapping at render-back to provider-specific `Agent` / `task` / `spawn_agent` / `use_subagent` / `Task`). `body_hash` (Decision #19) is computed over the post-translation canonical form — canonicalization rewrites provider-specific tool names to canonical neutral names before hashing. Snapshot pinning protects against downstream churn in Syllago's vocab. **Required by:** Decision #23 agents application — the `subagent_spawning` derivability predicate `D_K: contains(B.Tools, "agent")` is unfulfillable without canonical-name pinning. **Test vectors:** TV-AGENT-derivability-subagent-spawning and TV-AGENT-tool-name-canonicalization (Appendix B). See `panel/agents-requires-consensus.md` §3. |
| 26 | Registry-computed `derived_capabilities` projection | Every conforming registry MUST compute a `derived_capabilities` projection on each item at ingest, applying each DERIVABLE key's predicate `D_K` (Decision #23) over the canonical body. Projection is registry-computed; NOT carried in the L2 `publisher_section` (zero author burden). Exposed on registry-surface item responses for installer-side capability filtering. Exact on-the-wire format deferred until registry implementation needs are observed; the compute requirement is normative now. See `panel/agents-requires-consensus.md` §6a. |
| 27 | `body_size_bytes` registry field — addendum to Decision #19 | Every conforming registry MUST expose `body_size_bytes` (uint, byte count of the canonical body input to the `body_hash` algorithm) alongside `body_hash` on item responses. Supports content-moderation cost-bounding at serve time without re-fetching the body. **Motivation:** agent and skill prose bodies become system prompts at runtime — injection content there is load-bearing, and registries need a cheap pre-filter signal to bound moderation scan cost. Cheap registry-compute hook already present at ingest (the body bytes are already in hand to compute `body_hash`). See `panel/agents-requires-consensus.md` §6b. |
| 28 | Cross-content-type reference resolution enum | For cross-content-type references carried on items (e.g., `agent.MCPServers []string` referencing `mcp_config` items; `agent.Skills []string` referencing `skill` items), every conforming registry MUST resolve each reference at compute time into one of four states: `declared | resolved | unresolved | revoked`. Each resolved reference exposes the resolved target's UUIDv4; `unresolved` and `revoked` references MUST emit diagnostics naming the missing or revoked target. Install tools MUST refuse items with any `unresolved` or `revoked` reference unless the operator has explicitly opted in (parallel to Decision #18's `pack_resolution: unresolved` install-refuse rule). Parallel in shape to Decision #18's `pack_resolution` enum, but per-reference rather than per-item. See `panel/agents-requires-consensus.md` §6c. |
| 29 | Canonical hook event vocabulary + handler-type enum pinning | ACIF pins two canonical hook vocabularies by frozen-snapshot reference to Syllago. (a) **Canonical hook event vocabulary** — approximately 30 canonical event names (`before_tool_execute`, `session_start`, `permission_request`, etc.) drawn from Syllago's `cli/internal/converter/toolmap.go` HookEvents map. (b) **Handler-type closed enum** — `HookEntry.Type ∈ {command, http, prompt, agent}` drawn from Syllago's `cli/internal/converter/hooks.go` `HookEntry.Type` field. Canonicalization rewrites provider-specific event names and handler-type names to the pinned canonical vocabulary before `body_hash` (Decision #19) is computed. Renderers MAY translate to provider-specific names at render-back. Snapshot pinning protects against downstream churn in Syllago's vocab; long-tail provider coverage (~16 events have single-provider coverage in current empirical data) is observational, not a relaxation of the canonical vocabulary. **Required by:** Decision #23 hooks application — the `D_K: handler_types` predicate over `Hooks[*].Type` and the canonical event-name round-trip conformance test are unfulfillable without pinned closed-enum vocabularies. **Test vectors:** TV-HOOK-canonical-event-name and TV-HOOK-canonical-handler-type (Appendix B). Parallel structure to Decision #25. See `panel/hooks-requires-consensus.md` §5. |
| 30 | Canonical rule activation-mode vocabulary (ACIF-originated) | **ACIF's first owned vocabulary** — no frozen-snapshot reference, because no Syllago struct exists to freeze: `RuleMeta{Description, AlwaysApply, Globs}` cannot represent `manual` vs `model_decision` (both are `AlwaysApply:false, Globs:nil`). This is HANDOFF Step 4's authority inversion arriving early; the rules enum is the pilot for repatriating Decisions #25/#29 (syllago/capmon conform to ACIF's copy). Three published components: **(1) Closed enum** — `always` (loaded unconditionally), `glob` (loaded when files matching `globs` are in context), `model_decision` (model decides from description/context), `manual` (loaded only on explicit user invocation — @-mention, slash command, or equivalent). **(2) Total canonicalization mapping table** over all six observed provider sub-modes: `always_on → always`; `glob → glob`; `frontmatter_globs → glob` (documented collapse — declaration mechanism differs, activation semantics identical); `model_decision → model_decision`; `manual → manual`; `slash_command → manual` (zed — slash invocation is explicit user invocation). Deterministic legacy residual: a provider form carrying only `AlwaysApply=false` + no globs maps to `model_decision`; `manual` is reachable only from source formats carrying the distinction explicitly (windsurf `trigger: manual`, zed) or from ACIF-native authoring. Any provider mode with no mapping row → REJECT `acif.rule.activation_mode_unmappable`. **(3) Materialization + rejection rules:** activation block absent → materialize `mode: always` (matches all 10 surveyed providers' no-frontmatter default); `body_hash` computed post-materialization; validators MUST NOT re-apply defaults (parallel to Decisions #24/#21). Block present without `mode` → `acif.rule.activation_mode_missing` (mode is the primary discriminant, parallel to skills' `type` required-when-present; defaulting a present block would silently mislabel glob intent). Unknown or non-exact value (`" always"`) → `acif.rule.activation_mode_invalid` — enum membership is an exact byte match (no trim, no case-fold), stricter than and subsuming the Strict `len(s) > 0` rule. `mode: glob` without `globs` → `acif.rule.glob_mode_without_globs`; `globs` with `mode ≠ glob` → `acif.rule.globs_without_glob_mode`. **Required by:** Decision #23 rules application — the `activation_mode` `D_K` and rules render-back determinism are unfulfillable without the pinned enum + total mapping (a 4-value projection over an unpinned mapping is the Decision #24 defect class). Empirical grounding: 10-provider capability matrix, 6 observed activation sub-modes; windsurf's source format carries all four canonical values distinctly. Informative caution (Remy, preserved): the enum is richer than Syllago's current `RuleMeta` can round-trip; the mapping table's deterministic residual is the mitigation, and `RuleMeta` enrichment is Step 4 repatriation work. **Test vectors:** TV-RULE-* family (Appendix B). See `panel/rules-requires-consensus.md` §5. |

---

## Registry Section Schema

The `registry_section` of every L2 record. Always present; never sourced from publisher frontmatter.

```yaml
registry_section:
  body_hash:                          # REQUIRED — per Decision #19, computed by the MOAT v0.4.0 content-hash algorithm
    algorithm: sha256                 # Single-file items: SHA-256 over content body, frontmatter stripped, LF-normalized.
    value: "abc123..."                # Multi-file items: MOAT directory hash — per-file text/binary classification,
                                      # UTF-8 BOM strip + CRLF→LF for text, raw bytes for binary, VCS dirs excluded,
                                      # symlinks rejected. Registry-generated sidecars inside the content dir are
                                      # excluded at root only (circular-dependency guard).
                                      # NOTE: body_hash MUST be surfaced to ALL consumer-facing responses (Decision #17).
                                      # It is the canonical per-item change signal — not gated behind attestation.
  body_size_bytes: 4096               # REQUIRED — uint, byte count of the canonical body input to the body_hash
                                      # algorithm. Per Decision #27 (addendum to Decision #19). Cost-bounds
                                      # content-moderation scans at serve time without re-fetching the body.
  metadata_hash:                      # REQUIRED when publisher_section is present
    algorithm: sha256                 # SHA-256 over canonical publisher_section bytes (UTF-8 JSON, sorted keys, no whitespace, LF)
    value: "def456..."                # PATH α: over publisher_section bytes ONLY. Invariant under pack-context changes.
  attestation_hash:                   # OPTIONAL — hash from an external integrity/attestation system
    algorithm: sha256                 # populated by that system; distinct algorithm and byte sequence from body_hash
    value: "ghi789..."                # what system produced this is an implementation detail, not named here
  cross_references:                   # OPTIONAL — present when the canonical body declares cross-content-type refs.
                                      # Registry-computed per Decision #28. One entry per declared reference.
                                      # RECIPROCAL ENTRIES (OP-COND-SKILLS-4): for hook-activated skills, the
                                      # registry MUST emit a skill-side entry (source_path: "skill.activation.hook_ref",
                                      # target_kind: hook) reciprocal to the hook-side activation_target entry, so the
                                      # hook↔skill link is discoverable from both ends without consumer-side reverse scans.
    - source_path: "agent.MCPServers[0]"  # JSON path into the canonical body identifying the reference site
      declared_name: "figma"              # the bare string the publisher wrote at source_path
      target_kind: mcp_config             # the content type expected at the target
      target_id: "a1b2c3d4-..."           # REQUIRED iff resolution=resolved; UUIDv4 of the resolved target item
      resolution: resolved                # declared | resolved | unresolved | revoked
      diagnostic: ""                      # REQUIRED for unresolved | revoked; names the missing/revoked target.
                                          # Install tools MUST refuse items with any unresolved/revoked entry
                                          # unless the operator has explicitly opted in.
  derived_capabilities:               # OPTIONAL — registry-computed projection per Decision #26.
                                      # Output of each DERIVABLE key's predicate D_K applied to the
                                      # canonical body. Not stored in publisher_section (zero author
                                      # burden). Exposed for installer-side capability filtering.
                                      # D_K outputs are boolean per Decision #23; set-valued
                                      # projections (e.g., distinct handler types observed) live
                                      # under from_canonical alongside the boolean output.
    from_canonical:                   # sub-projection: predicate output + canonical-set projections.
      # Per-content-type entries; example shows hooks-shape:
      handler_types:
        derivable: true               # boolean D_K output (Decision #23 D_K boolean discipline)
        set: ["command", "http"]      # distinct values observed in canonical body
      matcher_patterns:
        derivable: true
      async_execution:
        derivable: false
      event_provider_coverage:        # registry-computed map: canonical event → providers recognizing it
        session_start: ["claude-code", "cursor", "copilot-cli"]
        # Decision #29 anchors the event-name vocabulary by frozen snapshot.
        # Supports installer-side event-coverage filtering.
      # Rules-shape example (Decision #30 / OP-COND-RULES-2):
      activation_mode:
        derivable: true               # boolean D_K output — mode ∈ {glob, model_decision, manual}
        mode: glob                    # the declared canonical mode (Decision #30 enum)
        globs:                        # BOUNDED projection (OP-COND-RULES-2): never fan out
          present: true               # unbounded publisher glob arrays into the polled response
          count: 3                    # surface; sample capped (≤16) with truncated flag; full
          sample: ["src/**/*.ts"]     # list stays in the body for fetch-on-demand
          truncated: false
    provider_capability_coverage:     # registry-computed map: canonical capability key → providers
                                      # supporting it (OP-COND-RULES-7; parallel to
                                      # event_provider_coverage — a shared capability-matrix fact,
                                      # not per-item compute). Home for provider-capability keys
                                      # disposed OOS-L1 that installers still filter on. NOTE:
                                      # hierarchical_loading lives HERE, not in
                                      # install_scope_capabilities — it is a provider-matrix fact,
                                      # and none of that projection's three provenance tags
                                      # (canonical | publisher_claim | install_context) can
                                      # honestly source one.
      file_imports: ["amp", "claude-code", "cursor", "gemini-cli", "kiro"]
      hierarchical_loading: ["amp", "claude-code", "cline", "codex", "copilot-cli", "cursor", "gemini-cli", "kiro", "windsurf"]
      cross_provider_recognition: ["amp", "claude-code", "codex", "copilot-cli", "cursor", "kiro", "windsurf"]
      auto_memory: ["claude-code", "gemini-cli", "windsurf"]
  install_scope_capabilities:         # OPTIONAL — registry-computed projection. Distinct provenance
                                      # from derived_capabilities: publisher-blind, install-context-
                                      # aware. Surfaces install-scope compatibility (hook_scopes /
                                      # agent_scopes / skill project|global|shared scopes — all
                                      # OOS-L1 dispositions rendered as an install-scope projection
                                      # for enterprise/personal install-path filtering).
                                      # Each entry carries a provenance tag (OP-COND-SKILLS-3):
                                      #   canonical       — derived from the canonical body
                                      #   publisher_claim — asserted by the publisher, not verified
                                      #   install_context — determined by the install mechanism
                                      #                     (e.g., a UI install with no project
                                      #                     filesystem path). Without the tag,
                                      # consumers cannot distinguish a canonical-derived scope from
                                      # a publisher claim.
    global: {supported: true, source: canonical}
    user: {supported: true, source: canonical}
    project: {supported: true, source: install_context}
    managed: {supported: false, source: canonical}
  inferred_pack_id: "b2c3d4e5-..."   # OPTIONAL — UUIDv5 registry-computed pack association (Decision #18).
                                      # Present iff publisher_section.pack_id is absent AND registry inferred a pack.
  pack_resolution: "inferred"        # OPTIONAL — declared | inferred | unresolved
                                      # unresolved: publisher_section.pack_id present but pack record missing.
                                      # Install tools MUST refuse unresolved items.
  inference_version: "v0.1"          # REQUIRED when inferred_pack_id present — declares which inference algorithm produced it
  fetched_at: "2026-05-11T18:00:00Z" # REQUIRED — RFC 3339 UTC, set at crawl time (not sidecar generation time)
  expires: "2026-05-14T18:00:00Z"    # OPTIONAL — default staleness: 72 hours from fetched_at if absent
  source_uri: "https://..."          # REQUIRED — canonical fetch URL; used to override copy-invalidated frontmatter fields
  publisher_declared: true           # REQUIRED — true iff publisher_section was populated from observed frontmatter
  publisher_metadata: "declared"     # OPTIONAL INFORMATIVE — declared | auto-generated | unknown
                                     # NOTE: "declared" means the registry observed frontmatter at crawl time.
                                     # It does NOT mean the publisher cryptographically attested these fields.
  generated_at: "2026-05-11T18:00:00Z"  # OPTIONAL (v0.1) — when this response was assembled by the registry
  max_staleness: "PT1H"              # OPTIONAL (v0.1) — registry's advertised freshness contract (ISO 8601 duration)
```

**Registries MUST NOT write to source files.** All registry-generated metadata lives in sidecars only.

**Forbidden item-record fields** (Decision #16): `effective_version`, `derived_version`, `pack_inherited_version`, `resolved_version`. These MUST NOT appear in either `publisher_section` or `registry_section` on item records. They MAY appear on pack records under the appropriate semantics (a pack's `version` is its own, not inherited).

---

## Open Questions

| # | Status | Question |
|---|---|---|
| OQ-1 | **Resolved** | Sidecar binding uses `body_hash` as the identity key. Single-file items: hash of the content file. Multi-file items: MOAT directory hash (Decision #19). Two hooks on the same event have different script bodies → different hashes → unambiguous binding. |
| OQ-2 | **Resolved** | Content hash boundary for multi-file items: ACIF adopts the MOAT v0.4.0 content-hash algorithm verbatim. Closed `TEXT_EXTENSIONS` set, NUL-byte binary detection, BOM/CRLF normalization for text, VCS directories excluded, symlinks rejected at ingestion. Registry-generated sidecar files inside the content directory are excluded at root only (circular-dependency guard, analog of MOAT's `moat-attestation.json` rule). See Decision #19. |
| OQ-3 | **Resolved** | Pack model — `kind: pack` L2 record with stable UUID identity. Two paths: registry-inferred (Option C primary, via v0.1 inference algorithm) and publisher-declared (Option A opt-in). Declared wins on conflict. Pack-less items are first-class. See Decision #18 and `panel/pack-model-consensus.md`. |
| OQ-4 | **Resolved** | No version inheritance into item records. Item `version` is literal-or-absent. Pack `version` lives on pack record only. `body_hash` is the canonical per-item change signal, surfaced normatively to all consumers. See Decisions #16, #17 and `panel/pack-model-consensus.md`. |
| OQ-5 | **Addressed** | Registry transparency: `publisher_declared` (bool, REQUIRED) + `publisher_metadata` (enum, OPTIONAL INFORMATIVE). See registry section schema above. |
| OQ-6 | **Open** | `os`/`arch` defaults — when `os` is absent from a script entry, does it mean "all OS" or "unspecified"? |
| OQ-7 | **Principle resolved; per-type walks in progress** | `requires` vocabulary — Decision #23 establishes the principle (three-way disposition: DERIVABLE / OUT-OF-SCOPE-AT-L1 / `requires`-ELIGIBLE; predicate-explicit derivability `D_K`; tiebreaker rule; empty-as-steady-state; three-valued unknown-key logic; orphan-key reject for cross-type scoping). **MCP slice resolved:** `mcp.requires` empty/absent for v0.1 (all 8 Syllago canonical keys DERIVABLE by `D_K` over `servers.*`). **Agents slice resolved:** `agents.requires` empty/absent for v0.1 (5 of 7 Syllago canonical keys DERIVABLE, 2 OUT-OF-SCOPE-AT-L1). **Hooks slice resolved:** `hooks.requires` empty/absent for v0.1 (3 of 9 Syllago canonical keys DERIVABLE — `handler_types`, `matcher_patterns`, `async_execution`; 6 OUT-OF-SCOPE-AT-L1 — `hook_scopes` install-location plus five script-runtime keys under the new script-body opacity sub-rationale; runtime hints deferred to roadmap). First non-unanimous panel (3:1); Position A — empty-`requires` for v0.1 — adopted. New normative scaffolding from hooks walk: Decision #29 (canonical hook event vocab + handler-type enum pinning), D_K boolean discipline normative in Decision #23, two new registry projections (`event_provider_coverage`, `install_scope_capabilities`). **Skills slice resolved:** `skills.requires` empty/absent for v0.1 (4 of 15 Syllago canonical keys DERIVABLE — `auto_invocable`, `disable_model_invocation`, `user_invocable`, `skill_bundled_resources`; 11 OUT-OF-SCOPE-AT-L1). Unanimous result with amendment menu (contrast hooks' 3:1 split). New normative scaffolding from skills walk: Decision #19 amendment (content-type-general single/multi-file classification predicate), Decision #21 amendment (`activation.user_invocable` + canonicalization-time default materialization), Strict whitespace rule for `D_K` string predicates, `install_scope_capabilities` provenance tags, reciprocal skill-side `cross_references`. **Rules slice resolved (the load-bearing test):** `rules.requires` empty/absent for v0.1 (1 of 5 Syllago canonical keys DERIVABLE — `activation_mode`, positive-set `D_K` over the Decision #30 enum; 4 OUT-OF-SCOPE-AT-L1 — `file_imports` under prose-body opacity [the strongest requires-candidate surfaced; coupled to unified OQ-8], `cross_provider_recognition`, `auto_memory`, `hierarchical_loading` [→ `provider_capability_coverage`]). **First 2:2 panel split of the series** (Remy/Karpathy REJECT vs spec-purist/registry-operator ADMIT on `file_imports`); resolved by Holden to REJECT on reversibility asymmetry, adoption empirics, and OQ-8 coherence. New normative scaffolding from the rules walk: Decision #30 (Rule Extension Block + first ACIF-owned vocabulary — activation-mode enum with total mapping table), the out-of-band eligibility guardrail in Decision #23 (standing test for all future walks), `provider_capability_coverage` registry projection, bounded-globs projection discipline. Predicate-pinning-debt ledger did NOT advance (all rules scaffolds ruled core-primitive). Empty-as-steady-state holds **five-for-five** — via the hard route: the strawman deliberately proposed the first eligible key, and the resolution was on the merits, not by principle-preservation. Per-content-type vocabulary walk remaining: commands (2 keys) — applies the same derivability test under the three-way disposition and the out-of-band guardrail. Empirical grounding: round 2 found hook libraries in six runtimes (TS, Ruby, Go, Rust, Python daemon, PowerShell); rules walk grounded in the 10-provider capability matrix (6 observed activation sub-modes). |
| OQ-8 | **Open (unified by rules walk — spans skills AND rules)** | In-prose file-reference grammar — what reference grammar (if any) does ACIF pin for prose file references, and does ACIF ever parse prose to resolve them? Covers skills' `@sibling.md` referencing (e.g., `@testing-anti-patterns.md` in `examples/obra/skill-tdd.md` — in-bundle) AND rules' `@path` imports (amp documents relative, absolute, and `~/` paths — frequently out-of-bundle, invisible to `body_hash`). Bundling is resolved (`skill_bundled_resources` DERIVABLE via Decision #19); referencing lives in prose ACIF does not parse in v0.1. **Resolution consequences pre-recorded (rules walk):** grammar pinned → rules `file_imports` becomes DERIVABLE (registry-computed, whole-corpus coverage; the deferred OP-COND-RULES-4 advisory lint and OP-COND-RULES-5 security lint [@-target classes `{in-bundle, absolute, home, url}` — exfil/remote-fetch hazard] become implementable). Never-parse → `file_imports` stays OOS-L1 as honest opacity, and spec-purist's preserved dissent (works-fine-without-it failure — silent semantic corruption) MUST be re-heard before that branch is finalized. In neither branch is `file_imports` `requires`-eligible (out-of-band guardrail). See `panel/rules-requires-consensus.md` §5, §9 and `panel/skills-requires-consensus.md` §6. |
| OQ-9 | **Open** | Two-tier freshness interop — when an external attestation manifest has its own expiry and the sidecar `expires` differ, which takes precedence for staleness determination? |
| OQ-10 | **Open** | Latent `SkillMeta` field promotion — should `AllowedTools` / `DisallowedTools` / `Model` / bundled `Hooks` be promoted to canonical skill capability vocabulary? Until resolved, these fields are named out-of-scope in Decision #23's skills application and their presence MUST NOT soften the orphan-key reject. OP-COND-SKILLS-5 (registry diagnostic for latent fields) is deferred to the roadmap, coupled to this question — its target set is exactly what this OQ will redefine. See `panel/skills-requires-consensus.md` §7. |

---

## Appendix A — Inference Algorithm v0.1 (normative)

Registries that emit `registry_section.inferred_pack_id` MUST follow this algorithm. Half-normative inference ("MAY infer however documented") is explicitly rejected — either implement v0.1 exactly, or omit `inferred_pack_id` entirely.

### A.1 — Canonical source precedence

When a repo contains multiple pack-shaped manifests, registries select the canonical source by this precedence:

1. `package.json` (top-level `name` field)
2. `.claude-plugin/plugin.json` (top-level `name` field)
3. `.cursor-plugin/plugin.json` (top-level `name` field)
4. `.codex-plugin/plugin.json` (top-level `name` field)
5. `gemini-extension.json` (top-level `name` field)
6. **Directory-adjacency fallback** — repo's basename from `repository_url`

The first present source wins. When multiple manifests exist, conflicting values produce a registry warning (surfaced to the publisher); the precedence chain resolves which value the registry adopts as canonical.

### A.2 — Canonical `display_name`

`canonical_display_name = trim(source.name)` from the highest-precedence source. No case-folding, no whitespace collapsing beyond a single leading/trailing trim. If the source's `name` field is absent or empty, fall back to the next source.

### A.3 — Canonical `repository_url`

`canonical_repository_url` is the lowercased, https-normalized, trailing-slash-stripped, `.git`-suffix-stripped form of the repo's fetch URL. Examples:

- `git@github.com:obra/superpowers.git` → `https://github.com/obra/superpowers`
- `https://github.com/obra/superpowers/` → `https://github.com/obra/superpowers`

### A.4 — `inferred_pack_id` derivation

```
inferred_pack_id = UUIDv5(
  namespace = ACIF_PACK_NAMESPACE,
  name      = canonical_repository_url + "\n" + canonical_display_name
)
```

Where `ACIF_PACK_NAMESPACE` is the spec-pinned literal UUID:

```
ACIF_PACK_NAMESPACE = "TBD-LITERAL-UUID-v5-NAMESPACE-FOR-ACIF-v0.1"
```

> **NOTE FOR SPEC AUTHORS:** the literal namespace constant MUST be chosen and pinned in the v0.1 spec text before publication. Registry-operator's OP-COND-1 makes this non-negotiable. Suggested format: a fresh UUIDv4 generated by the spec authors, documented as the canonical ACIF v0.1 namespace, never reused for other algorithm versions.

### A.5 — Canonical address derivation

`canonical_address = <owner>/<canonical_display_name>` where `owner` is extracted from `canonical_repository_url`:

- **github.com:** `owner = path segment after host`
- **gitlab.com:** `owner = path segment after host` (may be a group; full group path joined with `/`)
- **bitbucket.org:** `owner = path segment after host`
- **git.sr.ht:** `owner = first path segment, with leading `~` stripped`
- **Other hosts:** `owner = first path segment of canonical_repository_url`

### A.6 — Inference version field

Every registry response containing `inferred_pack_id` MUST include `inference_version: "v0.1"` in the same `registry_section`. Consumers detecting inference-version drift between registries SHOULD treat it as a divergence signal.

---

## Appendix B — Conformance Test Vectors (required for v0.1 ship)

The spec MUST publish these test vectors in a `conformance/` directory. Two implementations agreeing in prose but diverging in bytes is the failure mode these vectors prevent.

| ID | Tests | Description |
|---|---|---|
| TV-1 | `body_hash` stability across pack context | Same skill body bytes, three pack contexts (pack-less / pack-A / pack-B) → identical `body_hash.value` |
| TV-2 | `metadata_hash` invariance under PATH α | Same publisher frontmatter, different inferred pack contexts → identical `metadata_hash.value` |
| TV-3 | `inferred_pack_id` determinism | `repository_url=https://github.com/obra/superpowers` + `display_name=superpowers` → published reference UUIDv5 |
| TV-4 | Declared wins over inferred | Item with `publisher_section.pack_id=X` + `registry_section.inferred_pack_id=Y` (X≠Y) → consumer resolves via X |
| TV-5 | Unresolvable `pack_id` semantics | Item with `publisher_section.pack_id=Z` where Z does not exist → `pack_resolution="unresolved"`; install MUST refuse |
| TV-6 | Forbidden field set | Sidecar with `effective_version` on an item → conformance error |
| TV-7 | Literal version preserved through pack context | Item declares `version=2.0.0`, pack declares `version=5.1.0` → `publisher_section.version=2.0.0` (literal, unchanged); no item-level field reflects 5.1.0 |
| TV-8 | Pack-less item is first-class | Item with no `pack_id` and no `inferred_pack_id` → valid sidecar, installable |
| TV-9 | Canonical `metadata_hash` byte string | Given a `publisher_section` JSON, canonical serialization (UTF-8 JSON, sorted keys, no whitespace, LF) matches published byte string → `metadata_hash` matches published reference hash |
| TV-10 | Pack rename preserves identity (should-have) | Pack with `id=UUID` renamed `display_name` → `id` unchanged; existing item references via `pack_id` continue to resolve |
| TV-MCP-* | MCP canonicalization & requires-emptiness family (Decision #23, #24) | Family covers: (a) default `type` materialization — stdio when only `command`, streamable-http when only `url`; (b) ambiguous rejection (both `command` and `url` with no `type`) → `acif.mcp.transport_default_ambiguous`; (c) undetermined rejection (neither) → `acif.mcp.transport_default_undetermined`; (d) `body_hash` stability across no-type/explicit-type round-trips; (e) `mcp.requires` empty-or-absent is conformant; (f) unknown `requires.<key>` → three-valued `unknown` evaluation; (g) `requires.transport_types` (or any other derivable key) appearing on an `mcp_config` item → non-conformant (orphan-key reject under per-content-type vocab scoping). Individual TV IDs to be enumerated when the conformance suite is authored. |
| TV-AGENT-* | Agents `requires` empty-state + derivability predicate family (Decision #23, #25) | Family covers: (a) `agents.requires` empty-or-absent is conformant (empty-as-steady-state, Decision #23); (b) unknown `requires.<key>` on an agent item → three-valued `unknown` evaluation; (c) any DERIVABLE key (e.g., `requires.tool_restrictions`) appearing on an `agents` item → non-conformant (orphan-key reject under per-content-type vocab scoping); (d) `D_K: tool_restrictions` — canonical body with `Tools: [Read]` produces derivable-true; empty `Tools` + empty `DisallowedTools` produces derivable-false; (e) `D_K: model_selection` over `Model` — non-empty → derivable-true; empty → derivable-false; (f) `D_K: per_agent_mcp` over `MCPServers` — same shape; (g) `D_K: subagent_spawning` over `Tools` — `Tools: ["agent"]` produces derivable-true; `Tools: ["Read", "Edit"]` produces derivable-false (exercises Decision #25 canonical-tool-name pinning); (h) canonical `Tools` array contains spec-pinned neutral names (`agent`, not `Agent`/`Task`/`spawn_agent`); `body_hash` is computed post-translation; renderers MAY translate to provider-specific names at render time. Individual TV IDs to be enumerated when the conformance suite is authored. |
| TV-HOOK-* | Hooks `requires` empty-state + derivability predicate family (Decision #23, #29) | Family covers: (a) `hooks.requires` empty-or-absent is conformant (empty-as-steady-state, Decision #23); (b) any key (e.g., `requires.handler_types`) appearing on a `hooks` item → non-conformant (orphan-key reject under per-content-type vocab scoping); (c) unknown `requires.<key>` on a hook item → three-valued `unknown` evaluation; (d) `D_K: handler_types` — canonical body with `Hooks: [{Type: "command", Command: "..."}]` produces derivable-true; empty `Hooks` produces derivable-false; closed enum `{command, http, prompt, agent}` is normative per Decision #29; (e) `D_K: matcher_patterns` over `Matcher` — non-empty → derivable-true; empty → derivable-false; (f) `D_K: async_execution` over `Hooks[*].Async` — at least one `Async: true` → derivable-true; all `Async: false` (or absent) → derivable-false; (g) canonical event-name round-trip — provider-specific event names are translated to the pinned canonical vocabulary at canonicalize time; `body_hash` is computed post-translation (exercises Decision #29); (h) canonical handler-type round-trip — provider-specific handler-type names are translated to the pinned canonical enum at canonicalize time (exercises Decision #29). Individual TV IDs to be enumerated when the conformance suite is authored. |
| TV-RULE-* | Rules canonicalization + `requires` empty-state + Decision #30 family (Decision #23, #30) | Family covers: (a) activation-default materialization — activation block absent → canonical form carries `mode: always`; `body_hash` computed post-materialization (parallel to TV-MCP-*/TV-SKILL-*); (b) mode required-when-present — block present, `mode` absent → `acif.rule.activation_mode_missing`; (c) invalid value — `mode: sometimes` AND `mode: " always"` (exact byte-match membership, no trim) → `acif.rule.activation_mode_invalid`; (d) mapping-table totality — `frontmatter_globs`-declared source → `glob`; windsurf `trigger: manual` → `manual`; zed slash-command rule → `manual`; legacy `AlwaysApply=false`+no-globs → `model_decision` (deterministic residual); unmapped provider mode → `acif.rule.activation_mode_unmappable` (exercises Decision #30); (e) glob consistency — `mode: glob` without `globs` → `acif.rule.glob_mode_without_globs`; `globs` with `mode ≠ glob` → `acif.rule.globs_without_glob_mode`; (f) `D_K: activation_mode` — `always` → derivable-false; `glob`/`model_decision`/`manual` → derivable-true; activation-absent → derivable-false via materialization (exercises the positive-set form); (g) `derived_capabilities` projection carries `{derivable, mode, globs bounded per OP-COND-RULES-2}`; (h) `rule.requires` empty-or-absent is conformant (empty-as-steady-state); (i) orphan-key reject, three distinct reject reasons — `requires.file_imports` (the considered-and-rejected candidate; its rejection is load-bearing), `requires.activation_mode` (derivable keys are never `requires` keys), `requires.handler_types` (foreign-type key) — all non-conformant on a rule; (j) unknown `requires.<key>` → three-valued `unknown` evaluation; (k) prose-opacity round-trip — body containing `@`-import syntax canonicalizes and renders back with prose carried verbatim (ACIF does not parse @-references in v0.1); `body_hash` stable. Individual TV IDs to be enumerated when the conformance suite is authored. |
| TV-SKILL-* | Skills `requires` empty-state + derivability + amendment-exercising family (Decision #23, and the #19/#21 amendments) | Family covers: (a) `skills.requires` empty-or-absent is conformant (empty-as-steady-state, Decision #23); (b) orphan-key reject — any `requires.<key>` on a skill → non-conformant, including a key recognized in another type (`requires.handler_types`) AND a key matching a latent `SkillMeta` field (`requires.tool_restrictions`); latent-field presence MUST NOT soften the reject; (c) unknown `requires.<key>` → three-valued `unknown` evaluation; (d) `D_K: auto_invocable` — activation absent (→true), `type: auto` (→true), `type: manual` (→false), `type: hook` (→false); (e) `D_K: disable_model_invocation` — absent (default auto → false), `type: auto` (→false), `type: manual` (→true), `type: hook` (→true); (f) `D_K: user_invocable` — absent (default true → false), `user_invocable: true` (→false), `user_invocable: false` (→true); exercises the Decision #21 amendment; (g) `D_K: skill_bundled_resources` — single-file `SKILL.md` (→false); dir with `SKILL.md` only (→false); dir with `SKILL.md`+`LICENSE`+`README` (→false, exclusion list); dir with `SKILL.md`+`scripts/` (→true); exercises the Decision #19 classification amendment; (h) activation-default materialization — activation absent → canonicalized form carries `type: auto` and `user_invocable: true`; `body_hash` computed post-materialization (parallel to TV-MCP-*); (i) body classification (general) — directory with only `{LICENSE, README}` beyond the entry file → single-file; directory with a co-located content file → multi-file; applies to skills AND bundled-script hooks (content-type-general Decision #19 predicate); (j) hook-activated skill cross-reference — `type: hook` + `hook_ref.id` → registry resolves per Decision #28 enum AND emits the reciprocal skill-side `cross_references` entry (OP-COND-SKILLS-4). Individual TV IDs to be enumerated when the conformance suite is authored. |
