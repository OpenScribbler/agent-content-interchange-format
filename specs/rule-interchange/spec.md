# ACIF Rule Interchange Specification

**Version:** 0.1.0
**Status:** Draft
**Spec ID:** [ACIF-RULE]

---

## Abstract

This document defines the canonical interchange form for the rule content type: a prose instruction document that an AI coding tool loads into model context according to an activation mode. It specifies the canonical rule model, the activation-mode vocabulary with its total provider mapping and default materialization, glob-declaration consistency rules, the rule hash boundary, derivation predicates, render-back requirements, and the rule error-identifier registry.

## 1. Introduction

A rule is a Markdown document whose prose becomes standing model instructions — coding conventions, project constraints, style guidance. Unlike a skill, a rule has no invocation surface of its own: what varies across providers is *when it loads*. Provider formats express that trigger through at least six distinct mechanisms (always-on defaults, glob triggers, frontmatter glob lists, model discretion, manual invocation, slash commands); this document defines the provider-neutral canonical activation vocabulary those mechanisms canonicalize to and render back from.

Rules are a frontmatter-bearing content type ([ACIF-CORE] §6.1): the sidecar is the primary carrier, and frontmatter on the source file is an opt-in supplementary layer. The rule body is prose that ACIF 0.1 carries opaquely (§8.4).

The activation-mode vocabulary in this document is ACIF-originated: no prior implementation structure could represent all four canonical modes, so this vocabulary was authored for ACIF rather than adopted from a provider or converter snapshot. Downstream implementations conform to this document's copy.

## 2. Relationship to ACIF Core

This document is a Level 1 (L1) companion to [ACIF-CORE] and depends on it normatively. Conformance to this document requires conformance to [ACIF-CORE]; every discipline in [ACIF-CORE] §8 and the capability model in [ACIF-CORE] §9 apply to rules without restatement. This document adds rule-specific requirements only; it redefines no [ACIF-CORE] term.

This document is compatible with [ACIF-CORE] version 0.1.x. Both documents are Draft maturity; changes to [ACIF-CORE] may require corresponding changes here.

## 3. Terminology

Terms defined in [ACIF-CORE] §2 are used without redefinition. Additionally:

**activation mode** — the canonical declaration of when a rule loads into model context: one of the closed enum in Appendix A.

**glob trigger** — the `glob` activation mode: the rule loads when files matching its `globs` patterns are in context.

**always-on rule** — a rule whose canonical activation mode is `always`: loaded unconditionally, with no invocation gate.

**provider sub-mode** — a provider-native activation declaration mechanism, as enumerated in the Appendix A.2 mapping table.

## 4. Requirements Language

The key words "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHALL NOT", "SHOULD", "SHOULD NOT", "RECOMMENDED", "NOT RECOMMENDED", "MAY", and "OPTIONAL" in this document are to be interpreted as described in BCP 14 [RFC2119] [RFC8174] when, and only when, they appear in all capitals, as shown here.

## 5. Conformance

This document extends the [ACIF-CORE] §4 conformance classes with rule-specific requirements and adds one class:

**Conforming canonicalizer** — additionally satisfies §6–§8 (model validation, mode canonicalization and materialization, hash boundary).

**Conforming validator** — additionally satisfies the reject conditions in §6 that are evaluable over canonical form, without re-applying defaults or translations. Conditions gated on the source form (`acif.rule.activation_mode_missing`, `acif.rule.activation_mode_unmappable`) bind at ingestion ([ACIF-CORE] §2) and are not re-evaluated by validators — canonical form always carries a materialized `mode`.

**Conforming rule record** — an item with `kind: rule` conforms if it satisfies [ACIF-CORE] §5 and §6 of this document.

**Conforming install tool** — additionally satisfies the [ACIF-CORE] §9.5 and §10 refusal rules as they apply to rule items.

**Conforming renderer** — software that emits a provider-native form from canonical form; satisfies §11.

Registry conformance is defined in [ACIF-REGISTRY]; §12 of this document states the rule-specific compute obligations a conforming registry inherits.

