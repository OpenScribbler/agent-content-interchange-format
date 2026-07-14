# ACIF Hook Interchange Specification

**Version:** 0.1.0
**Status:** Draft
**Spec ID:** [ACIF-HOOK]

---

## Abstract

This document defines the canonical interchange form for the hook content type: lifecycle-event-triggered content executed by an AI coding tool. It specifies the canonical hook model, the canonical event vocabulary and handler-type enum, per-operating-system script selection and canonicalization, the hook `body_hash` preimage, derivation predicates, install-time coverage rules, render-back requirements, and the hook error-identifier registry.

## 1. Introduction

A hook binds a provider lifecycle event (a tool call about to execute, a session starting, a prompt being submitted) to one or more handlers the provider runs when the event fires. Providers express hooks in mutually incompatible native formats: different event names, different handler shapes, and four different mechanisms for per-operating-system script variation. This document defines the provider-neutral canonical form that those native formats canonicalize to and render back from.

Hooks are a **sidecar-only** content type ([ACIF-CORE] §6.1): the provider owns the native configuration file, so no frontmatter surface exists. The canonical sidecar is the only carrier, and the executable wiring it carries participates in `body_hash` (§9).

## 2. Relationship to ACIF Core

This document is a Level 1 (L1) companion to [ACIF-CORE] and depends on it normatively. Conformance to this document requires conformance to [ACIF-CORE]; every discipline in [ACIF-CORE] §8 and the capability model in [ACIF-CORE] §9 apply to hooks without restatement. This document adds hook-specific requirements only; it redefines no [ACIF-CORE] term.

This document is compatible with [ACIF-CORE] version 0.1.x. Both documents are Draft maturity; changes to [ACIF-CORE] may require corresponding changes here.

The per-OS script-entry machinery in §7 is defined type-general — it constrains any script entry carrying `os` or `arch` fields — and is instantiated on hooks only in ACIF 0.1. A future L1 specification that acquires OS-variant script entries adopts §7 by normative reference rather than redefining it.

## 3. Terminology

Terms defined in [ACIF-CORE] §2 are used without redefinition. Additionally:

**event** — the canonical lifecycle trigger name (Appendix A) identifying when a hook fires.

**matcher** — an optional pattern string filtering which occurrences of the event fire the hook (e.g., which tool names, for tool events).

**handler** — one typed action the provider performs when the hook fires. Handler types are the closed enum in Appendix B.

**script entry** — one element of a command handler's `scripts` array: an OS-variant carrier of that handler's logical entrypoint.

**default entry** — a script entry with `os` absent. **constrained entry** — a script entry with `os` present.

**target OS** — the operating-system enum member (§7.1) a selection is evaluated against.

**selection** — the total function (§7.3) from target OS to at-most-one script entry per handler.

**wiring** — the canonical hook extension block: everything the sidecar declares about the hook other than referenced file bytes.

## 4. Requirements Language

The key words "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHALL NOT", "SHOULD", "SHOULD NOT", "RECOMMENDED", "NOT RECOMMENDED", "MAY", and "OPTIONAL" in this document are to be interpreted as described in BCP 14 [RFC2119] [RFC8174] when, and only when, they appear in all capitals, as shown here.

## 5. Conformance

This document extends the [ACIF-CORE] §4 conformance classes with hook-specific requirements and adds one class:

**Conforming canonicalizer** — additionally satisfies §6–§9 (model validation, per-OS canonicalization, vocabulary translation, hash preimage).

**Conforming validator** — additionally satisfies the reject conditions in §6–§8 evaluated over canonical form, without re-applying defaults or translations.

**Conforming hook record** — an item with `kind: hook` conforms if it satisfies [ACIF-CORE] §5 and §6 of this document.

**Conforming install tool** — additionally satisfies §11 (coverage-gap rule).

**Conforming renderer** — software that emits a provider-native form from canonical form; satisfies §12.

Registry conformance is defined in [ACIF-REGISTRY]; §13 of this document states the hook-specific compute obligations a conforming registry inherits.

The test-vector families in Appendix C are normatively authoritative: an implementation that contradicts a published vector is non-conformant regardless of any prose reading.

## 6. Canonical Hook Model

### 6.1 Schema

The hook extension block appears below the common envelope when `kind: hook`:

```yaml
hook:
  event: before_tool_execute      # REQUIRED — canonical event name (Appendix A)

  matcher: "file_write|file_edit" # OPTIONAL — event-occurrence filter; canonical tool
                                  # names component-wise ([ACIF-CORE] Appendix A.3)

  handlers:                       # REQUIRED — one or more typed handlers (Appendix B)
    - type: command               # materialized when absent (§8.2)
      scripts:                    # REQUIRED for type: command — OS-variants of ONE
                                  # logical entrypoint (§7)
        - type: file
          path: hooks/check-write
          os: [darwin, linux]     # OPTIONAL — sorted set (§7.1); omit if OS-agnostic
          arch: [amd64, arm64]    # OPTIONAL — advisory in 0.1 (§7.1)
        - type: file
          path: hooks/check-write.cmd
          os: [windows]
        # inline variant:
        # - type: inline
        #   content: |
        #     #!/bin/bash
        #     echo "checked"
        #   os: [darwin, linux]
      async: false                # OPTIONAL — default false
      timeout: 60                 # OPTIONAL
      status_message: "Checking"  # OPTIONAL

  auxiliary_files:                # OPTIONAL — files a script loads at runtime
    - path: hooks/shared-utils.sh #   (not provider-invoked; provider-invoked files
                                  #    belong in scripts)

  blocking: false                 # OPTIONAL — default false; the criticality
                                  # discriminant for §11

  requires: {}                    # OPTIONAL — empty/absent in 0.1 (§10)

  activation_target:              # OPTIONAL — present when this hook activates a skill
    skill:
      id: "550e8400-..."          # REQUIRED — target skill item UUID (load-bearing)
      name: "tdd-workflow"        # OPTIONAL — advisory only
```

