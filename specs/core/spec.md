# ACIF Core Specification

**Version:** 0.1.0
**Status:** Draft
**Spec ID:** [ACIF-CORE]

---

## Abstract

This document defines the core layer of the Agent Content Interchange Format (ACIF): the common envelope shared by all content types, the carrier model for canonical metadata, the identity and change-signal model, the `body_hash` content-hash algorithm, the canonicalization disciplines that every ACIF specification builds on, the capability (`requires`) model, and the canonical neutral tool vocabulary. Six per-content-type interchange specifications, a publisher-record specification, a registry specification, and a render-back specification build on this core.

## 1. Introduction

AI coding tools (referred to in this document set as *providers*) load user-authored content — hooks, skills, rules, commands, agents, and MCP server configurations — in provider-specific formats that differ in field names, file layouts, vocabularies, and defaults. ACIF defines a provider-neutral canonical form for each of these content types, so that an item authored once can be canonicalized, published, compared, verified, and rendered back to any conforming provider format deterministically.

This document defines the material shared by every ACIF content type. It contains no per-content-type requirements; those live in the six Level 1 (L1) interchange specifications.

The six content types are co-equal: every cross-cutting mechanism in this document (envelope, carriers, hashing, canonicalization disciplines, capability model) is defined once and applies to all six.

### 1.1 Document set and layering *(informative)*

| Layer | Document | Defines |
|---|---|---|
| Core | [ACIF-CORE] (this document) | Envelope, carriers, identity, `body_hash`, disciplines, capability model, tool vocabulary |
| L1 | [ACIF-HOOK], [ACIF-SKILL], [ACIF-RULE], [ACIF-COMMAND], [ACIF-AGENT], [ACIF-MCP] | Per-content-type extension blocks, vocabularies, canonicalization, derivation predicates |
| L2 | [ACIF-PUBLISHER] | The two-section published record, `publisher_section`, frontmatter CI reconciliation, pack records |
| L3 | [ACIF-REGISTRY] | `registry_section`, registry-computed projections, freshness, `source_uri` |
| L4 | [ACIF-RENDER] | Deterministic canonical→provider render-back framework |

Dependency direction: every other ACIF document depends normatively on this one. This document depends on no other ACIF document.

## 2. Terminology

**item** — a single unit of publishable content: one hook, skill, rule, command, agent, MCP configuration, or pack record.

**content type** — one of the seven values of the `kind` field (§5.1). The six *interchange* content types are `hook`, `skill`, `rule`, `command`, `agent`, and `mcp_config`; `pack` is a grouping record defined in [ACIF-PUBLISHER].

**canonical form** — the provider-neutral representation of an item after canonicalization: provider-specific names rewritten to canonical vocabularies, defaults materialized, and rejects applied.

**canonicalization** — the deterministic transformation from a source form (provider-native or ACIF-authored) to canonical form.

**canonicalizer** — software that performs canonicalization.

**validator** — software that checks an item already in canonical form against the conformance requirements of the ACIF documents, without re-applying canonicalization transformations.

**canonical body** — the content bytes of an item over which `body_hash` is computed, as classified by §7.2 and bounded by §7.3–§7.5.

**sidecar** — a generated file carrying an item's canonical metadata, separate from the item's source file(s).

**frontmatter** — a YAML metadata block at the top of a Markdown source file, delimited by `---` lines.

**publisher** — the party that authors and hosts an item's source.

**registry** — a service that discovers, canonicalizes, records, and serves items. Registry conformance requirements are defined in [ACIF-REGISTRY]; this document uses the term where core rules constrain registry behavior.

**provider** — an AI coding tool that consumes installed content (also called a *harness*).

**install tool** — software that places an item into a provider's discovery location on a user's machine.

**derivation predicate (D_K)** — a per-capability-key boolean predicate over the canonical body, defined in §9.2.

**canonical JSON serialization** — the serialization defined in §8.6.

**fix-forward diagnostic** — a diagnostic whose text names the remedy that makes the input conformant, not only the defect.

**ingestion** — the point at which a canonicalizer first reads an item's source and referenced bytes. Reject conditions gated "at ingestion" bind the conforming canonicalizer; a validator consuming already-canonical form does not re-evaluate them.

## 3. Requirements Language