The test-vector families in Appendix B are normatively authoritative: an implementation that contradicts a published vector is non-conformant regardless of any prose reading.

## 6. Canonical Rule Model

### 6.1 Schema

The rule extension block appears below the common envelope when `kind: rule`:

```yaml
rule:
  activation:                   # always present in canonical form (§7)
    mode: glob                  # REQUIRED in canonical form — always | glob | model_decision | manual
    globs: ["src/**/*.ts"]      # REQUIRED iff mode: glob; forbidden otherwise (§6.2)

  requires: {}                  # OPTIONAL — empty/absent in 0.1 (§9)
```

### 6.2 Field requirements

**`activation`** — always present in canonical form; §7 defines materialization from sources that omit it. In a source form, when the block is present, `mode` is REQUIRED: a present block without `mode` MUST be rejected with `acif.rule.activation_mode_missing`. *(Informative: `mode` is the block's primary discriminant; defaulting a present-but-modeless block to `always` would silently mislabel declared glob intent.)*

**`activation.mode`** — in canonical form, MUST be a member of the closed enum in Appendix A.1, matched by exact byte comparison ([ACIF-CORE] §8.3): no trimming, no case folding (`" always"` and `Always` both reject). The two reject identifiers are discriminated by locus: an unrecognized **value in the `mode` field** (or its provider equivalent) rejects with `acif.rule.activation_mode_invalid`; a provider **structural activation mechanism** — a declaration shape, not a mode value — with no Appendix A.2 mapping row rejects with `acif.rule.activation_mode_unmappable` (§10).

**`activation.globs`** — REQUIRED when `mode: glob`; MUST NOT appear with any other mode. `mode: glob` with `globs` absent or an empty array MUST be rejected with `acif.rule.glob_mode_without_globs`; `globs` present with `mode` ≠ `glob` MUST be rejected with `acif.rule.globs_without_glob_mode`. Each element MUST be a non-empty string ([ACIF-CORE] §8.3). Glob pattern syntax is not pinned in ACIF 0.1: elements are carried as opaque pattern strings and are not validated against any glob dialect.

**`requires`** — OPTIONAL. The recognized `requires` vocabulary for rules is empty in ACIF 0.1 (§9); any key present is non-conformant ([ACIF-CORE] §9.4).

## 7. Activation Default Materialization

The canonicalizer MUST materialize the activation default at canonicalization ([ACIF-CORE] §8.1), in this single place: `activation` block absent in the source → materialize `activation` with `mode: always`.

Canonical form therefore always carries an explicit `activation.mode`. Validators MUST NOT re-apply the default. The §9.1 predicate is defined over the post-materialization form and is total because of this rule. Materialized values are canonical-form content, not publisher-declared metadata: per [ACIF-CORE] §7.8 they are never written into `publisher_section` and enter no hash preimage.

*(Informative)* `always` is the default because it matches every surveyed provider's no-frontmatter behavior: a bare rule file with no declaration loads unconditionally. The materialization pattern is shared with skills ([ACIF-SKILL] §7) and MCP transport types ([ACIF-MCP]).

## 8. Body and Hash Boundary

### 8.1 Body classification and `body_hash`

The rule's canonical body is the rule source file's prose, classified and hashed per [ACIF-CORE] §7: single-file bodies hash the canonical text form with the frontmatter block stripped; a rule shipping co-located content files classifies multi-file per [ACIF-CORE] §7.2 and hashes per §7.4.

### 8.2 Extension-block hash coverage

Rules are frontmatter-bearing, so per [ACIF-CORE] §7.8 the extension block MUST NOT enter the `body_hash` preimage. Declared activation values are observed faithfully into `publisher_section` and covered by `metadata_hash` ([ACIF-PUBLISHER]); values the publisher never declared exist in canonical form only as the materialized default and are covered by no hash ([ACIF-CORE] §7.8).

Consequences (normative in effect, stated for clarity): re-targeting a declared activation — `always` → `glob`, editing a `globs` pattern, `manual` → `always` — moves `metadata_hash` and does not move `body_hash`; a change confined to the rule's prose moves `body_hash` only.

### 8.3 Prose opacity

The rule body is opaque to the canonical layer. In particular, `@`-import references in rule prose (e.g., `@security.md`, `@~/company-standards.md`) are carried verbatim: ACIF 0.1 does not parse, resolve, validate, or rewrite them, and canonicalization plus render-back round-trips them byte-identically. An import target outside the rule's body directory is invisible to `body_hash`. The body-content reference grammar is a roadmap item; see also §9.2 and §14.

## 9. Capability Dispositions and Derivation Predicates

The recognized `requires` vocabulary for rules is **empty** in ACIF 0.1. Every capability key of the rule vocabulary is disposed per [ACIF-CORE] §9.2 as follows.

### 9.1 DERIVABLE keys

| Key | D_K over canonical body B (post-materialization, §7) |
|---|---|
| `activation_mode` | `B.activation.mode ∈ {glob, manual, model_decision}` — positive-set form |

The predicate produces `{derivable-true, derivable-false}`: derivable-true means the rule declares a non-default activation gate. The positive-set form is deliberate — a future enum member is derivable-false until explicitly added, where a negation form (`mode != "always"`) would silently flip it. Canonicalization rejects every malformed input (§6.2) before the predicate runs, so it only ever evaluates validated enum members. The declared mode and globs are set-valued registry projections (§12.1), not predicate outputs.

### 9.2 OUT-OF-SCOPE-AT-L1 keys *(informative rationale)*

`file_imports` is prose-body-opaque: the `@`-import evidence lives in body prose ACIF carries without parsing (§8.3), and under the out-of-band guardrail ([ACIF-CORE] §9.3) a body-carried capability is never `requires`-eligible. It is recorded as the strongest `requires` candidate any capability walk surfaced — non-derivable today, author-created, guarding a real silent-failure class (an unresolved import degrades to literal text on non-supporting providers) — and it was rejected on adoption empirics (a key authors would populate approximately never generates false-negative confidence), reversibility asymmetry, and cross-type coherence. If the roadmap reference-grammar item pins a structured import record, `file_imports` becomes DERIVABLE; it is never `requires`-eligible in either branch.

`cross_provider_recognition` is provider-side format recognition (which providers auto-read other providers' rule files) — a provider-matrix fact. `auto_memory` is a provider-runtime feature entirely outside the publish pipeline. `hierarchical_loading` (multi-level directory loading with precedence) is likewise a provider-matrix fact; all three surface through the `provider_capability_coverage` projection ([ACIF-REGISTRY]), not through any item field.

### 9.3 Orphan keys

Any `requires.<key>` on a rule item is non-conformant ([ACIF-CORE] §9.4) — including `requires.file_imports` (the considered-and-rejected candidate; its rejection is load-bearing), `requires.activation_mode` (DERIVABLE keys are never `requires` keys), and keys recognized for other content types. An unrecognized key evaluated by a consumer follows the three-valued rule ([ACIF-CORE] §9.5).

## 10. Canonicalization Mapping

Canonicalization rewrites provider sub-modes to the canonical enum per the total mapping table in Appendix A.2 before any hash is computed ([ACIF-CORE] §8.2). Two rows warrant normative emphasis:

- **Documented collapse:** `frontmatter_globs` and `glob` sub-modes both canonicalize to `mode: glob` — the declaration mechanism differs, the activation semantics are identical. Round-trip through this collapse is documented-lossy on declaration mechanism only.
- **Deterministic legacy residual:** a source form carrying only an always-apply boolean set false and no globs canonicalizes to `mode: model_decision`. `manual` is reachable only from source formats that carry the distinction explicitly and from ACIF-native authoring.

Any provider activation mechanism with no mapping row rejects with `acif.rule.activation_mode_unmappable` (the totality net).

## 11. Render-Back Requirements

These requirements bind conforming renderers; the general render-back framework is [ACIF-RENDER].

- The rule body, including any `@`-import syntax, is emitted byte-verbatim (§8.3).
- Where the target format carries an activation declaration, the renderer emits the target's native declaration for the canonical mode per Appendix A.2 read in reverse. The `frontmatter_globs`/`glob` collapse renders to whichever mechanism the target format defines; where a target carries both, mechanism choice is a per-provider decision recorded in [ACIF-RENDER].
- Where the target format has **no** declaration surface for the canonical mode, the rule degrades to the target's default loading semantics, and the renderer MUST emit `acif.rule.activation_degraded` naming the canonical mode lost and the target's effective behavior. Absence of the diagnostic on a degrading render is non-conformant. *(Informative: the dangerous direction is gate loss — a `manual` rule degrading to a provider that loads all rule files unconditionally becomes permanent context injection the author opted against; the mandatory diagnostic makes that visible at render time.)*
- Opaque passthrough fields MUST be re-serialized through the target format's structured encoder ([ACIF-CORE] §8.5).

## 12. Registry Projections

The projections in this section are computed by registries over the canonical body ([ACIF-REGISTRY] defines the response surface).

### 12.1 `activation_mode` projection

A conforming registry MUST compute, for every rule item at ingest: the §9.1 boolean, the declared canonical `mode`, and — for `mode: glob` — a **bounded** globs projection: `{present: bool, count: N, sample: [...], truncated: bool}` with the sample capped (at most 16 entries). Registries MUST NOT fan the full publisher glob array into polled response surfaces; the full list stays in the body record for fetch-on-demand.

### 12.2 `provider_capability_coverage`

Registries MUST surface, per rule-relevant capability key (`file_imports`, `hierarchical_loading`, `cross_provider_recognition`, `auto_memory`), the set of providers supporting it, from provider capability-matrix data. This is a shared matrix fact, not per-item compute; requirements on the response surface live in [ACIF-REGISTRY].

### 12.3 Moderation priority *(informative)*

The highest-priority moderation bucket for rules is `mode: always` — the empirical default — combined with cross-provider magic filenames: an always-on rule is ungated permanent context injection, and a single file named to a convention that many providers auto-recognize multiplies the blast radius. This guidance is registry discretion, not a conformance requirement; the canonical mode in §12.1 is the signal that makes such policies implementable.

## 13. Error Identifiers

| Identifier | Class | Condition |
|---|---|---|
| `acif.rule.activation_mode_missing` | reject | `activation` block present in source without `mode` (§6.2) |
| `acif.rule.activation_mode_invalid` | reject | `mode` value outside the closed enum, or inexact byte form (§6.2) |
| `acif.rule.activation_mode_unmappable` | reject | Provider activation mechanism with no Appendix A.2 mapping row (§10) |
| `acif.rule.glob_mode_without_globs` | reject | `mode: glob` with `globs` absent or empty (§6.2) |
| `acif.rule.globs_without_glob_mode` | reject | `globs` present with `mode` ≠ `glob` (§6.2) |
| `acif.rule.activation_degraded` | diagnostic (MUST-emit, render) | Canonical mode lost at render to a no-declaration-surface target (§11) |

Reject-class identifiers make canonicalization fail; the diagnostic accompanies successful rendering. All reject diagnostics for authoring errors are fix-forward ([ACIF-CORE] §8.7).

## 14. Security Considerations

**Always-on prose injection.** An always-on rule fires every turn with no invocation gate — at or above skills on the injection axis, because a skill's auto-invocation at least passes a model decision. `mode: always` is also the materialized default, so the majority of crawled rules land in the highest-risk bucket by construction. The §12.1 projection exists so registries and installers can gate on the mode.

**Magic-filename blast radius.** Several providers auto-recognize rule files by conventional filename, including other providers' conventions. A single malicious rule file under a widely-recognized name is always-on across every recognizing provider at once — typosquatting with a multiplier. Filename conventions are discovery-layer facts; the countermeasures are registry-side (provenance, moderation priority in §12.3), not canonical-form fields.

**Import targets are unverifiable in 0.1.** Rule prose can reference `@~/`-relative or URL-shaped import targets — a credential-exfiltration and remote-fetch-injection surface on providers that resolve imports. ACIF 0.1 carries the prose opaquely (§8.3): no canonical field exists to lint, and heuristic flagging is registry discretion. The structured import grammar, with target-class lints (`in-bundle`/`absolute`/`home`/`url`), is a roadmap item coupled to the reference-grammar question.

**Degradation changes semantics silently.** Rendering a gated rule to an ungated provider converts opt-in guidance into unconditional instructions; §11's mandatory diagnostic is the countermeasure. In the reverse direction, an unresolved import on a non-supporting provider degrades to literal text — the rule's meaning silently changes with no canonical-layer signal. Both are recorded honestly as 0.1 limitations.

**Metadata is self-asserted.** Everything in [ACIF-CORE] §11 applies.

## 15. References

### 15.1 Normative

- [ACIF-CORE] "ACIF Core Specification", version 0.1.x. `../core/spec.md`
- [RFC2119] Bradner, S., "Key words for use in RFCs to Indicate Requirement Levels", BCP 14, RFC 2119, March 1997. <https://www.rfc-editor.org/rfc/rfc2119>
- [RFC8174] Leiba, B., "Ambiguity of Uppercase vs Lowercase in RFC 2119 Key Words", BCP 14, RFC 8174, May 2017. <https://www.rfc-editor.org/rfc/rfc8174>

### 15.2 Informative

- [ACIF-SKILL] "ACIF Skill Interchange Specification", version 0.1.x. `../skill-interchange/spec.md` — the parallel materialization pattern and the shared reference-grammar roadmap item.
- [ACIF-PUBLISHER] "ACIF Publisher Record Specification", version 0.1.x. `../publisher-spec/spec.md`.
- [ACIF-REGISTRY] "ACIF Registry Specification", version 0.1.x. `../registry-spec/spec.md`.
- [ACIF-RENDER] "ACIF Render-Back Specification", version 0.1.x. `../render-back/spec.md`.
- [ACIF-MCP] "ACIF MCP Configuration Interchange Specification", version 0.1.x. `../mcp-interchange/spec.md`.
- [SHAPE] ACIF design record: `SHAPE.md` and `panel/rules-requires-consensus.md` in the ACIF repository — decision provenance (Decisions #23 as amended, #30).

---

## Appendix A — Canonical Activation-Mode Vocabulary (Normative)

This appendix is ACIF-owned normative text; implementations conform to this copy. It is normative for the canonical mode names, their definitions, the canonicalization mapping rows, and the residual rule; which providers carry a given sub-mode is observational snapshot data.

### A.1 Closed enum

`activation.mode ∈ {always, glob, manual, model_decision}` — closed enum, exact byte match ([ACIF-CORE] §8.3).

| Mode | Definition |
|---|---|
| `always` | Loaded unconditionally, every session and every turn |
| `glob` | Loaded when files matching the rule's `globs` patterns are in context |
| `model_decision` | The model decides from the rule's description and context whether to load it |
| `manual` | Loaded only on explicit user invocation (@-mention, slash command, or equivalent) |

### A.2 Total canonicalization mapping (provider sub-modes → canonical)

| Provider sub-mode | Canonical | Notes |
|---|---|---|
| `always_on` | `always` | — |
| `glob` | `glob` | — |
| `frontmatter_globs` | `glob` | Documented collapse: declaration mechanism differs, activation semantics identical (§10) |
| `model_decision` | `model_decision` | — |
| `manual` | `manual` | — |
| `slash_command` | `manual` | Slash invocation is explicit user invocation |
| *(legacy residual)* always-apply boolean false + no globs | `model_decision` | Deterministic residual: source formats that cannot express `manual` vs `model_decision` resolve here (§10) |
| *(absent)* no activation declaration | `always` | The §7 materialized default — matches all surveyed providers' no-frontmatter behavior |
| Any other mechanism | — | MUST reject `acif.rule.activation_mode_unmappable` (totality net) |

*(Informative)* Six provider sub-modes were observed across a ten-provider survey; at least one surveyed source format carries all four canonical values distinctly, which is what makes the four-value enum witnessable from provider sources rather than speculative.

## Appendix B — Conformance Test-Vector Families (Normative)

The vectors in these families, published in the `conformance/` directory, are normatively authoritative over prose. Family definition:

**TV-RULE-\***: (a) activation-default materialization — activation absent in source → canonical form carries `mode: always`; neither `body_hash` nor `metadata_hash` is affected by the materialization ([ACIF-CORE] §7.8); (b) mode required-when-present → `acif.rule.activation_mode_missing`; (c) invalid values — `mode: sometimes` AND `mode: " always"` (exact byte membership) → `acif.rule.activation_mode_invalid`; (d) mapping-table totality — `frontmatter_globs` source → `glob`; explicit `manual` source → `manual`; slash-command source → `manual`; legacy always-apply-false + no globs → `model_decision`; unmapped mechanism → `acif.rule.activation_mode_unmappable`; (e) glob consistency — `mode: glob` without `globs` and with `globs: []` → `acif.rule.glob_mode_without_globs`; `globs` with `mode: always` → `acif.rule.globs_without_glob_mode`; (f) `D_K` activation_mode — `always` → derivable-false; `glob`/`model_decision`/`manual` → derivable-true; activation-absent → derivable-false via materialization (positive-set form); (g) projection shape — `{derivable, mode, globs: {present, count, sample ≤16, truncated}}`; (h) empty `requires` conformant; (i) orphan-key reject, three distinct reject reasons — `requires.file_imports`, `requires.activation_mode`, `requires.handler_types`; (j) unknown-key three-valued evaluation; (k) prose-opacity round-trip — body containing `@`-import syntax canonicalizes and renders back byte-verbatim; `body_hash` stable; (l) hash boundary — re-targeting a *declared* `mode` with body bytes unchanged moves `metadata_hash` and MUST NOT move `body_hash`; editing prose moves `body_hash` and MUST NOT move `metadata_hash`; (m) render degradation — rendering `manual` to a no-declaration-surface target → MUST emit `acif.rule.activation_degraded`.

Individual vector IDs are assigned in the conformance suite.

## Appendix C — Provenance and Preserved Positions (Informative)

Promoted 2026-07-11 from the ACIF design record: the rule extension block and Decisions #23 (rules application, out-of-band guardrail) and #30 of `SHAPE.md`, with the full deliberation record in `panel/rules-requires-consensus.md` — the first 2:2 panel split of the capability-walk series, resolved by the working group to keep `rules.requires` empty.

Preserved positions recorded for future revision: spec-purist's ADMIT dissent on `file_imports` (fails the works-fine-without-it severity test; MUST be re-heard before any permanent never-parse resolution of the reference-grammar roadmap item); registry-operator's graceful-degradation class for `requires` evaluation (moot with no admitted key; reconsider if a graceful-class key ever lands); Remy's three-value-enum caution (round-trip resolving power; the Appendix A.2 residual rule is the mitigation — if round-trip divergence appears in practice, the mapping table is the file to fix); Karpathy's two-field minimal block (overridden; his out-of-band guardrail was adopted into [ACIF-CORE] §9.3).

Newly minted at spec-promotion time (not present in the design record; flagged for review): `acif.rule.activation_degraded` and the §11 degradation rule (the design record pinned canonicalization-direction totality but no render-direction diagnostic; the gate-loss hazard motivates the MUST-emit, paralleling [ACIF-HOOK] §12.1); the §6.2 pins that `globs: []` rejects as `glob_mode_without_globs` and that glob elements are non-empty opaque strings with no dialect validation; the §8.2 hash-boundary statement ([ACIF-CORE] §7.8 model); and the TV-RULE (l)/(m) vectors. These items were ratified back into the design record (SHAPE.md, Spec-Promotion Ratifications section) at promotion time.