### 6.2 Field requirements

**`event`** — REQUIRED. In canonical form, MUST be a canonical event name from Appendix A, matched by exact byte comparison. Canonicalization translates provider-native event names per the Appendix A mapping; a name that is neither canonical nor a provider-native name appearing in Appendix A MUST be rejected with `acif.hook.event_unrecognized`. *(Informative: restricting recognition to the pinned tables guards against key-injection via crafted event names.)*

**`matcher`** — OPTIONAL. When present, MUST be non-empty ([ACIF-CORE] §8.3). Canonicalization translates matcher components per [ACIF-CORE] Appendix A.3. Absent in canonical form when the source carries no matcher or an empty one.

**`handlers`** — REQUIRED, one or more entries; an absent or empty `handlers` array MUST be rejected with `acif.hook.handlers_missing`. Handler order is semantically significant (it is the execution order for the event) and is preserved through canonicalization and serialization. Each entry's `type` MUST be a member of the Appendix B enum in canonical form; the absent-type legacy residual is materialized per §8.2. Fields meaningful per type are listed in Appendix B; a handler carrying a field not meaningful for its type retains it as opaque passthrough ([ACIF-CORE] §8.5).

**`scripts`** — REQUIRED on every `type: command` handler, one or more entries; MUST NOT appear on other handler types. Each entry carries `type: file` with `path`, or `type: inline` with `content`; `os` and `arch` are OPTIONAL per §7. Entries are OS-variants of the handler's single logical entrypoint — they are alternatives selected by target OS, not a sequence.

**`auxiliary_files`** — OPTIONAL. Runtime dependencies of scripts. Each entry's `path` names a file included in the hash manifest (§9.2).

**`async`** — OPTIONAL boolean on `type: command` handlers (Appendix B), default `false`, materialized at canonicalization ([ACIF-CORE] §8.1): canonical form always carries an explicit `async` on every command handler, and the materialized value enters the §9.3 wiring serialization. Declares that the provider runs the handler without awaiting its completion.

**`blocking`** — OPTIONAL boolean, default `false`, materialized at canonicalization ([ACIF-CORE] §8.1). Declares that the provider should treat the hook's outcome as gating.

**`requires`** — OPTIONAL. The recognized `requires` vocabulary for hooks is empty in ACIF 0.1 (§10); any key present is non-conformant ([ACIF-CORE] §9.4).

**`activation_target`** — OPTIONAL. When present, `skill.id` is REQUIRED and is the load-bearing reference ([ACIF-CORE] §10); `skill.name` is advisory only. Canonical truth for hook→skill activation lives on the hook; the skill side's `activation` block is a discovery convenience defined in [ACIF-SKILL].

### 6.3 Model unification note *(informative)*

Earlier design snapshots showed the command entrypoint's `scripts` array at the top of the hook block and referenced handler fields (`Hooks[i].Type`, `Matcher`, `Hooks[i].Async`) in predicate notation without showing them in the schema. This document unifies the two views: `handlers` is the array the predicate notation's `Hooks[i]` denotes, and `scripts` lives on each command handler, since it carries that handler's entrypoint. A source configuration declaring several handlers for one event canonicalizes to one hook item with several `handlers` entries.

## 7. Per-OS Script Entries

This section is written type-general — it constrains any script entry carrying `os` or `arch` — and is instantiated on hooks in ACIF 0.1.

### 7.1 Closed OS enum; absence and empty semantics

- `os` values form the closed enum `{windows, linux, darwin}`, matched by exact byte comparison ([ACIF-CORE] §8.3). A non-member value MUST be rejected with `acif.hook.script_os_invalid`. Provider aliases (e.g., `osx`) are rewritten before validation and MUST NOT survive into canonical form.
- **`os` absent means unconstrained**: the entry is a selection candidate on every enum member. Absence MUST NOT be canonicalized to the full enumeration `[darwin, linux, windows]` — the two forms are distinct canonical bytes, and rewriting one into the other silently moves `body_hash`.
- **`os: []` is not absence**: an empty array matches nothing, making the entry unreachable; it MUST be rejected with `acif.hook.script_os_empty` (an empty `arch` array likewise: `acif.hook.script_arch_empty`).
- **`arch` does not participate in selection in ACIF 0.1.** It is carried in canonical form and surfaced as advisory registry data (§13.1). Selection on `arch` is a roadmap item gated on a closed arch enum with alias mapping.
- **Canonical array order:** `os` and `arch` express sets, not sequences. In canonical form their elements MUST be sorted by raw UTF-8 byte order and MUST NOT contain duplicates. Two sources differing only in tag order canonicalize to identical bytes and identical `body_hash`.

### 7.2 Disjointness at canonicalization

Define the match predicate over a script entry `E` and target OS `o`:

```
M(E, o) := (E.os absent) ∨ (o ∈ E.os)
```

An entry with `os` absent is a **default entry**; any other entry is a **constrained entry**.

For each command handler's `scripts` array, canonicalization MUST verify:

1. At most one default entry. Violation → `acif.hook.script_default_ambiguous`.
2. For every enum member `o`, at most one constrained entry matches `o`. Violation → `acif.hook.script_platform_ambiguous`; the diagnostic MUST name the colliding OS value(s) and the colliding entry indices.

