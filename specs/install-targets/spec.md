# ACIF Install-Targets Specification

**Version:** 0.1.0
**Status:** Draft
**Spec ID:** [ACIF-INSTALL]

---

## Abstract

This document defines the Level 5 layer of the Agent Content Interchange Format: the provider install-target matrix — where each provider reads and writes each content type on disk — and the contract binding the install tool, the actor that places items into those locations. It specifies the entry-point descriptor model, the closed scope and layout enums, the path-template placeholder grammar and its deterministic resolution function, the shared-file merge contract, the install-time diagnostics discipline, and the maintenance model under which vendor-controlled path facts are amended.

## 1. Introduction

Rendering ([ACIF-RENDER]) ends at bytes: a provider-native artifact, correct for its target, located nowhere. Between those bytes and a working installation stands one more fact the canonical form deliberately does not carry — the filesystem location at which the target provider discovers content of that type. This document makes that fact normative, shared, and machine-readable, for the same reason the source-mechanism tokens were normalized into [ACIF-RULE] Appendix A.2 and [ACIF-HOOK] §7.4: while the fact lives only inside individual install tools, every tool re-derives it independently, no two tools can be shown to agree, and no conformance statement about placement is possible.

The matrix this document publishes is keyed by `(provider, content type)` and is pure provider-matrix data in the sense of [ACIF-REGISTRY] §8.4 — but unlike capability coverage, placement is load-bearing: a conforming install tool's write path depends on it. It is therefore published under the deterministic-projection discipline (frozen rows, selftest-synced export, amended by process) rather than as an observational crawl snapshot. §12 and Appendix A.1 define what that freeze does and does not claim.

The six content types are co-equal here as everywhere in this document set: the descriptor model, grammar, and layout vocabulary are defined once and apply to all six.

## 2. Relationship to ACIF Core and the Lower Layers

This document is the Level 5 (L5) companion to [ACIF-CORE] and depends normatively on [ACIF-CORE], the six L1 interchange specifications, and [ACIF-RENDER]. It redefines no term from those documents. Render-back produces the bytes an install tool places; this document is downstream of render and places no requirement on renderers, publishers, or registries except where explicitly stated (§12 byte-identical re-serving).

Nothing in this document adds a field to the canonical body, `publisher_section`, or `requires`, and nothing in it participates in `body_hash` or `metadata_hash` ([ACIF-CORE] §8.2). Install location is an environment fact about a provider, never a property of an item; an item's canonical bytes are identical wherever it will be installed.

This document is compatible with [ACIF-CORE] version 0.1.x. All documents are Draft maturity.

## 3. Terminology

Terms defined in [ACIF-CORE] §2 — including **provider** and **install tool** — are used without redefinition. Additionally:

**entry point** — one location at which a provider reads content of one type: a `(scope, path template, layout)` triple, published as a row of the Appendix A.2 matrix.

**entry-point row** — the published form of an entry point, carrying the normative triple plus its maintenance fields (`status`, and the informative `as_of`).

**path template** — a string in the closed placeholder grammar of §8 that resolves to a concrete filesystem path.

**placeholder token** — a `<`-delimited token of the closed set the §8 grammar defines.

**content name** — the per-item substitution input to path resolution, supplied by the install invocation (§8.2).

**layout** — the classification of how items of a type occupy an entry point: `single_file`, `directory_of_files`, or `merged_into_shared_file` (§9).

**contribution** — the bytes an install adds to a shared file under the `merged_into_shared_file` layout (§10).

## 4. Requirements Language

The key words "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHALL NOT", "SHOULD", "SHOULD NOT", "RECOMMENDED", "NOT RECOMMENDED", "MAY", and "OPTIONAL" in this document are to be interpreted as described in BCP 14 [RFC2119] [RFC8174] when, and only when, they appear in all capitals, as shown here.

## 5. Conformance

**Conforming install tool** — satisfies every MUST and MUST NOT in this document, and in the install-time sections of the L1 specifications for each content type it installs ([ACIF-HOOK] §11 coverage-gap rule; the revoked-reference refusal of [ACIF-CORE] §10 and [ACIF-REGISTRY] §9). An install tool MAY support any subset of providers and content types; conformance is claimed per `(provider, content type)` pair.

The test-vector family in Appendix B is normatively authoritative over prose.

## 6. The Entry-Point Descriptor Model

For each `(provider, content type)` pair a provider supports on disk, Appendix A.2 publishes an **ordered list** of entry-point rows. The list, not a single row, is the unit: providers legitimately read one type from several locations, and multiplicity is data, not an error.

Each row carries:

| Field | Values | Normativity |
|---|---|---|
| `scope` | closed enum, §7 | normative |
| `path_template` | closed grammar, §8 | normative |
| `layout` | closed enum, §9 | normative |
| `status` | `current` \| `superseded` | normative (maintenance, §12) |
| `as_of` | free text naming the provider build or documentation the row was verified against | informative |