The key words "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHALL NOT", "SHOULD", "SHOULD NOT", "RECOMMENDED", "NOT RECOMMENDED", "MAY", and "OPTIONAL" in this document are to be interpreted as described in BCP 14 [RFC2119] [RFC8174] when, and only when, they appear in all capitals, as shown here.

## 4. Conformance

This document defines four conformance classes. The L1–L4 documents define additional classes and extend these.

**Conforming canonicalizer.** Satisfies all MUST and MUST NOT requirements in §5–§8 that are addressed to canonicalization, including the disciplines in §8. Produces byte-identical canonical form for identical input.

**Conforming validator.** Satisfies all MUST and MUST NOT requirements addressed to validation, including §8.1 (validators MUST NOT re-apply defaults) and §9.4–§9.6 (capability evaluation).

**Conforming item record.** An item in canonical form conforms if it satisfies all MUST and MUST NOT requirements in §5 (envelope) and the applicable L1 specification.

**Conforming install tool.** Satisfies all MUST requirements in this document and the applicable L1/L2/L3 documents that are addressed to install tools (e.g., §9.5 unknown-key refusal).

Error identifiers in this document set use the namespace `acif.*`. Each named error identifier is normative: a conforming implementation that detects the named condition MUST report it under that identifier.

## 5. Common Envelope

Every item carries the common envelope, regardless of `kind`.

### 5.1 Fields

```yaml
kind: hook | skill | rule | command | agent | mcp_config | pack   # REQUIRED
id: "f47ac10b-58cc-4372-a567-0e02b2c3d479"                        # REQUIRED
display_name: "Session Start: Inject Prompt"                      # REQUIRED
version: "5.1.0"                                                  # OPTIONAL
description: "Injects system context at session start."           # OPTIONAL
license:                                                          # OPTIONAL
  spdx: MIT
  file: LICENSE
  url: "https://example.com/license.txt"
pack_id: "a1b2c3d4-..."                                           # OPTIONAL
```

**`kind`** — REQUIRED. MUST be one of the seven values above, matched by exact byte comparison.

**`id`** — REQUIRED. MUST be a UUID version 4 [RFC9562], generated once when the item is first registered or authored. The `id` is the item's stable identity: it MUST NOT change across renames, moves, content edits, or pack reorganizations. (Exception: pack records with `source_kind: inferred` use a UUID version 5 identity; see [ACIF-PUBLISHER].)

**`display_name`** — REQUIRED. A human-readable name for display only. Implementations MUST NOT use `display_name` for identity, cross-reference resolution, or deduplication.

**`version`** — OPTIONAL, literal-or-absent. When declared, the value MUST be valid Semantic Versioning 2.0.0 [SEMVER]. No implementation may synthesize, inherit, or derive a value when the publisher omits it. `version` is advisory; the canonical change signal is `body_hash` (§6.2).

**`description`** — OPTIONAL. Free text.

**`license`** — OPTIONAL. When present, `spdx` is REQUIRED and MUST be an SPDX license identifier; `file` (repository-relative path) and `url` (absolute URL) are each OPTIONAL.

**`pack_id`** — OPTIONAL. A UUID version 4 declaring pack membership. Pack semantics are defined in [ACIF-PUBLISHER].

### 5.2 Forbidden fields