Both diagnostics MUST be fix-forward ([ACIF-CORE] §8.7): they name the remedy (add explicit `os:` tags that partition the enum).

*(Informative)* Ambiguity is rejected at canonicalization rather than tie-broken at runtime. A specificity ordering was considered and rejected: overlapping `os`×`arch` coverage sets are incomparable, and a most-specific-wins rule is silent exactly where it is needed — two conforming providers would run different scripts. Note also that the common untagged multi-script layout (`.sh` + `.ps1` + `.cmd`, no tags) rejects as multiple default entries. That layout genuinely is ambiguous under these semantics; the fix-forward diagnostic is the adoption mitigation, and registries are advised to measure reject rates on representative crawls.

### 7.3 Selection

Runtime selection for a command handler on target OS `o*` is total:

1. If exactly one constrained entry matches `o*`, that entry is selected.
2. Otherwise, if a default entry exists, it is selected.
3. Otherwise no entry is selected: the handler is a **defined no-op** on `o*`, and implementations MUST report `acif.hook.script_no_platform_match` when this branch is taken.

The only precedence is constrained-beats-default. Disjointness (§7.2) guarantees step 1 is unambiguous; incomparability can never reach selection.

### 7.4 Provider-mechanism canonicalization mapping

The mapping from observed provider per-OS mechanisms to canonical script entries is total over the surveyed space; anything outside it rejects.

| Source mechanism | Canonical mapping | Diagnostics / provenance |
|---|---|---|
| Per-OS key map (`windows` / `linux` / `osx` keys, each with a command) plus a base command | Each per-OS key → a singleton constrained entry (`osx` renamed `darwin` before validation); after the key mapping, constrained entries with identical executable identity (§13.1: `(type, path)` for `type: file`; `(type, SHA-256(content))` for `type: inline`, content normalized per §9.3) MUST be merged into a single entry whose `os` set is the sorted union (§7.1); the base command → the default entry | Lossless; provenance `declared` |
| Dual shell fields (`bash` and `powershell` commands) | `bash` → constrained entry `os: [darwin, linux]`; `powershell` → constrained entry `os: [windows]` | MUST emit `acif.hook.platform_shell_os_proxy`; provenance `inferred-from-convention` |
| Filename-extension convention | `.ps1` / `.cmd` / `.bat` → `os: [windows]`; `.sh` and extensionless → `os: [darwin, linux]`; any other extension → default entry, MUST emit `acif.hook.platform_filename_uninferable`; successful inference MUST emit `acif.hook.platform_filename_inferred` (INFORMATIVE) | Provenance `inferred-from-convention` |
| Single interpreter-selection field on one command (e.g., `shell: powershell`) | Excluded from OS mapping — one entrypoint plus an interpreter flag is nothing to map; the field is carried as opaque passthrough | See §12.3 (structured encoder); the value participates in the hash preimage (§9) |
| Single command, no per-OS mechanism | Default entry | — |
| Any unmapped mechanism | MUST reject `acif.hook.platform_unmappable` | Totality net |

*(Informative)* The shell-field collapse is semantically wrong as a general claim — PowerShell is cross-platform, and bash exists on Windows — and is retained on the entrypoint-count rationale: two distinct command fields are two entrypoints, hence mappable, whereas an interpreter flag on one command is one entrypoint. The mandatory diagnostics and `inferred-from-convention` provenance exist because these rows mint an OS tag the author never wrote. The extension convention has a disclosed false mapping: an extensionless script with a PowerShell shebang infers unix.

### 7.5 Tag provenance

Each `os` tag in canonical form has a decode-time provenance: **declared** (present in the source) or **inferred-from-convention** (minted by a §7.4 heuristic row). Provenance is registry observation metadata, not canonical-form content: it is recorded by the canonicalizing registry for projection (§13.1) and is NOT part of the `body_hash` preimage. A guessed tag MUST remain distinguishable from an authored one on registry surfaces. Selection (§7.3) uses canonical tags uniformly regardless of provenance.

## 8. Vocabulary Canonicalization

### 8.1 Event names

Canonicalization rewrites provider-native event names to the canonical vocabulary (Appendix A) before `body_hash` is computed ([ACIF-CORE] §8.2). Reverse translation applies the pinned tiebreaker in Appendix A.3; for any multi-match without a pinned row, the lexicographically smaller canonical name wins ([ACIF-CORE] §8.4).

### 8.2 Handler types

Canonicalization rewrites provider-native handler-type names to the Appendix B enum. **Legacy residual:** a source handler with `type` absent or empty is a `command` handler; the canonicalizer MUST materialize the explicit `type: command` before `body_hash` is computed, and validators MUST NOT re-apply the default ([ACIF-CORE] §8.1). A handler type that is neither canonical nor a provider-native name appearing in Appendix B MUST be rejected with `acif.hook.handler_type_unrecognized`.

## 9. The Hook `body_hash` Preimage

Hooks are sidecar-only, so [ACIF-CORE] §7.7 applies: the preimage covers referenced file bytes plus the canonical wiring. This section pins the exact construction. Test vector family TV-PLATFORM (q) (Appendix C) enforces it.

### 9.1 Inputs

All inputs are taken from the **post-canonicalization** form: after §7.4 mapping, §8 vocabulary translation, and §8.2/§6.2 default materialization.

### 9.2 File manifest

The referenced-file set of a hook is: every `type: file` script entry's `path` across all handlers, plus every `auxiliary_files` entry's `path`. Each referenced file MUST exist at ingestion ([ACIF-CORE] §2); a conforming canonicalizer MUST reject a missing referenced file with `acif.hook.script_file_missing`.