Three structural rules:

- **Uniqueness.** `(provider, content type, scope, path_template)` is unique across the matrix. Two rows differing only in `layout` or `status` are a publication defect, not a choice offered to consumers.
- **Order is precedence.** Row order within a `(provider, content type)` list is normative. The first `status: current` row for a requested scope is the **write target**; every row is a read/discovery location. An install tool MUST NOT write to a non-first row for its scope except under explicit operator instruction.
- **Absence is meaningful.** A `(provider, content type)` pair with no rows means no location is published for that pair. An install tool MUST NOT guess: the outcome is the `acif.install.no_entry_point` refusal (§11). A guessed path that a provider happens to read today is precisely the impl-private knowledge this document exists to eliminate.

## 7. Scope

`scope` is a closed enum, matched by exact byte comparison ([ACIF-CORE] §8.3):

| Scope | Anchor | Meaning |
|---|---|---|
| `user` | the invoking user's home directory | content available to that user in every project |
| `project` | the project root | content versioned and scoped with a repository |
| `managed` | an administrator-controlled absolute location | org- or machine-managed content the user does not edit |

**Relationship to `install_scope_capabilities` ([ACIF-REGISTRY] §8.5).** The registry projection answers *whether an item may live at a scope*; this matrix answers *where that scope is on disk for a provider*. The two vocabularies map totally: §8.5 `project` → `project`; §8.5 `global` and `user` → `user` (the two keys are provider-parlance synonyms for the same per-user anchor); §8.5 `managed` → `managed`. A §8.5 entry tagged `source: install_context` derives from this matrix; where such an entry and this matrix disagree, this matrix governs and the projection has a bug ([CHANGE-PROCESS] source-of-truth rule).

*(Informative)* Cross-provider shared locations — a path such as `AGENTS.md` appearing in several providers' rows — are a phenomenon, not a scope: each reading provider publishes its own row, and the collision is visible by resolving the rows, which is how install tools detect that writing for one provider changes what another reads (§13).

## 8. The Path-Template Grammar

### 8.1 Closure

The placeholder token set is **closed**: `<content-name>` is its only member in 0.1. A path template is a `/`-separated string in which each segment is either literal or contains placeholder tokens; the grammar admits nothing else — no escapes, no alternation, no globs. A template (or an export row) carrying a token outside the closed set fails resolution with `acif.install.placeholder_unrecognized` (§11) — the version-skew net for consumers reading a matrix newer than their grammar.

Growing the token set is a Class C change ([CHANGE-PROCESS]). Tokens beginning `<unknown-` are reserved for negative test fixtures and are never minted.

### 8.2 `<content-name>`

`<content-name>` is an **input to resolution**, supplied by the install invocation alongside the target provider and content type — the install-side analog of the render context ([ACIF-RENDER] §6.1). This document pins its validity, not its derivation; naming an item is upstream of placing it. Two pins bind the derivation where one exists:

- **skill** — `<content-name>` names the skill directory; the entry file inside it is `SKILL.md` ([ACIF-SKILL] §9). The template resolves to the directory (§9).
- **all types** — where discovery derived a name (the URL-derived filename, [ACIF-REGISTRY] §10.5), an install tool SHOULD offer it as the default; `display_name` MUST NOT be used as a content name ([ACIF-CORE] §5.1 bars it from identity use).