The following field names MUST NOT appear on an item record, in any section: `effective_version`, `derived_version`, `pack_inherited_version`, `resolved_version`. Their presence is a conformance error. (These names are reserved to prevent version-inheritance semantics from re-entering the format; a pack's own `version` lives on the pack record only.)

## 6. Carriers, Identity, and Change Signal

### 6.1 Carrier model

The sidecar is the universal primary carrier: every item in canonical form has a sidecar, without exception. Frontmatter is a supplementary carrier available only to content types whose source is a publisher-authored Markdown file.

| Content type | Primary carrier | Frontmatter |
|---|---|---|
| `hook`, `mcp_config` | Sidecar | Not possible — the provider owns the native config file; no inline surface exists |
| `skill`, `rule`, `agent`, `command` | Sidecar | Opt-in supplementary layer |

Content types whose only carrier is the sidecar are referred to as **sidecar-only** content types throughout this document set.

Requirements:

- In a sidecar, `kind` is REQUIRED (the file has no implicit type). In frontmatter, `kind` is OPTIONAL and MAY be inferred from the canonical filename (e.g., `SKILL.md` → `kind: skill`).
- Data flows sidecar → frontmatter, never the reverse. Tooling that projects canonical values into source files MUST read from the canonical sidecar. Reconciliation rules for conflicts are defined in [ACIF-PUBLISHER].
- Registries MUST NOT write to source files. All registry-generated metadata lives in sidecars.

*(Informative)* The frontmatter layer is intentionally redundant with the sidecar: a copied source file carries its own metadata. That redundancy is safe only because the flow direction is one-way.

### 6.2 Identity and change signal

- `id` (§5.1) is the item's identity.
- `body_hash` (§7) is the canonical per-item **change signal**. It is dispositive: consumers determining whether content changed MUST use `body_hash`, not `version`.
- `version` is advisory ordering and display metadata.

Consumer-surface requirements on `body_hash` (tuple endpoints, response exposure) are defined in [ACIF-REGISTRY].

## 7. The `body_hash` Algorithm

### 7.1 Algorithm identity *(informative)*

The algorithm in this section is the MOAT v0.4.0 content-hash algorithm, adopted verbatim. It is restated here in full as ACIF-owned normative text; MOAT is credited as informative provenance only, and no conformance requirement in this document set depends on any MOAT document.

### 7.2 Single-file / multi-file classification

An item's canonical body is classified before hashing.

For content types with a frontmatter surface: the body is **multi-file** if and only if, after excluding files matching `LICENSE*` or `README*` at the body root, version-control metadata directories (§7.4), and registry-generated sidecar files at the body root (§7.5), the body directory contains at least one content file beyond the canonical entry file (e.g., `SKILL.md`). Otherwise the body is **single-file**.

This predicate is content-type-general: co-located resources of any kind — a skill's bundled scripts, templates, or data files — make the body multi-file. Without a pinned predicate, two conforming implementations could disagree on the hash input boundary and produce divergent `body_hash` values for identical content.

For sidecar-only content types, the body boundary is defined by the applicable L1 specification (see §7.7).

### 7.3 Per-file hashing

Each file in the body is classified **text** or **binary**:

- A file is text if and only if its final extension (lowercased) is in the closed `TEXT_EXTENSIONS` set below AND its first 8192 bytes contain no NUL (0x00) byte. All other files, including extensionless files and dotfiles with no second dot (e.g., `.gitignore`), are binary.
- The final extension of a name with exactly one leading dot and no other dot is the empty string (dotfiles are extensionless). Otherwise it is the substring from the last dot, lowercased (`.tar.gz` → `.gz`).

`TEXT_EXTENSIONS` (closed set, normative):

```
.md .txt .rst
.yaml .yml .json .toml .ini .cfg .conf
.html .htm .xml .svg .css .scss .less
.js .ts .jsx .tsx .mjs .cjs
.py .rb .lua .rs .go
.sh .bash .zsh .fish
.csv .tsv .sql
.lock .sum .mod
```

**Text files** are hashed as SHA-256 over the canonical text form: a leading UTF-8 byte-order mark (`EF BB BF`) is stripped, then line endings are normalized in a single left-to-right pass — `CR LF` → `LF`, lone `CR` → `LF`, `LF` unchanged.

**Binary files** are hashed as SHA-256 over their raw bytes.

*(Informative)* The text/binary classification exists solely to make hashing stable; it is not a security classification. Some plain-text script extensions (e.g., `.ps1`, `.cmd`, `.bat`) are outside `TEXT_EXTENSIONS` and hash as raw bytes, so a line-ending-only edit moves their hash where it would not move a `.sh` file's. Moderation logic distinguishing source scripts from opaque compiled artifacts must not key on this flag. The set is closed at this value because the algorithm is adopted verbatim from its provenance (§7.1) together with its published test vectors; revising the set is a hash-breaking change reserved for a future algorithm version.

**Single-file bodies** with a frontmatter surface are hashed as SHA-256 over the canonical text form of the content with the frontmatter block stripped. The frontmatter block is delimited in the canonical text form by a leading line consisting of `---` and the next subsequent line consisting of `---`, where the closing line is terminated by LF or by end of input; the block, both delimiter lines included, is removed. A change confined to frontmatter does not move `body_hash`; it moves `metadata_hash` ([ACIF-PUBLISHER]).

### 7.4 Directory combine (multi-file bodies)

1. Enumerate all regular files under the body root, excluding any path containing a version-control metadata directory component: `.git`, `.svn`, `.hg`, `.bzr`, `_darcs`, `.fossil`.
2. Symbolic links anywhere in the body MUST be rejected at ingestion.
3. For each file, compute the relative path from the body root in POSIX form (`/` separators), normalized to Unicode NFC.
4. Compute each file's per-file hash per §7.3.
5. Sort entries by the raw UTF-8 byte order of their relative paths.
6. Build the manifest: one line per entry, `<lowercase-hex-hash><SP><SP><relative-path><LF>`.
7. The directory hash is `sha256:` followed by the lowercase hex SHA-256 of the manifest bytes.

A body containing no files after exclusions is unpublishable for frontmatter-bearing content types.

The `body_hash.value` field carries the lowercase hex digest; the `body_hash.algorithm` field carries `sha256`.

### 7.5 Sidecar exclusion (root-only)

Any registry-generated sidecar file stored inside the content directory is excluded from `body_hash` at the body root only. A file of the same name in a subdirectory has no protocol meaning and MUST be included in the hash. *(Informative: root-only exclusion breaks the circular dependency — the sidecar contains `body_hash` — while preventing content from hiding under the excluded name at depth.)*

### 7.6 Hash-then-canonicalize ordering

`body_hash` is computed over the **post-canonicalization** form: after vocabulary translation (§8.2), default materialization (§8.1), and any L1-defined body rewrites. This ordering is normative for every content type.

### 7.7 Sidecar-only preimage extension

For sidecar-only content types, the executable wiring carried in the sidecar (e.g., a hook's script routing) is part of the item's semantics but is not file bytes. For these types, the `body_hash` preimage is the §7.4 construction over the item's referenced files **plus a canonical serialization of the canonical wiring**, in a combination pinned exactly by the applicable L1 specification. Re-targeting any wiring value (an OS tag, an interpreter flag, an event name) MUST move `body_hash`. See [ACIF-HOOK] §9 for the hook instantiation.

### 7.8 Hash coverage of canonical metadata (single-coverage)

The hash home of an item's canonical extension block follows its carrier:

- For **sidecar-only** content types, the extension block is executable wiring and enters the `body_hash` preimage (§7.7). It MUST NOT be duplicated into `publisher_section`: when a publisher-authored sidecar for a sidecar-only item yields a `publisher_section` ([ACIF-PUBLISHER]), that section carries envelope-level fields only.
- For **frontmatter-bearing** content types, the declared extension-block values are publisher-declared metadata: they are observed faithfully into `publisher_section` and covered by `metadata_hash` ([ACIF-PUBLISHER]), and they MUST NOT enter the `body_hash` preimage.

Default values materialized at canonicalization (§8.1) are deterministic functions of declared absence. They are part of canonical form — derivation predicates (§9.2) and registry projections read them — but they are not publisher-declared: they MUST NOT be written into `publisher_section`, and for frontmatter-bearing types they enter no hash preimage. *(Informative: this is not a coverage hole — a materialized value cannot be re-targeted without declaring it, and declaring it moves `metadata_hash`.)*

Consequently `body_hash` and `metadata_hash` jointly cover an item's entire publisher-declared surface, each byte under exactly one hash; `body_hash` remains the dispositive content change signal (§6.2). Pack records carry no canonical body; their hashing is defined in [ACIF-PUBLISHER] and is outside this section's scope.

## 8. Canonicalization Disciplines

The disciplines in this section are normative for every canonicalizer and every L1–L4 document.

### 8.1 Materialize-then-hash

When a canonical field has a default, the canonicalizer MUST materialize the explicit value before `body_hash` is computed, in the single place the applicable specification defines. Validators MUST NOT re-apply defaults: a validator consumes the post-default canonical form. Where the default cannot be determined unambiguously, canonicalization MUST reject with the named error identifier the applicable specification defines, never guess.

### 8.2 Canonicalize-then-hash (vocabulary translation)

Provider-specific names (tool names, event names, handler types, activation modes, placeholder tokens) are rewritten to the pinned canonical vocabulary at canonicalization; `body_hash` is computed over the post-translation form.

### 8.3 Closed-enum byte discipline

Membership in a closed canonical enum is decided by exact byte comparison: no whitespace trimming, no case folding, no alias acceptance in canonical form. Provider aliases are rewritten before validation and MUST NOT survive into canonical form. Predicates over string fields treat whitespace-only strings as non-empty: the emptiness test is strictly `len(s) > 0`.

### 8.4 Reverse-translation determinism

Where multiple canonical names map to one provider-native name, reverse translation MUST apply the tiebreaker pinned in the owning vocabulary table. Where no per-pair tiebreaker is pinned, the lexicographically smaller canonical name wins. An implementation-order-dependent reverse translation is non-conformant.

### 8.5 Unmapped passthrough and the structured-encoder rule

- Rendering a canonical name to a provider with no mapping row emits the canonical name verbatim — no invention, no error. Degradation warnings apply where the owning specification defines them.
- Opaque passthrough values (provider-owned fields carried verbatim through canonical form) MUST be re-serialized through the target format's structured encoder at render-back. String-splicing a passthrough value into output is non-conformant.

### 8.6 Canonical JSON serialization

Where this document set requires a canonical JSON serialization of a value, the serialization is the JSON Canonicalization Scheme [RFC8785] applied to the value: UTF-8, object members sorted, no insignificant whitespace. Fields absent from the canonical form are omitted, not null-filled — absence is semantically distinct from every present value.

RFC 8785 preserves array element order. Where a specification's canonical value contains an array whose element order is not semantically significant, that specification MUST define the canonical element ordering before serialization, and MUST state explicitly where array order is significant and preserved. An unpinned array order in a hash preimage is a cross-implementation determinism defect.

### 8.7 Diagnostics

- Every named error identifier in this document set is stable and MUST be reported verbatim (`acif.<area>.<condition>`).
- Rejection diagnostics for authoring errors MUST be fix-forward: the diagnostic names the remedy, not only the defect.
- Diagnostics classified INFORMATIVE by the owning specification never gate conformance, canonicalization, or install.

## 9. Capability Model (`requires`)

### 9.1 The `requires` slot

Every interchange content type's extension block carries an OPTIONAL `requires` map declaring author-declared capabilities the consuming environment must satisfy. Each content type defines its own recognized `requires` vocabulary in its L1 specification.

In ACIF 0.1, the recognized `requires` vocabulary of **every** content type is empty: a conforming item's `requires` is empty or absent. The slot is reserved, not vestigial — it exists for genuinely out-of-band environmental requirements (§9.3) that no canonical field can carry.

In canonical form, an empty `requires` map is omitted: empty and absent are one canonical state, and canonicalization normalizes `requires: {}` to absence. *(Informative: without this rule the two spellings would be distinct canonical bytes and, for sidecar-only types, distinct `body_hash` values for semantically identical items.)*

### 9.2 Three-way disposition and derivation predicates

Every candidate capability key K in a content type's vocabulary is disposed to exactly one of:

- **DERIVABLE** — the L1 specification defines an explicit derivation predicate `D_K` over the canonical body. `D_K` MUST produce a value in `{derivable-true, derivable-false}` (boolean discipline). Set-valued projections (e.g., the set of distinct handler types observed) are not `D_K` outputs; they are registry-computed projections defined in [ACIF-REGISTRY]. K is excluded from `requires` because the predicate provides the signal. A `D_K` MAY be structurally constant on conforming records — a disposition rather than a signal — where the owning L1 specification says so explicitly; the exclusion from `requires` is then justified by the structural guarantee.
- **OUT-OF-SCOPE-AT-L1** — K names a concern not author-declared at the canonical layer: provider UX, install-location, meta-property, or body opacity (the capability's evidence lives in opaque body bytes — script bodies or prose — that the canonical wiring carries without parsing). Recorded in informative rationale; not validator-testable.
- **`requires`-ELIGIBLE** — no `D_K` exists AND the capability is author-declared AND the out-of-band test (§9.3) passes. K is admitted to the content type's recognized vocabulary.

A `D_K` MUST be a *derivation* — correct by construction over canonical structured content (a field, an array, an enum value validated at canonicalization before the predicate runs) — never a *heuristic* (a usually-right scan). Substring or pattern scans over unstructured body prose are heuristics regardless of whether the scanned token is canonicalization-pinned. Heuristic signals MAY ship only as advisory projections ([ACIF-REGISTRY]): method-version-stamped, both error directions documented, never gating. If a `D_K` compounds, every conjunct MUST cite a single canonical field with explicit edge-case definitions for absent, empty, null, and whitespace-only values.

### 9.3 Out-of-band eligibility guardrail

A capability is `requires`-eligible only when the item depends on something it does not contain — an environmental assumption external to the body (a runtime version, a host service capability). Any capability whose evidence lives in the body — structured field, prose, or script bytes — is resolved by the body: DERIVABLE if a canonical field carries it, OUT-OF-SCOPE-AT-L1 under body opacity if only opaque bytes carry it. A body-carried capability is never `requires`-eligible, regardless of whether a canonical field for it is missing.

Equivalently, every capability routes to one of three destinations: a **body-carried** fact is resolved by the body; a **provider-matrix** fact (which providers support a feature) is a registry projection, never an item field; only a **user-environment** fact — author-declared, neither body-derivable nor matrix-knowable — is `requires`-eligible.

### 9.4 Orphan-key reject

An item carrying a `requires.<key>` not defined for its content type is non-conformant. This applies uniformly: keys recognized for a different content type, keys disposed DERIVABLE or OUT-OF-SCOPE-AT-L1 for this content type, and keys matching a passthrough or latent field of the content type are all rejected. The presence of a matching latent field MUST NOT soften the reject.

### 9.5 Three-valued unknown-key evaluation

When a consumer evaluates a `requires` key it does not recognize, the evaluation result is `unknown` — distinct from `satisfied` and `unsatisfied`. Two-valued semantics (silently treating unknown as satisfied, or as unsatisfied) are non-conformant. Install tools MUST refuse items with any capability in `unknown` status unless the operator has explicitly opted into ignore-unknown semantics.

### 9.6 Empty-as-steady-state *(informative)*

Empty `requires` on all six content types is the validated steady state of ACIF 0.1, not a gap: the canonical wiring exposes capability evidence directly, and the derivation predicates carry the signal. The predicted first genuine tenant of the slot is runtime hints (e.g., a Python version floor for a hook script) — an out-of-band environmental pin on the ACIF roadmap.

## 10. Cross-Content-Type References

A canonical body MAY reference another item (e.g., a hook naming the skill it activates, an agent naming MCP configurations). Requirements:

- A reference is authored in one of two forms. A **UUID-authored** reference carries the target item's `id`; a name field alongside it is human-readable advisory only, and implementations MUST NOT resolve through the advisory name. A **name-declared** reference carries only a name, where that is all the source format provides (e.g., an agent's MCP-server and skill names); it enters the `declared` state and is resolved to a target `id` by registry compute ([ACIF-REGISTRY]). Load-bearing *consumption* — linkage, install refusal — always uses the authored or resolved `id`; a consumer MUST NOT treat a raw name match as resolution.
- Each reference site resolves to one of four states: `declared | resolved | unresolved | revoked`. Resolution is registry compute ([ACIF-REGISTRY]); the state vocabulary is pinned here so all documents share it.
- Install tools MUST refuse items carrying any `unresolved` or `revoked` reference unless the operator has explicitly opted in.

## 11. Security Considerations

**Self-asserted metadata.** Every envelope and frontmatter field is self-asserted by the publisher. `display_name`, `description`, `license`, and `version` carry no integrity guarantee; nothing in this format verifies them, and a consumer that treats them as verified has no basis for doing so. The enforceable protections are the testable rules elsewhere in this document set: the three-valued capability evaluation (§9.5), the cross-reference refusal rule (§10), and the registry-layer integrity surfaces ([ACIF-REGISTRY]).

**Hash scope.** `body_hash` proves that bytes are unchanged; it does not prove the bytes were inspected or are safe. All branches, scripts, and prose of an item are bound into one hash — the hash is complete in coverage, not in inspection. An external attestation slot exists at the registry layer ([ACIF-REGISTRY]); what fills it is out of scope for ACIF.

**Executable and prompt-bearing content.** Items carry executable scripts (hooks) and prose that becomes model instructions at runtime (skills, rules, agents, commands). Prompt-injection content in prose fields is load-bearing; `description` is a moderation surface. The size and provenance signals defined in [ACIF-REGISTRY] exist so that registries and install tools can surface this risk before content reaches execution.

**Identity manipulation.** `id` is publisher-generated and self-asserted; two publishers can claim the same UUID. Cross-registry identity comparison uses `body_hash`, not `id` (see [ACIF-REGISTRY]).

**Unknown-capability laundering.** The three-valued evaluation in §9.5 exists to prevent silent fail-open: an installer that treats unrecognized requirements as satisfied converts a publisher's declared constraint into an undetected gap.

## 12. References

### 12.1 Normative

- [RFC2119] Bradner, S., "Key words for use in RFCs to Indicate Requirement Levels", BCP 14, RFC 2119, March 1997. <https://www.rfc-editor.org/rfc/rfc2119>
- [RFC8174] Leiba, B., "Ambiguity of Uppercase vs Lowercase in RFC 2119 Key Words", BCP 14, RFC 8174, May 2017. <https://www.rfc-editor.org/rfc/rfc8174>
- [RFC8785] Rundgren, A., Jordan, B., Erdtman, S., "JSON Canonicalization Scheme (JCS)", RFC 8785, June 2020. <https://www.rfc-editor.org/rfc/rfc8785>
- [RFC9562] Davis, K., Peabody, B., Leach, P., "Universally Unique IDentifiers (UUIDs)", RFC 9562, May 2024. <https://www.rfc-editor.org/rfc/rfc9562>
- [SEMVER] Preston-Werner, T., "Semantic Versioning 2.0.0". <https://semver.org/spec/v2.0.0.html>
- [SPDX] The Linux Foundation, "SPDX License List". <https://spdx.org/licenses/>

### 12.2 Informative

- [MOAT] MOAT v0.4.0 content-hash algorithm — the provenance of §7. The restatement in §7 is normative on its own; MOAT documents are not required to implement ACIF.
- [SHAPE] ACIF design record: `SHAPE.md` and `panel/*.md` in the ACIF repository — the decision history (Decisions #1–#34) from which this document was promoted.

---

## Appendix A — Canonical Tool Vocabulary (Normative)

This appendix is ACIF-owned normative text: the canonical copy to which implementations conform. Divergence between a downstream implementation and this appendix is a bug in the implementation, not in ACIF. Provider-coverage facts implied by the mapping tables (which providers carry a name for a canonical entry) are observational snapshot data; this appendix is normative only for the canonical names, the mappings' render-back targets, and the tiebreakers.

Canonical tool names are snake_case and provider-neutral. Canonicalization rewrites provider-native tool names to canonical names before `body_hash` is computed (§8.2); renderers MAY translate to provider-native names at render-back.

### A.1 Canonical names and provider mappings

| Canonical | Provider mappings (`provider → native name`) |
|---|---|
| `file_read` | claude-code `Read` · gemini-cli `read_file` · copilot-cli `view` · kiro `read` · opencode `read` · vs-code-copilot `Read` · zed `read_file` · roo-code `read_file` · cursor `read_file` · windsurf `view_line_range` · codex `read_file` · factory-droid `Read` · pi `read` |
| `file_write` | claude-code `Write` · gemini-cli `write_file` · copilot-cli `create` · kiro `fs_write` · opencode `write` · vs-code-copilot `Write` · zed `edit_file` · roo-code `write_to_file` · cursor `edit_file` · windsurf `write_to_file` · codex `apply_patch` · factory-droid `Create` · pi `write` |
| `file_edit` | claude-code `Edit` · gemini-cli `replace` · copilot-cli `edit` · kiro `fs_write` · opencode `edit` · vs-code-copilot `Edit` · zed `edit_file` · roo-code `replace_in_file` · cursor `edit_file` · windsurf `edit_file` · codex `apply_patch` · factory-droid `Edit` · pi `edit` |
| `shell` | claude-code `Bash` · gemini-cli `run_shell_command` · copilot-cli `bash` · kiro `shell` · opencode `bash` · vs-code-copilot `Bash` · zed `terminal` · roo-code `execute_command` · cursor `run_terminal_cmd` · windsurf `run_command` · codex `shell` · factory-droid `Execute` · pi `bash` |
| `find` | claude-code `Glob` · gemini-cli `glob` · copilot-cli `glob` · kiro `glob` · opencode `glob` · vs-code-copilot `Glob` · zed `find_path` · roo-code `list_files` · cursor `file_search` · windsurf `find_by_name` · codex `list_dir` · factory-droid `Glob` · pi `find` |
| `search` | claude-code `Grep` · gemini-cli `grep_search` · copilot-cli `grep` · kiro `grep` · opencode `grep` · vs-code-copilot `Grep` · zed `grep` · roo-code `search_files` · cursor `grep_search` · windsurf `grep_search` · codex `grep_files` · factory-droid `Grep` · pi `grep` |
| `web_search` | claude-code `WebSearch` · gemini-cli `google_web_search` · opencode `websearch` · vs-code-copilot `WebSearch` · zed `web_search` · cursor `web_search` · windsurf `search_web` · codex `web_search` · kiro `web_search` · factory-droid `WebSearch` |
| `agent` | claude-code `Agent` · copilot-cli `task` · opencode `task` · vs-code-copilot `Agent` · zed `spawn_agent` · codex `spawn_agent` · kiro `use_subagent` · factory-droid `Task` |
| `web_fetch` | claude-code `WebFetch` · gemini-cli `web_fetch` · copilot-cli `web_fetch` · kiro `web_fetch` · opencode `webfetch` · vs-code-copilot `WebFetch` · zed `fetch` · windsurf `read_url_content` · factory-droid `FetchUrl` |
| `list` | pi `ls` |
| `notebook_edit` | claude-code `NotebookEdit` · vs-code-copilot `NotebookEdit` |
| `multi_edit` | claude-code `MultiEdit` · vs-code-copilot `MultiEdit` |
| `list_dir` | claude-code `LS` · vs-code-copilot `LS` |
| `notebook_read` | claude-code `NotebookRead` · vs-code-copilot `NotebookRead` |
| `kill_shell` | claude-code `KillBash` · vs-code-copilot `KillBash` |
| `skill` | claude-code `Skill` · vs-code-copilot `Skill` |
| `ask_user` | claude-code `AskUserQuestion` · vs-code-copilot `AskUserQuestion` |

### A.2 Reverse-translation tiebreakers

- **write/edit collapse:** zed and cursor use `edit_file`, codex uses `apply_patch`, and kiro uses `fs_write` for BOTH `file_write` and `file_edit`. Reverse translation MUST prefer `file_edit` (the more specific operation). Round-trips through these providers are documented-lossy on the write/edit distinction.
- **Legacy alias:** claude-code's legacy `Task` (renamed `Agent` in claude-code v2.1.63) reverse-translates to canonical `agent`, matched case-insensitively.
- For any other multi-match, §8.4's default applies: the lexicographically smaller canonical name wins.

### A.3 Matcher translation

Hook matcher strings are translated component-wise on `|`-split alternations. Bare wildcards (`.*`, `*`) pass through untranslated. A component with a `.*` suffix is translated by stripping the suffix, translating the base, and reattaching the suffix. Components containing `__`, `/`, or `:` (MCP-style and namespaced names) pass through untranslated.

### A.4 MCP tool-name formats

Per-provider MCP tool-name formats, for matcher passthrough and render-back: claude-code / kiro / factory-droid `mcp__server__tool` · gemini-cli `mcp_server_tool` · opencode / cline / roo-code / cursor / windsurf `server__tool` · copilot-cli / codex `server/tool` · zed `mcp:server:tool`. A name not parseable under the source provider's pattern is not an MCP tool name and passes through verbatim.

---

## Appendix B — Provenance (Informative)

This document was promoted from the ACIF design record (`SHAPE.md`, Decisions #1–#34, and the panel consensus documents under `panel/`) on 2026-07-11. The tool vocabulary in Appendix A was repatriated from a frozen snapshot of the Syllago converter (`toolmap.go` at commit `cf047f52`) on 2026-07-11; from that date the authority direction is inverted — downstream implementations, including Syllago and capmon, conform to this document's copy.