Every `path` MUST be relative with `/` separators and MUST NOT contain a `.` or `..` segment, a leading `/`, a Windows drive or UNC prefix, or a `\` byte; a violating path MUST be rejected with `acif.hook.script_path_invalid`. Paths resolve against the item's **source root**: the base directory the ingestion context designates for the item — for a provider-native configuration, the directory against which the source provider resolves the same paths; for an ACIF-authored sidecar, the sidecar file's directory.

Build the manifest exactly as in [ACIF-CORE] §7.4, with these bindings:

- The entry key is the `path` string as written in canonical form, normalized to Unicode NFC, POSIX separators. Duplicate paths appear once.
- Each file's per-file hash follows [ACIF-CORE] §7.3 (text/binary classification, BOM strip, CRLF→LF for text).
- Symbolic links are rejected; version-control directory components are not applicable (paths are explicit).
- Entries are sorted by raw UTF-8 byte order of the key; each line is `<lowercase-hex-hash><SP><SP><path><LF>`.

The manifest MAY be empty (a hook whose scripts are all `type: inline` and which has no auxiliary files).

Let `DH` be the string `sha256:` followed by the lowercase hex SHA-256 of the manifest bytes (of the empty byte string when the manifest is empty).

### 9.3 Wiring serialization

Let `W` be the canonical JSON serialization ([ACIF-CORE] §8.6, RFC 8785) of the complete canonical `hook` extension-block object with absent fields omitted. There is no field-level selection: every field of the canonical block enters `W`, including handler fields (`async`, `timeout`, `status_message`, per-type fields), every script entry (`type`, `path` or `content`, `os`, `arch`), all opaque passthrough fields (such as an interpreter-selection field), `event`, `matcher`, `auxiliary_files`, `blocking`, `requires`, and `activation_target`. The field list here is illustrative, not exhaustive.

Array ordering in `W` ([ACIF-CORE] §8.6):

- `handlers` — order significant, preserved (§6.2).
- `os`, `arch` — sorted, duplicate-free sets (§7.1).
- `scripts` within a handler — order not significant; entries MUST be sorted by the raw UTF-8 byte order of each entry's own canonical JSON serialization.
- `auxiliary_files` — entries MUST be sorted by the raw UTF-8 byte order of `path`; duplicate paths appear once.

**Inline content normalization:** a `type: inline` entry's `content` string is normalized at canonicalization exactly as a text file is under [ACIF-CORE] §7.3 — leading UTF-8 BOM stripped, CRLF and lone CR normalized to LF — before entering `W` (and before the §13.1 executable-identity hash). Inline and file-carried scripts therefore normalize identically.

### 9.4 Preimage and value

```
preimage        = UTF8(DH) || 0x0A || W || 0x0A
body_hash.value = lowercase-hex( SHA-256(preimage) )
body_hash.algorithm = sha256
```

Consequences (normative in effect, stated for clarity): re-targeting an `os` tag with script bytes unchanged moves `body_hash`; flipping an opaque interpreter-selection value moves `body_hash`; re-pointing `event` or `activation_target` moves `body_hash`; editing any referenced file moves `body_hash`. The registry change signal ([ACIF-CORE] §6.2) therefore covers routing, not only content.

*(Informative)* The common envelope (`display_name`, `description`, `version`, `license`) is not part of the preimage: envelope fields are metadata. A hook crawled from provider-native configuration has no `publisher_section` and no `metadata_hash`; when a publisher-authored sidecar declares envelope metadata, an envelope-only `publisher_section` and its `metadata_hash` exist per [ACIF-CORE] §7.8 and [ACIF-PUBLISHER] — the hook extension block is never duplicated there. A display-name edit moves at most `metadata_hash`; everything executable or routing-relevant moves `body_hash`.

## 10. Capability Dispositions and Derivation Predicates

The recognized `requires` vocabulary for hooks is **empty** in ACIF 0.1. Every capability key of the hook vocabulary is disposed per [ACIF-CORE] §9.2 as follows.

### 10.1 DERIVABLE keys

| Key | D_K over canonical body B |
|---|---|
| `handler_types` | `∃ i . B.handlers[i].type ≠ ""` — constant derivable-true on a conforming record (`handlers` is REQUIRED and non-empty, §6.2); the predicate exists as a disposition, not a signal. The derivable-false case is unreachable on valid input: an empty `handlers` array rejects with `acif.hook.handlers_missing` before any predicate runs. The set of distinct types observed is a registry projection, not the predicate output. |
| `matcher_patterns` | `B.matcher present` (present implies non-empty per §6.2) |
| `async_execution` | `∃ i . B.handlers[i].async == true` |

Each predicate produces `{derivable-true, derivable-false}` per the boolean discipline; each conjunct cites a single canonical field validated at canonicalization before the predicate runs.

*(Informative)* The registry projection `os_coverage` (§13.1) is likewise a correct-by-construction derivation over the canonical body, but it is a registry-projection surface, not a member of the hook `requires` vocabulary disposed here; the disposed vocabulary has exactly three DERIVABLE keys.

### 10.2 OUT-OF-SCOPE-AT-L1 keys *(informative rationale)*

`hook_scopes` is install-location-determined; the canonical body carries no install path. `decision_control`, `input_modification`, `json_io_protocol`, `context_injection`, and `permission_control` are script-body-opaque: their semantics live in script bytes that the canonical wiring carries without parsing, so no canonical field can carry them and no derivation is possible. Under the out-of-band guardrail ([ACIF-CORE] §9.3) none is `requires`-eligible: their evidence is in the body.

Runtime hints (e.g., `python: ">=3.10"`) are the predicted first genuine `requires` tenant and are a roadmap item, not part of 0.1.

### 10.3 Orphan keys

Any `requires.<key>` on a hook item — including the keys named in §10.1 and §10.2 — is non-conformant ([ACIF-CORE] §9.4). An unrecognized key evaluated by a consumer follows the three-valued rule ([ACIF-CORE] §9.5).

## 11. Install-Time Coverage-Gap Rule

Selection (§7.3) is total, so a hook can resolve to a defined no-op on an install target. For each install-target OS segment, a conforming install tool evaluates each command handler:

| Condition on the segment | Install-tool behavior |
|---|---|
| A default entry exists, or a constrained entry matches | Proceed |
| No match, no default, and `blocking: true` | MUST refuse installation on that segment, with operator opt-in to override |
| No match, no default, and `blocking: false` | SHOULD warn with `acif.hook.script_no_platform_match` (install-time class); install proceeds and the handler is a defined no-op on that segment |

The identifier `acif.hook.script_no_platform_match` serves two distinct obligations: §7.3 binds whichever implementation *evaluates selection* (MUST report when the no-op branch is taken), while this section binds the install tool *predicting coverage* before installation (SHOULD warn, upgraded to MUST refuse by the `blocking: true` row). The two obligations never bind the same actor for the same act.

*(Informative)* A `blocking: true` hook is by declaration a gate; installing it where it silently never fires is a fail-open control — the deployment inventory shows the control present while the target platform never runs it. `blocking` is the criticality discriminant already in the schema; no separate severity field exists.

## 12. Render-Back Requirements

These requirements bind conforming renderers; the general render-back framework is [ACIF-RENDER].

### 12.1 Degradation to no-mechanism providers

Rendering to a provider with no per-OS mechanism: emit the default entry, drop constrained entries, and MUST emit `acif.hook.platform_override_dropped` for the drop. Absence of the diagnostic on a drop is non-conformant.

### 12.2 No-default degradation

Rendering an all-constrained hook (no default entry) to a no-mechanism provider is keyed on the selection result: if the render context declares a target OS and §7.3 selection for that OS yields an entry, emit that entry; in every other case — no target OS declared, or the declared target OS yields no selection — the renderer MUST refuse with `acif.hook.no_default_for_degraded_render`. *(Informative: this is the one refuse outcome in hook render-back — without a selected entry, every choice of emitted output is wrong for some deployment, so no defined-safe output exists.)*

### 12.3 Passthrough and round-trip

- All opaque passthrough values MUST be re-serialized through the target format's structured encoder ([ACIF-CORE] §8.5); string-splicing is non-conformant.
- A default entry made unreachable by full constrained coverage MUST NOT be stripped at render-back; removing it breaks round-trip to source formats in which the base command is required.
- Event and handler-type names are translated to provider-native names per Appendix A/B; canonical names with no mapping row for the target emit verbatim ([ACIF-CORE] §8.5).
- *(Informative)* Round-trip through a per-OS key-map provider is identity-preserving because re-ingestion applies the §7.4 identity-merge: an entry constrained to multiple OSes necessarily renders to one key per OS, and the merge collapses those keys back to the single entry. Without the merge, round-trip identity would be unachievable for any multi-OS constrained entry.

## 13. Registry Projections

The projections in this section are computed by registries over the canonical body ([ACIF-REGISTRY] defines the response surface). Every field is a derivation — correct by construction over canonical structure — never a heuristic.

### 13.1 `os_coverage`

A conforming registry MUST compute the `os_coverage` projection for every hook item at ingest:

```yaml
os_coverage:
  derivable: true          # ∃ script entry with os present
  os: [darwin, linux]      # union of declared os tags, sorted (§7.1)
  arch: []                 # union of declared arch tags (advisory)
  unconstrained: true      # ∃ default entry ("is there a run-anywhere fallback?")
  os_divergent: false      # see predicate below
  provenance: declared     # declared | inferred-from-convention | mixed (§7.5)