**Validity predicate.** A content name MUST be a non-empty string containing no `/`, no `\`, no NUL, and no segment equal to `.` or `..` after substitution. A violation rejects with `acif.install.content_name_invalid` before any path is formed. Substitution is byte-exact: no trimming, no case folding, no encoding.

### 8.3 Anchors and resolution

Resolution is a function: identical `(entry-point row, content name, home directory, project root)` MUST produce a byte-identical resolved path, across invocations and across conforming implementations.

- A template beginning `~/` is **home-anchored**: `~` resolves to the invoking user's home directory — the platform's native notion (`$HOME` on POSIX systems, `%USERPROFILE%` on Windows). `~` carries no other meaning and appears only as the leading segment.
- A `managed`-scope template is **absolute** and resolves verbatim (it may still carry `<content-name>`).
- Any other template is **project-anchored**: resolved against the project root the invocation supplies.

Templates are written with `/` separators; an install tool maps them to the native separator at the filesystem boundary. Resolution performs placeholder substitution and anchoring only — it MUST NOT normalize case, expand symlinks, or rewrite segments.

ACIF 0.1 publishes no per-OS entry-point dimension: every 0.1 row resolves on every OS through the anchor rules above. A provider that ships an OS-divergent location (an `%APPDATA%`-rooted path with no home-anchored equivalent) is the named roadmap trigger for adding an `os` field to the row model, following the closed OS enum of [ACIF-HOOK] §7.1; the dimension is not pre-built ahead of an observed need.

## 9. Layouts

`layout` is a closed enum, matched by exact byte comparison. It classifies what the resolved path names and how many items share it:

| Layout | Resolved path names | Items per path |
|---|---|---|
| `single_file` | one item's file; the template carries `<content-name>` and any provider-required extension as a literal | one |
| `directory_of_files` | one item's directory root; entry-file naming inside it belongs to the owning L1 ([ACIF-SKILL] §9 pins `SKILL.md`) | one |
| `merged_into_shared_file` | a provider-owned file the template names **without** `<content-name>`; items land as contributions inside it (§10) | many |

The mapping from content type to layout is per-row data, not per-type doctrine: the same content type legitimately occupies different layouts on different providers (a rule is a file-per-item on one provider and a section of a monolithic memory file on another). What is uniform is the classification itself — every row of Appendix A.2 carries exactly one of the three members.

## 10. The Shared-File Merge Contract

`merged_into_shared_file` is the highest-risk layout: the install tool writes into a file it does not own, alongside provider settings and other installs. Four obligations bind every conforming install into a shared file:

1. **Structured encoding.** The contribution MUST be written through the target format's structured encoder; string-splicing into the file is non-conformant ([ACIF-CORE] §8.5, [ACIF-RENDER] §8). For markdown-monolith targets, the contribution MUST be a contiguous region delimited so that rule 3 is mechanically satisfiable.
2. **Preservation.** Content of the shared file outside the contribution MUST be semantically preserved — an install that reorders, reformats, or drops unrelated members is non-conformant.
3. **Idempotence.** Re-installing an item replaces its own prior contribution and touches nothing else. The contribution is keyed by the target format's native collection key for the content type where the owning L1's render section defines one (the server-name member for an MCP configuration, [ACIF-MCP] §10; the event wiring emitted per [ACIF-HOOK] §12); where none is defined, the key is `<content-name>`.
4. **Un-merge.** Uninstall removes exactly the contribution — the shared file afterward is the file as if the item had never been installed, modulo encoder-canonical formatting of untouched members.

The bytes *of* the contribution are the renderer's output and are pinned by [ACIF-RENDER] and the owning L1's render section; this document pins only their placement and lifecycle, and defines no merge semantics of its own — where hook shared-file behavior is concerned, [ACIF-HOOK] §12 and the §7.4 identity-merge govern and are not restated here. Round-trip verification ([ACIF-RENDER] §9) over a shared file is scoped to the extracted contribution, not the whole file. Byte-level merge pinning per target format — exact anchor comments for markdown monoliths, member ordering on insert — is a named roadmap item; until it lands, two conforming tools may produce byte-different shared files that satisfy all four obligations.

## 11. Install Disposition and Diagnostics

Resolution and install produce dispositions in the [ACIF-HOOK] §11 pattern — proceed, warn, or refuse — with the identifiers this document mints (§14):

| Condition | Identifier | Disposition |
|---|---|---|
| content name fails the §8.2 validity predicate | `acif.install.content_name_invalid` | reject the invocation |
| no row exists for `(provider, content type)` | `acif.install.no_entry_point` | refuse — an install tool MUST NOT guess a path |
| rows exist, but none for the requested scope | `acif.install.scope_unavailable` | refuse; `params` MUST name the scopes that do have rows |
| a row carries a token outside the consumer's grammar | `acif.install.placeholder_unrecognized` | refuse for the write direction; the row MAY still serve read/discovery |
| the resolved write row is `status: superseded` | `acif.install.entry_point_superseded` | warn and proceed; operators MAY configure refuse |

Silence is the violation, as everywhere in this document set: each condition has exactly one disclosure home, and an install tool MUST NOT convert a refuse lane into a best-effort write under an option flag ([ACIF-RENDER] §6.1 discipline). The warn lane exists for supersession because the superseded location is still a real location — a stale-but-working install is disclosed, not forbidden; a guessed path is forbidden because it is not disclosed anywhere.

## 12. Maintenance: What the Freeze Claims

The Appendix A.2 rows are **normative as the interoperability contract among ACIF actors**: two conforming install tools given the same row set and inputs resolve the same paths, and conformance vectors pin that property. Correspondence of a row to a living provider build is a **maintained empirical claim** — install paths are vendor-controlled facts that change with provider releases, and this document's authority over its rows is authority over what conforming tools *do*, never over what providers *ship*.

That split sets the maintenance model:

- **Row-data amendments** — correcting or superseding a row because a provider moved, added, or retired a location — follow the row-data amendment lane of [CHANGE-PROCESS]: land on observation, no batch window. A moved directory fires no totality-net diagnostic on any content (the loud absence that makes this lane necessary — nothing in an item's bytes goes wrong when a provider relocates its config dir), so the signal path is observation and filed reports, not diagnostics.
- **Supersession, not deletion.** A row a provider no longer reads moves to `status: superseded` and remains published. Consumers holding older exports see the supersession on their next diff instead of a vanished row; the superseded location keeps serving read/discovery (uninstall of old installs needs it).
- **Grammar and enum changes** — a new placeholder token, scope, layout, or row field — are Class C changes with full design treatment.
- **Consumption.** The matrix is published as the deterministic export `conformance/install-entry-points.yaml`, selftest-synced to Appendix A.2 (spec-prose parsing happens at the authority; downstream diffs the export, [CHANGE-PROCESS] source-of-truth rule). It carries no crawl date and no observational provenance — it is a function of its git revision, which is what keeps downstream drift checks deterministic. An install tool SHOULD refresh the export from its registry or from the spec repository at install time and treat any copy vendored into its binary as a fallback; a registry re-serving the export MUST serve it byte-identical — no freshness decoration, no `fetched_at` stamp.

## 13. Security Considerations

**Resolved paths are write targets.** The §8.2 validity predicate is the traversal defense: a content name carrying separators or dot-segments would otherwise turn a template into a write primitive against arbitrary paths. Rejection happens before path formation, and the predicate is vectored (Appendix B).

**A wrong path is a fail-open install.** An install that lands where the provider no longer reads reports success while the content never runs — for a blocking hook, a silently absent control ([ACIF-HOOK] §11). This is why guessing is forbidden (§6), supersession is disclosed (§11), and rows are amended on observation rather than on release cadence (§12).

**Shared files cross trust boundaries twice.** A `merged_into_shared_file` write lands beside provider settings the user relies on (the §10 preservation and un-merge obligations), and a cross-provider shared path means an install performed for one provider changes what another provider loads — an install tool SHOULD resolve the full matrix for a path it is about to write and disclose every other `(provider, content type)` row that names it.

**`managed` scope is an authority boundary.** Managed rows resolve to administrator-controlled locations. An install tool MUST NOT escalate privileges to write a managed row on a user's behalf; a managed install is an administrator's act, and the row exists so that act is placed correctly, not so it can be automated around.

## 14. Error Identifiers

All identifiers follow the [ACIF-CORE] §12 naming discipline, family `acif.install.*`. This document is their owning specification. None uses the `_unmappable` suffix: that suffix is reserved for L1 canonicalization totality nets whose firing is Class B evidence, and no install condition is one — the matrix's amendment signal is observation, not a diagnostic (§12).

| Identifier | Class | Condition |
|---|---|---|
| `acif.install.content_name_invalid` | reject | §8.2 validity predicate violation |
| `acif.install.no_entry_point` | refuse | no row for `(provider, content type)` (§11) |
| `acif.install.scope_unavailable` | refuse | no row for the requested scope; `params` names available scopes (§11) |
| `acif.install.placeholder_unrecognized` | refuse | row token outside the consumer's closed grammar (§8.1) |
| `acif.install.entry_point_superseded` | diagnostic (warn) | write target resolved via a `status: superseded` row (§11) |

## 15. References

### 15.1 Normative

- [ACIF-CORE] "ACIF Core Specification", version 0.1.x. `../core/spec.md`
- [ACIF-HOOK] / [ACIF-SKILL] / [ACIF-RULE] / [ACIF-COMMAND] / [ACIF-AGENT] / [ACIF-MCP] — the six L1 interchange specifications, version 0.1.x, sibling directories under `specs/`.
- [ACIF-RENDER] "ACIF Render-Back Specification", version 0.1.x. `../render-back/spec.md`
- [CHANGE-PROCESS] "ACIF Change Process". `../../CHANGE-PROCESS.md`
- [RFC2119] Bradner, S., "Key words for use in RFCs to Indicate Requirement Levels", BCP 14, RFC 2119, March 1997. <https://www.rfc-editor.org/rfc/rfc2119>
- [RFC8174] Leiba, B., "Ambiguity of Uppercase vs Lowercase in RFC 2119 Key Words", BCP 14, RFC 8174, May 2017. <https://www.rfc-editor.org/rfc/rfc8174>

### 15.2 Informative

- [ACIF-PUBLISHER] "ACIF Publisher Record Specification", version 0.1.x. `../publisher-spec/spec.md`
- [ACIF-REGISTRY] "ACIF Registry Specification", version 0.1.x. `../registry-spec/spec.md`

---

## Appendix A — The Install-Target Matrix (Normative)

### A.1 Ownership

This appendix is normative for the placeholder grammar, the scope and layout enums, the row model, and the entry-point rows as the interoperability contract among ACIF actors. Correspondence of a row to a living provider build is a maintained empirical claim, revised by amendment under the [CHANGE-PROCESS] row-data lane (§12) — a provider release that moves a location makes the matrix *behind*, never *wrong about what conforming tools do*, and the correction lands on observation. Which providers appear at all is observational history: presence of a provider in this matrix asserts that its locations were verified against the build or documentation its rows' `as_of` names, and asserts nothing about providers absent from it.

The machine-readable form of this appendix is `conformance/install-entry-points.yaml`, kept current by the runner selftest's install-entry-points sync check; downstream consumers diff against the export, never against this prose.

### A.2 Entry-point rows

Rows are grouped by provider, then content type; order within a group is normative precedence (§6). Sorting between groups is alphabetical by provider slug, then content type — the pinned canonical export ordering. No `managed` row is published in 0.1: none was in the verified survey, and the enum member awaits its first verified location. Providers are keyed by the slugs the normative appendices already use ([ACIF-HOOK] Appendix A/B columns); the survey basis omitted rows whose location, filename, or scope could not be stated determinately (a bare provider config dir with no per-type naming; a config path whose anchor the survey left ambiguous) — absence asserts nothing (A.1).

*(Informative)* One omission is the named witness for the §8.3 OS-dimension roadmap item: cline's MCP settings file lives under the host editor's per-OS application-data root (`%APPDATA%` / `~/Library/Application Support` / `~/.config`), which no 0.1 template can carry.

| Provider | Type | Scope | Path template | Layout | Status | as_of *(informative)* |
|---|---|---|---|---|---|---|
| `amp` | hook | project | `.amp/settings.json` | merged_into_shared_file | current | syllago 2026-07 survey |
| `amp` | mcp_config | project | `.amp/settings.json` | merged_into_shared_file | current | syllago 2026-07 survey |
| `amp` | rule | user | `~/.config/amp/AGENTS.md` | merged_into_shared_file | current | syllago 2026-07 survey |
| `amp` | rule | project | `AGENTS.md` | merged_into_shared_file | current | syllago 2026-07 survey |
| `amp` | skill | user | `~/.config/agents/skills/<content-name>/` | directory_of_files | current | syllago 2026-07 survey |
| `amp` | skill | project | `.agents/skills/<content-name>/` | directory_of_files | current | syllago 2026-07 survey |
| `claude-code` | agent | user | `~/.claude/agents/<content-name>.md` | single_file | current | syllago 2026-07 survey |
| `claude-code` | agent | project | `.claude/agents/<content-name>.md` | single_file | current | syllago 2026-07 survey |
| `claude-code` | command | user | `~/.claude/commands/<content-name>.md` | single_file | current | syllago 2026-07 survey |
| `claude-code` | command | project | `.claude/commands/<content-name>.md` | single_file | current | syllago 2026-07 survey |
| `claude-code` | hook | user | `~/.claude/settings.json` | merged_into_shared_file | current | syllago 2026-07 survey; installer path table (ADR-0020) |
| `claude-code` | hook | project | `.claude/settings.json` | merged_into_shared_file | current | syllago 2026-07 survey |
| `claude-code` | mcp_config | project | `.mcp.json` | merged_into_shared_file | current | syllago 2026-07 survey |
| `claude-code` | rule | user | `~/.claude/rules/<content-name>.md` | single_file | current | syllago 2026-07 survey |
| `claude-code` | rule | project | `.claude/rules/<content-name>.md` | single_file | current | syllago 2026-07 survey |
| `claude-code` | rule | project | `CLAUDE.md` | merged_into_shared_file | current | syllago 2026-07 survey |
| `claude-code` | skill | user | `~/.claude/skills/<content-name>/` | directory_of_files | current | syllago 2026-07 survey |
| `claude-code` | skill | project | `.claude/skills/<content-name>/` | directory_of_files | current | syllago 2026-07 survey |
| `cline` | command | user | `~/Documents/Cline/Workflows/<content-name>.md` | single_file | current | syllago 2026-07 survey |
| `cline` | command | project | `.clinerules/workflows/<content-name>.md` | single_file | current | syllago 2026-07 survey |
| `cline` | rule | user | `~/Documents/Cline/Rules/<content-name>.md` | single_file | current | syllago 2026-07 survey |
| `cline` | rule | project | `.clinerules/<content-name>.md` | single_file | current | syllago 2026-07 survey |
| `cline` | rule | project | `.clinerules` | merged_into_shared_file | current | syllago 2026-07 survey |
| `cline` | skill | user | `~/.cline/skills/<content-name>/` | directory_of_files | current | syllago 2026-07 survey |
| `cline` | skill | project | `.cline/skills/<content-name>/` | directory_of_files | current | syllago 2026-07 survey |
| `codex` | command | project | `.codex/commands/<content-name>.md` | single_file | current | syllago 2026-07 survey |
| `codex` | hook | project | `.codex/hooks.json` | merged_into_shared_file | current | syllago 2026-07 survey |
| `codex` | mcp_config | user | `~/.codex/config.toml` | merged_into_shared_file | current | syllago 2026-07 survey |
| `codex` | rule | user | `~/.codex/AGENTS.md` | merged_into_shared_file | current | syllago 2026-07 survey |
| `codex` | rule | project | `AGENTS.md` | merged_into_shared_file | current | syllago 2026-07 survey |
| `codex` | skill | user | `~/.agents/skills/<content-name>/` | directory_of_files | current | syllago 2026-07 survey |
| `codex` | skill | project | `.agents/skills/<content-name>/` | directory_of_files | current | syllago 2026-07 survey |
| `copilot-cli` | agent | user | `~/.github/agents/<content-name>.md` | single_file | current | syllago 2026-07 survey |
| `copilot-cli` | agent | project | `.copilot/agents/<content-name>.md` | single_file | current | syllago 2026-07 survey |
| `copilot-cli` | agent | project | `.github/agents/<content-name>.md` | single_file | current | syllago 2026-07 survey |
| `copilot-cli` | command | user | `~/.copilot/commands/<content-name>.md` | single_file | current | syllago 2026-07 survey |
| `copilot-cli` | command | project | `.copilot/commands/<content-name>.md` | single_file | current | syllago 2026-07 survey |
| `copilot-cli` | hook | project | `.github/hooks/<content-name>.json` | single_file | current | syllago 2026-07 survey |
| `copilot-cli` | mcp_config | user | `~/.copilot/mcp-config.json` | merged_into_shared_file | current | syllago 2026-07 survey |
| `copilot-cli` | mcp_config | project | `.copilot/mcp-config.json` | merged_into_shared_file | current | syllago 2026-07 survey |
| `copilot-cli` | rule | project | `.github/copilot-instructions.md` | merged_into_shared_file | current | syllago 2026-07 survey |
| `copilot-cli` | rule | project | `AGENTS.md` | merged_into_shared_file | current | syllago 2026-07 survey |
| `copilot-cli` | skill | user | `~/.github/skills/<content-name>/` | directory_of_files | current | syllago 2026-07 survey |
| `copilot-cli` | skill | project | `.github/skills/<content-name>/` | directory_of_files | current | syllago 2026-07 survey |
| `crush` | hook | user | `~/.config/crush/crush.json` | merged_into_shared_file | current | syllago 2026-07 survey; installer path table (ADR-0020) |
| `crush` | hook | project | `crush.json` | merged_into_shared_file | current | syllago 2026-07 survey |
| `crush` | mcp_config | user | `~/.config/crush/crush.json` | merged_into_shared_file | current | syllago 2026-07 survey |
| `crush` | mcp_config | project | `crush.json` | merged_into_shared_file | current | syllago 2026-07 survey |
| `crush` | rule | project | `AGENTS.md` | merged_into_shared_file | current | syllago 2026-07 survey |
| `crush` | skill | user | `~/.config/crush/skills/<content-name>/` | directory_of_files | current | syllago 2026-07 survey |
| `crush` | skill | project | `.crush/skills/<content-name>/` | directory_of_files | current | syllago 2026-07 survey |
| `cursor` | agent | user | `~/.cursor/agents/<content-name>.md` | single_file | current | syllago 2026-07 survey |
| `cursor` | agent | project | `.cursor/agents/<content-name>.md` | single_file | current | syllago 2026-07 survey |
| `cursor` | hook | user | `~/.cursor/settings.json` | merged_into_shared_file | current | syllago 2026-07 survey; installer path table (ADR-0020) |
| `cursor` | hook | project | `.cursor/settings.json` | merged_into_shared_file | current | syllago 2026-07 survey |
| `cursor` | mcp_config | user | `~/.cursor/mcp.json` | merged_into_shared_file | current | syllago 2026-07 survey |
| `cursor` | mcp_config | project | `.cursor/mcp.json` | merged_into_shared_file | current | syllago 2026-07 survey |
| `cursor` | rule | project | `.cursor/rules/<content-name>.mdc` | single_file | current | syllago 2026-07 survey |
| `cursor` | rule | project | `.cursorrules` | merged_into_shared_file | current | syllago 2026-07 survey |
| `cursor` | skill | user | `~/.cursor/skills/<content-name>/` | directory_of_files | current | syllago 2026-07 survey |
| `cursor` | skill | project | `.cursor/skills/<content-name>/` | directory_of_files | current | syllago 2026-07 survey |
| `factory-droid` | agent | user | `~/.factory/droids/<content-name>.md` | single_file | current | syllago 2026-07 survey |
| `factory-droid` | agent | project | `.factory/droids/<content-name>.md` | single_file | current | syllago 2026-07 survey |
| `factory-droid` | command | user | `~/.factory/commands/<content-name>.md` | single_file | current | syllago 2026-07 survey |
| `factory-droid` | command | project | `.factory/commands/<content-name>.md` | single_file | current | syllago 2026-07 survey |
| `factory-droid` | hook | user | `~/.factory/settings.json` | merged_into_shared_file | current | syllago 2026-07 survey; installer path table (ADR-0020) |
| `factory-droid` | hook | project | `.factory/settings.json` | merged_into_shared_file | current | syllago 2026-07 survey |
| `factory-droid` | mcp_config | user | `~/.factory/mcp.json` | merged_into_shared_file | current | syllago 2026-07 survey |
| `factory-droid` | mcp_config | project | `.factory/mcp.json` | merged_into_shared_file | current | syllago 2026-07 survey |
| `factory-droid` | rule | project | `AGENTS.md` | merged_into_shared_file | current | syllago 2026-07 survey |
| `factory-droid` | skill | user | `~/.factory/skills/<content-name>/` | directory_of_files | current | syllago 2026-07 survey |
| `factory-droid` | skill | project | `.factory/skills/<content-name>/` | directory_of_files | current | syllago 2026-07 survey |
| `gemini-cli` | agent | user | `~/.gemini/agents/<content-name>.md` | single_file | current | syllago 2026-07 survey |
| `gemini-cli` | agent | project | `.gemini/agents/<content-name>.md` | single_file | current | syllago 2026-07 survey |
| `gemini-cli` | hook | user | `~/.gemini/settings.json` | merged_into_shared_file | current | syllago 2026-07 survey; installer path table (ADR-0020) |
| `gemini-cli` | hook | project | `.gemini/settings.json` | merged_into_shared_file | current | syllago 2026-07 survey |
| `gemini-cli` | mcp_config | user | `~/.gemini/settings.json` | merged_into_shared_file | current | syllago 2026-07 survey |
| `gemini-cli` | mcp_config | project | `.gemini/settings.json` | merged_into_shared_file | current | syllago 2026-07 survey |
| `gemini-cli` | rule | user | `~/.gemini/GEMINI.md` | merged_into_shared_file | current | syllago 2026-07 survey |
| `gemini-cli` | rule | project | `GEMINI.md` | merged_into_shared_file | current | syllago 2026-07 survey |
| `gemini-cli` | skill | user | `~/.gemini/skills/<content-name>/` | directory_of_files | current | syllago 2026-07 survey |
| `gemini-cli` | skill | user | `~/.agents/skills/<content-name>/` | directory_of_files | current | syllago 2026-07 survey |
| `gemini-cli` | skill | project | `.gemini/skills/<content-name>/` | directory_of_files | current | syllago 2026-07 survey |
| `gemini-cli` | skill | project | `.agents/skills/<content-name>/` | directory_of_files | current | syllago 2026-07 survey |
| `kiro` | mcp_config | user | `~/.kiro/settings/mcp.json` | merged_into_shared_file | current | syllago 2026-07 survey |
| `kiro` | mcp_config | project | `.kiro/settings/mcp.json` | merged_into_shared_file | current | syllago 2026-07 survey |
| `kiro` | rule | project | `.kiro/steering/<content-name>.md` | single_file | current | syllago 2026-07 survey |
| `opencode` | agent | user | `~/.config/opencode/agents/<content-name>.md` | single_file | current | syllago 2026-07 survey |
| `opencode` | agent | project | `.opencode/agents/<content-name>.md` | single_file | current | syllago 2026-07 survey |
| `opencode` | command | user | `~/.config/opencode/commands/<content-name>.md` | single_file | current | syllago 2026-07 survey |
| `opencode` | command | project | `.opencode/commands/<content-name>.md` | single_file | current | syllago 2026-07 survey |
| `opencode` | mcp_config | project | `opencode.json` | merged_into_shared_file | current | syllago 2026-07 survey |
| `opencode` | mcp_config | project | `opencode.jsonc` | merged_into_shared_file | current | syllago 2026-07 survey |
| `opencode` | rule | user | `~/.config/opencode/AGENTS.md` | merged_into_shared_file | current | syllago 2026-07 survey |
| `opencode` | rule | project | `AGENTS.md` | merged_into_shared_file | current | syllago 2026-07 survey |
| `opencode` | skill | user | `~/.config/opencode/skills/<content-name>/` | directory_of_files | current | syllago 2026-07 survey |
| `opencode` | skill | user | `~/.agents/skills/<content-name>/` | directory_of_files | current | syllago 2026-07 survey |
| `opencode` | skill | project | `.opencode/skills/<content-name>/` | directory_of_files | current | syllago 2026-07 survey |
| `opencode` | skill | project | `.agents/skills/<content-name>/` | directory_of_files | current | syllago 2026-07 survey |
| `pi` | command | user | `~/.pi/agent/prompts/<content-name>.md` | single_file | current | syllago 2026-07 survey |
| `pi` | command | project | `.pi/prompts/<content-name>.md` | single_file | current | syllago 2026-07 survey |
| `pi` | hook | user | `~/.pi/agent/extensions/<content-name>.ts` | single_file | current | syllago 2026-07 survey |
| `pi` | hook | project | `.pi/extensions/<content-name>.ts` | single_file | current | syllago 2026-07 survey |
| `pi` | rule | project | `AGENTS.md` | merged_into_shared_file | current | syllago 2026-07 survey |
| `pi` | skill | user | `~/.pi/agent/skills/<content-name>/` | directory_of_files | current | syllago 2026-07 survey |
| `pi` | skill | project | `.pi/skills/<content-name>/` | directory_of_files | current | syllago 2026-07 survey |
| `roo-code` | command | user | `~/.roo/commands/<content-name>.md` | single_file | current | syllago 2026-07 survey |
| `roo-code` | command | project | `.roo/commands/<content-name>.md` | single_file | current | syllago 2026-07 survey |
| `roo-code` | mcp_config | project | `.roo/mcp.json` | merged_into_shared_file | current | syllago 2026-07 survey |
| `roo-code` | rule | user | `~/.roo/rules/<content-name>.md` | single_file | current | syllago 2026-07 survey |
| `roo-code` | rule | project | `.roo/rules/<content-name>.md` | single_file | current | syllago 2026-07 survey |
| `roo-code` | rule | project | `.roorules` | merged_into_shared_file | current | syllago 2026-07 survey |
| `roo-code` | skill | user | `~/.roo/skills/<content-name>/` | directory_of_files | current | syllago 2026-07 survey |
| `roo-code` | skill | user | `~/.agents/skills/<content-name>/` | directory_of_files | current | syllago 2026-07 survey |
| `roo-code` | skill | project | `.roo/skills/<content-name>/` | directory_of_files | current | syllago 2026-07 survey |
| `roo-code` | skill | project | `.agents/skills/<content-name>/` | directory_of_files | current | syllago 2026-07 survey |
| `windsurf` | command | user | `~/.codeium/windsurf/global_workflows/<content-name>.md` | single_file | current | syllago 2026-07 survey |
| `windsurf` | command | project | `.windsurf/workflows/<content-name>.md` | single_file | current | syllago 2026-07 survey |
| `windsurf` | rule | project | `.windsurf/rules/<content-name>.md` | single_file | current | syllago 2026-07 survey |
| `windsurf` | rule | project | `.windsurfrules` | merged_into_shared_file | current | syllago 2026-07 survey |
| `windsurf` | skill | user | `~/.codeium/windsurf/skills/<content-name>/` | directory_of_files | current | syllago 2026-07 survey |
| `windsurf` | skill | user | `~/.agents/skills/<content-name>/` | directory_of_files | current | syllago 2026-07 survey |
| `windsurf` | skill | project | `.windsurf/skills/<content-name>/` | directory_of_files | current | syllago 2026-07 survey |
| `windsurf` | skill | project | `.agents/skills/<content-name>/` | directory_of_files | current | syllago 2026-07 survey |

## Appendix B — Conformance Test-Vector Family (Normative)

The vectors in this family, published in the `conformance/` directory, are normatively authoritative over prose.

**TV-INSTALL-\***: (a) resolution determinism and multiplicity — a multi-row `(provider, content type)` list resolves every row, order preserved, first-current-row-per-scope identified as the write target, byte-identical across invocations and implementations; (b) layout coverage — resolution exercised across all three layout members and all six content types (the six-coequal witness); (c) content-name validity — separator, backslash, dot-segment, and empty names reject with `acif.install.content_name_invalid` before path formation; (d) placeholder totality — a row carrying a token outside the closed set refuses the write direction with `acif.install.placeholder_unrecognized`; (e) disposition lanes — `no_entry_point` and `scope_unavailable` refuse with pinned `params`, supersession warns with the write proceeding; (f) anchor resolution — home-anchored, project-anchored, and absolute managed templates resolve against invocation-supplied roots deterministically.

Individual vector IDs are assigned in the conformance suite.

## Appendix C — Provenance (Informative)

Minted 2026-07-16 as the install-entry-points expansion (SHAPE.md Decision #41; stabilization-plan Phase 4, Gate C: spec-purist + registry-operator, convergent). The Gate C record: home = a dedicated L5 actor document (this one) rather than a [ACIF-REGISTRY] §8 projection (a frozen table is ACIF's assertion, not a registry derivation) or a render-context input ([ACIF-RENDER] §6.1 pins its context closed; placement is the install tool's act, downstream of bytes); polarity = frozen rows under the deterministic-projection discipline with the row-data amendment lane, rather than an observational §8.4-style snapshot (an install-tool MUST cannot cite stale-able data), with the registry-operator's conditions adopted: the A.1 ownership carve-out, supersession-not-deletion, byte-identical re-serving, refresh-over-vendored consumption, and the amendment lane landing on observation without a batch window.

The matrix rows derive from the provider survey conducted for the shipping install-tool implementation and were verified against provider builds or documentation as the per-row `as_of` records.