```

**`os_divergent` predicate:** define a script entry's executable identity as `(type, path)` for `type: file` and `(type, SHA-256(content))` for `type: inline` (content normalized per §9.3). A command handler is divergent iff there exist enum members `o1 ≠ o2` whose §7.3 selections both exist and have different executable identities. `os_divergent` is true iff any handler is divergent. *(Informative: path-based identity for file entries is intentionally conservative — identical bytes at two distinct paths read as divergent; false negatives are impossible.)*

*(Informative)* The `os` set alone cannot distinguish one portable script tagged for three OSes from three different per-OS programs; `os_divergent` is the boolean that makes a fleet policy such as "no OS-divergent hooks" implementable. `provenance` is `declared` when no tag was minted by a §7.4 heuristic row, `inferred-from-convention` when all were, `mixed` otherwise.

### 13.2 `event_provider_coverage`

Registries MUST compute, per canonical event name, the set of providers recognizing the event, from provider capability-matrix data. This is a shared matrix fact, not per-item compute; it supports installer-side event-coverage filtering. Surface requirements live in [ACIF-REGISTRY].

## 14. Error Identifiers

| Identifier | Class | Condition |
|---|---|---|
| `acif.hook.event_unrecognized` | reject | Event name neither canonical nor a mapped provider-native name (§6.2) |
| `acif.hook.handlers_missing` | reject | `handlers` absent or empty (§6.2) |
| `acif.hook.handler_type_unrecognized` | reject | Handler type neither canonical nor a mapped provider-native name (§8.2) |
| `acif.hook.script_os_invalid` | reject | `os` value outside the closed enum, or inexact byte form (§7.1) |
| `acif.hook.script_os_empty` | reject | `os: []` (§7.1) |
| `acif.hook.script_arch_empty` | reject | `arch: []` (§7.1) |
| `acif.hook.script_default_ambiguous` | reject | More than one default entry in a handler's scripts (§7.2) |
| `acif.hook.script_platform_ambiguous` | reject | Two constrained entries match one OS (§7.2) |
| `acif.hook.script_file_missing` | reject | Referenced script/auxiliary file absent at ingestion (§9.2) |
| `acif.hook.script_path_invalid` | reject | Referenced path absolute, traversing, or non-POSIX (§9.2) |
| `acif.hook.platform_unmappable` | reject | Provider per-OS mechanism outside the §7.4 table |
| `acif.hook.no_default_for_degraded_render` | refuse (render) | §12.2 |
| `acif.hook.platform_override_dropped` | diagnostic (MUST-emit) | Constrained entries dropped at degraded render (§12.1) |
| `acif.hook.platform_shell_os_proxy` | diagnostic (MUST-emit) | OS tags minted from dual shell fields (§7.4) |
| `acif.hook.platform_filename_uninferable` | diagnostic (MUST-emit) | Extension convention could not infer an OS (§7.4) |
| `acif.hook.platform_filename_inferred` | diagnostic (INFORMATIVE) | Extension convention minted an OS tag (§7.4) |
| `acif.hook.script_no_platform_match` | diagnostic (runtime MUST-report; install-time SHOULD-warn) | Selection resolved, or would resolve, to the defined no-op (§7.3, §11) |

Reject-class identifiers make canonicalization fail; diagnostic-class identifiers accompany successful processing. All reject diagnostics for authoring errors are fix-forward ([ACIF-CORE] §8.7).

## 15. Security Considerations

**Review evasion via OS divergence.** A per-OS-divergent hook resolves to a branch that reviewers on other operating systems never execute. Severity is HIGH in the review-evasion direction: review fleets are commonly single-OS, and the divergence is invisible without the §13.1 signals. This is not a new attack class — it is conditional-payload gating with the OS axis made legible in structure — and its moderation priority sits below always-executing content classes, because the divergence gates an existing execution primitive rather than adding one.

**What `body_hash` buys — and does not.** With the §9 preimage, `body_hash` is anti-swap (all branches and all routing bound into one value; no substitution between review and delivery) and anti-blindness (an OS re-target or interpreter flip fires the change signal). It does not establish that any branch was inspected: a malicious branch can be present in the attested artifact, committed by every hash, and scrutinized by no one. Moderation pipelines should scan all branches, not the scanning host's branch — the cheapest attack places the payload in the branch the moderation stack analyzes worst.

**The decoy shape is well-formed.** One benign default entry plus one malicious `os: [windows]` override passes every §7.2 check and resolves cleanly to the malicious branch on Windows. Ambiguity rejection closes non-determinism, not divergence abuse; the countermeasures are the `os_divergent` and `provenance` signals, whole-branch moderation, and (roadmap) behavioral verification.

**Heuristically minted tags.** The §7.4 inference rows manufacture OS tags the author never wrote, and a false tag misroutes scanners (an extensionless PowerShell script inferred unix runs on Windows anyway when an operator invokes it). Provenance tagging (§7.5) exists so no downstream policy treats a guessed tag as an authored fact.

**Coverage gaps fail open.** §11 exists because a `blocking: true` control that silently no-ops on part of a fleet is indistinguishable from a deployed control in inventory. Refusal-with-override is the fail-closed default.

**Source-is-artifact.** For `type: file` entries the canonical body is the source — there is no separate build artifact — so `body_hash` plus an https-only fetch pointer gives source-to-artifact correspondence by construction. A checked-in **binary** in `scripts` re-opens the opaque-artifact shape and warrants higher moderation scrutiny.

**No revocation primitive.** ACIF 0.1 has no content-revocation or advisory feed; registry delisting stops new installs only. Containment of an already-installed malicious hook is out of scope for 0.1 and recorded as a HIGH-severity roadmap item keyed on `body_hash`.

**Prompt-bearing handlers.** `prompt` and `agent` handlers carry text that becomes model instructions; injection content there is load-bearing even though no script executes.

## 16. References

### 16.1 Normative

- [ACIF-CORE] "ACIF Core Specification", version 0.1.x. `../core/spec.md`
- [RFC2119] Bradner, S., "Key words for use in RFCs to Indicate Requirement Levels", BCP 14, RFC 2119, March 1997. <https://www.rfc-editor.org/rfc/rfc2119>
- [RFC8174] Leiba, B., "Ambiguity of Uppercase vs Lowercase in RFC 2119 Key Words", BCP 14, RFC 8174, May 2017. <https://www.rfc-editor.org/rfc/rfc8174>
- [RFC8785] Rundgren, A., Jordan, B., Erdtman, S., "JSON Canonicalization Scheme (JCS)", RFC 8785, June 2020. <https://www.rfc-editor.org/rfc/rfc8785>

### 16.2 Informative

- [SHAPE] ACIF design record: `SHAPE.md`, `panel/hooks-requires-consensus.md`, and `panel/platform-commands-consensus.md` in the ACIF repository — decision provenance (Decisions #6, #19, #21, #23, #29, #33).

---

## Appendix A — Canonical Hook Event Vocabulary (Normative)

This appendix is ACIF-owned normative text; implementations conform to this copy. It is normative for the canonical names, the render-back targets of each mapping, and the tiebreakers; which providers carry a name for an event is observational snapshot data.

### A.1 Canonical names and provider mappings (39 events)

| Canonical | Provider mappings |
|---|---|
| `before_tool_execute` | claude-code `PreToolUse` · gemini-cli `BeforeTool` · copilot-cli `preToolUse` · kiro `preToolUse` · cursor `PreToolUse` · opencode `tool.execute.before` · vs-code-copilot `PreToolUse` · factory-droid `PreToolUse` · pi `tool_call` |
| `after_tool_execute` | claude-code `PostToolUse` · gemini-cli `AfterTool` · copilot-cli `postToolUse` · kiro `postToolUse` · cursor `PostToolUse` · opencode `tool.execute.after` · vs-code-copilot `PostToolUse` · factory-droid `PostToolUse` · pi `tool_result` |
| `before_prompt` | claude-code `UserPromptSubmit` · gemini-cli `BeforeAgent` · copilot-cli `userPromptSubmitted` · kiro `userPromptSubmit` · cursor `UserPromptSubmit` · windsurf `pre_user_prompt` · vs-code-copilot `UserPromptSubmit` · factory-droid `UserPromptSubmit` · pi `input` |
| `agent_stop` | claude-code `Stop` · gemini-cli `AfterAgent` · kiro `stop` · copilot-cli `agentStop` · cursor `Stop` · windsurf `post_cascade_response` · opencode `session.idle` · vs-code-copilot `Stop` · factory-droid `Stop` · pi `agent_end` |
| `session_start` | claude-code `SessionStart` · gemini-cli `SessionStart` · copilot-cli `sessionStart` · kiro `agentSpawn` · cursor `SessionStart` · windsurf `session_start` · opencode `session.created` · vs-code-copilot `SessionStart` · factory-droid `SessionStart` · pi `session_start` |
| `session_end` | claude-code `SessionEnd` · gemini-cli `SessionEnd` · copilot-cli `sessionEnd` · cursor `SessionEnd` · windsurf `session_end` · factory-droid `SessionEnd` · pi `session_shutdown` |
| `before_compact` | claude-code `PreCompact` · gemini-cli `PreCompress` · cursor `PreCompact` · vs-code-copilot `PreCompact` · factory-droid `PreCompact` · pi `session_before_compact` |
| `notification` | claude-code `Notification` · gemini-cli `Notification` |
| `subagent_start` | claude-code `SubagentStart` · cursor `SubagentStart` · vs-code-copilot `SubagentStart` · factory-droid `SubagentStart` · pi `before_agent_start` |
| `subagent_stop` | claude-code `SubagentStop` · copilot-cli `subagentStop` · cursor `SubagentStop` · vs-code-copilot `SubagentStop` · factory-droid `SubagentStop` |
| `error_occurred` | claude-code `ErrorOccurred` · copilot-cli `errorOccurred` · opencode `session.error` |
| `tool_use_failure` | claude-code `PostToolUseFailure` · cursor `postToolUseFailure` · copilot-cli `errorOccurred` |
| `permission_request` | claude-code `PermissionRequest` · opencode `permission.asked` |
| `after_compact` | claude-code `PostCompact` |
| `instructions_loaded` | claude-code `InstructionsLoaded` |
| `config_change` | claude-code `ConfigChange` |
| `worktree_create` | claude-code `WorktreeCreate` · windsurf `post_setup_worktree` |
| `worktree_remove` | claude-code `WorktreeRemove` |
| `elicitation` | claude-code `Elicitation` |
| `elicitation_result` | claude-code `ElicitationResult` |
| `teammate_idle` | claude-code `TeammateIdle` |
| `task_completed` | claude-code `TaskCompleted` |
| `stop_failure` | claude-code `StopFailure` |
| `before_model` | gemini-cli `BeforeModel` · cursor `beforeAgentResponse` |
| `after_model` | gemini-cli `AfterModel` · cursor `afterAgentResponse` |
| `before_tool_selection` | gemini-cli `BeforeToolSelection` · cursor `beforeToolSelection` |
| `file_changed` | claude-code `FileChanged` · cursor `afterFileEdit` · kiro `File Save` · opencode `file.edited` |
| `file_created` | kiro `File Create` |
| `file_deleted` | kiro `File Delete` |
| `before_task` | kiro `Pre Task Execution` |
| `after_task` | kiro `Post Task Execution` |
| `transcript_export` | windsurf `post_cascade_response_with_transcript` |
| `turn_start` | pi `turn_start` |
| `turn_end` | pi `turn_end` |
| `model_select` | pi `model_select` |
| `user_bash` | pi `user_bash` |
| `context_update` | pi `context` |
| `message_start` | pi `message_start` |
| `message_end` | pi `message_end` |

### A.2 Event-name validity

An event name is recognized if and only if it is a canonical name in A.1 or a provider-native name appearing in A.1. Any other name rejects per §6.2.

### A.3 Reverse-translation tiebreaker

copilot-cli maps BOTH `error_occurred` and `tool_use_failure` to `errorOccurred`; reverse translation MUST prefer `error_occurred`. For any other multi-match, the lexicographically smaller canonical name wins ([ACIF-CORE] §8.4).

*(Informative)* Approximately 16 events have single-provider coverage. Coverage is observational; the canonical vocabulary is not relaxed by low coverage.

## Appendix B — Canonical Handler-Type Enum (Normative)

`handlers[i].type ∈ {command, http, prompt, agent}` — closed enum, exact byte match ([ACIF-CORE] §8.3). Fields meaningful per type:

| Type | Fields |
|---|---|
| `command` | `scripts`, `timeout`, `status_message`, `async` |
| `http` | `url`, `headers`, `allowed_env_vars`, `timeout`, `status_message` |
| `prompt` | `prompt`, `model`, `timeout`, `status_message` |
| `agent` | `agent`, `timeout`, `status_message` |

The absent-type legacy residual materializes to `command` per §8.2.

The provider-native handler-type alias set of this appendix is **empty** in ACIF 0.1: no provider is known to spell these types differently, so the §8.2 reject fires on any non-canonical `type` value, and the absent-type residual is the only mapping.

## Appendix C — Conformance Test-Vector Families (Normative)

The vectors in these families, published in the `conformance/` directory, are normatively authoritative over prose. Family definitions:

**TV-HOOK-\*** (capability model): (a) empty `requires` conformant; (b) orphan-key reject (`requires.handler_types` on a hook); (c) unknown-key three-valued evaluation; (d) `D_K` handler_types — derivable-true on a conforming record; the empty-`handlers` input tests the `acif.hook.handlers_missing` reject, not a derivable-false result (the derivable-false branch is unreachable on valid input, §10.1); (e) `D_K` matcher_patterns; (f) `D_K` async_execution; (g) canonical event-name round-trip, `body_hash` post-translation; (h) canonical handler-type round-trip; (i) missing referenced file — a `type: file` script path with no file at ingestion → `acif.hook.script_file_missing`; (j) invalid referenced path — an absolute path and a `..`-traversing path each → `acif.hook.script_path_invalid`.

**TV-PLATFORM-\*** (per-OS selection, canonicalization, hash coverage): (a) absence=all; (b) constrained-beats-default; (c) empty-list rejects; (d) invalid OS values (`freebsd`; case-variant `Linux`); (e) default ambiguity; (f) constrained overlap with named colliding OS + indices; (g) disjoint set passes; (g′) decoy accept — one default + one `os:[windows]` ACCEPTS (documents that selection determinism is not divergence safety); (h) no-match no-default → defined no-op + diagnostic; (i) per-OS key-map canonicalization to four disjoint entries, `body_hash` post-mapping; (i′) per-OS key map with duplicate executable identity — the §7.4 identity-merge collapses the duplicate-path keys to one constrained entry with sorted `os` union, `body_hash` pinned on the merged form; (j) `osx` never in canonical form; (k) shell-field collapse + MUST `platform_shell_os_proxy` + provenance; (l) extension-convention table incl. `.cmd`/`.bat`, `.xyz` → default + `platform_filename_uninferable`, and the disclosed false mapping (extensionless pwsh shebang infers unix); (m) interpreter-flag exclusion — no `os` synthesized; render-back structured-encodes an injection-shaped passthrough value; (n) `platform_unmappable`; (o) render-back drop + MUST `platform_override_dropped`; (p) no-default render: selected-entry emit when the declared target OS yields a selection; refuse both when no target is declared and when the declared target yields no selection; (q) **hash coverage — flipping one `os` tag with script bytes unchanged MUST move `body_hash`; flipping an interpreter-selection passthrough value likewise** (this vector fails against any implementation that omits §9.3's wiring serialization); (q′) **determinism — two sources differing only in `os` tag order, `scripts[]` entry order, or inline-content line endings MUST yield byte-identical canonical form and identical `body_hash`** (§7.1, §9.3); (r) round-trip identity modulo documented-lossy cases, dead-default preserved; (s) `os_coverage` projection incl. the divergence pair — one entry tagged `[darwin,linux,windows]` → `os_divergent: false` vs three per-OS entries → `true` with identical `os` sets; (t) install coverage-gap — `blocking: true` MUST-refuse vs `blocking: false` SHOULD-warn.

Individual vector IDs are assigned in the conformance suite.

## Appendix D — Provenance and Preserved Positions (Informative)

Promoted 2026-07-11 from the ACIF design record: the hook extension block and Decisions #6, #19, #21, #23, #29, and #33 of `SHAPE.md`, with full deliberation records in `panel/hooks-requires-consensus.md` and `panel/platform-commands-consensus.md`.

The event vocabulary and handler-type enum were repatriated from a frozen snapshot of the Syllago converter (commit `cf047f52`); implementations, including Syllago and capmon, conform to this document's copy.

Preserved positions recorded for future revision: three panel variants proposed admitting one or more script-runtime keys (`json_io_protocol`; `input_modification` + `permission_control`) to `requires` for command handlers — re-heard if corpus evidence shows authors declaring them. A stricter fail-closed render rule for `blocking: true` hooks was overridden by observed provider warn-default behavior; enterprise policy engines obtain that posture via `os_divergent` + provenance refusal. A closed enum for interpreter-selection passthrough was rejected as a brittle list; if a passthrough splice vulnerability ever appears in a renderer, revisit enum validation before adding escaping.

Newly minted at spec-promotion time (not present in the design record; flagged for review): `acif.hook.event_unrecognized`, `acif.hook.handlers_missing`, `acif.hook.handler_type_unrecognized`, `acif.hook.script_file_missing`; the §9.4 preimage framing, including its broadening from the design record's `scripts[]`-only wiring to the entire canonical extension block; the §7.1/§9.3 canonical array-ordering and inline-content-normalization pins; the §13.1 `os_divergent` executable-identity predicate; and the §6.3 model unification. The preimage broadening and the model unification were ratified back into the design record (SHAPE.md Decisions #19/#33, hook extension block, Appendix C.3, TV-HOOK row) at promotion time. A spec-purist review of both exemplar documents ran before replication; all findings were applied.

Amended after the second independent review (2026-07-11): the §6.2 `async` materialization rule (the published vectors' hash literals already assumed it; the prose had only a schema comment), the §9.2 path constraints and source-root resolution rule with `acif.hook.script_path_invalid`, the Appendix B empty-alias-set note, and the TV-HOOK (i)/(j) vectors.
