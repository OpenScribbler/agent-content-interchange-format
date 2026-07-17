# ACIF Render-Back Specification

**Version:** 0.1.0
**Status:** Draft
**Spec ID:** [ACIF-RENDER]

---

## Abstract

This document defines the Level 4 layer of the Agent Content Interchange Format: the framework for rendering canonical form back to provider-native formats. It specifies the deterministic render function and its context, the four fidelity classes and the diagnostics discipline that governs degradation, the general translation rules renderers inherit, round-trip properties, and the division of labor between this framework and the per-content-type render sections in the L1 specifications.

## 1. Introduction

Render-back is the inverse direction of canonicalization: emitting a provider-native artifact — a hooks configuration, a `SKILL.md` with provider frontmatter, an MCP configuration file — from an item's canonical form. Canonicalization is many-to-one (provider dialects converge on canonical bytes); render-back is one-to-many (one canonical form, one output per target). What makes the direction safe is determinism plus disclosed fidelity: a renderer never guesses, never silently drops, and refuses only where every possible output is wrong.

This document defines the framework. The per-content-type rules — which fields translate, which degrade, which diagnostics fire — live in each L1 specification's render-back section and are not restated here.

## 2. Relationship to ACIF Core and the Lower Layers

This document is the Level 4 (L4) companion to [ACIF-CORE] and depends normatively on [ACIF-CORE] and the six L1 interchange specifications. It redefines no term from those documents. [ACIF-PUBLISHER] and [ACIF-REGISTRY] are upstream producers of the canonical form renderers consume; this document places no requirement on them.

This document is compatible with [ACIF-CORE] version 0.1.x. All documents are Draft maturity.

## 3. Terminology

Terms defined in [ACIF-CORE] §2 are used without redefinition. Additionally:

**renderer** — software that emits a provider-native form from canonical form.

**render context** — the input tuple a renderer is invoked with, beyond the canonical form itself (§6.1).

**fidelity class** — the classification of one canonical value's fate at render: `lossless`, `documented-lossy`, `degraded`, or `refused` (§7).

**degradation** — emitting output that carries less of the canonical form's semantics than the source expressed, accompanied by a mandatory diagnostic.

**round-trip** — rendering canonical form to a provider format and canonicalizing the result back.

## 4. Requirements Language

The key words "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHALL NOT", "SHOULD", "SHOULD NOT", "RECOMMENDED", "NOT RECOMMENDED", "MAY", and "OPTIONAL" in this document are to be interpreted as described in BCP 14 [RFC2119] [RFC8174] when, and only when, they appear in all capitals, as shown here.

## 5. Conformance

**Conforming renderer** — satisfies every MUST and MUST NOT in this document and in the render-back section of the L1 specification for each content type it renders: [ACIF-HOOK] §12, [ACIF-SKILL] §12, [ACIF-RULE] §11, [ACIF-COMMAND] §11, [ACIF-AGENT] §11, [ACIF-MCP] §10. A renderer MAY support any subset of content types and targets; conformance is claimed per (content type, target) pair.

The test-vector family in Appendix A, and the render vectors of the per-type families, are normatively authoritative over prose.

## 6. The Render Function

### 6.1 Render context

A render invocation takes the canonical form plus a render context:

- **target provider** — REQUIRED. Selects the vocabulary mapping columns and the target format.
- **target OS** — OPTIONAL. Consumed only where an L1 defines OS-dependent rendering ([ACIF-HOOK] §12.2); absence is a defined state, not an error.

ACIF 0.1 pins no further context inputs. A renderer accepting implementation-specific options MUST NOT let them change the rendered bytes of a conforming (content type, target) render — options that alter output are a fork of the render function, not a parameter of it.

### 6.2 Determinism

Rendering is a function: identical canonical form plus identical render context MUST produce byte-identical output, across invocations and across conforming implementations. Iteration-order-dependent output (map ordering, nondeterministic field sequence) is non-conformant. Where the target format does not itself pin an order, the member order MUST come from a source shared by all implementations — the order pinned by the owning L1 render section, or, where none is pinned, the [ACIF-CORE] §8.6 member sorting; a renderer-local "fixed and documented" order cannot satisfy cross-implementation identity and is non-conformant.

### 6.3 No invention

A renderer MUST NOT emit values absent from the canonical form and its owning vocabulary tables: no synthesized defaults beyond those the target format's own documented semantics re-derive ([ACIF-MCP] §10 strip-and-restore), no guessed mappings for names without a table row ([ACIF-CORE] §8.5), no inferred OS tags, no invented placeholder escapes.

## 7. Fidelity Classes and the Degradation Discipline

Every canonical value's fate at a given target falls in exactly one class, determined by the owning L1 specification:

| Class | Meaning | Renderer obligation |
|---|---|---|
| **lossless** | The target carries the value's full semantics | Emit per the mapping table |
| **documented-lossy** | The target collapses a distinction the canonical form carries (write/edit tool collapse, glob declaration mechanism, named-argument placeholders) | Emit the collapsed form; the collapse point MUST be named in the owning L1's tables; no per-render diagnostic is required |
| **degraded** | The target cannot carry the value; output loses semantics the author expressed (dropped OS overrides, lost activation gates, untranslated placeholders) | Emit the degraded form AND emit the named diagnostic the owning L1 pins (`acif.hook.platform_override_dropped`, `acif.rule.activation_degraded`, `acif.command.placeholder_untranslated`). Degradation without its diagnostic is non-conformant |
| **refused** | No defined-safe output exists — every choice is wrong for some deployment | Refuse with the named identifier the owning L1 pins (`acif.hook.no_default_for_degraded_render`) |

Two rules govern the classes:

- **Silence is the violation.** The difference between documented-lossy and degraded is where the disclosure lives — in the spec's tables versus in a per-render diagnostic — and every path has exactly one disclosure home. A renderer MUST NOT reclassify a degraded path as lossy by simply not emitting the diagnostic.
- **Refusal is the exception lane.** An L1 admits a refuse outcome only where emitting anything would be wrong for some deployment; renderers MUST NOT extend refusal to paths their L1 classifies as degraded ([ACIF-HOOK] §12.2 is the sole refuse outcome in 0.1).

## 8. General Translation Rules

These rules restate the [ACIF-CORE] §8 disciplines in the render direction; they bind every renderer without per-type restatement:

- **Vocabulary translation.** Canonical names (tools, events, handler types, modes, placeholders) translate to provider-native names per the owning vocabulary tables; a canonical name with no mapping row for the target emits verbatim ([ACIF-CORE] §8.5).
- **Reverse-translation determinism.** Where multiple canonical names collapse to one provider-native name, the round-trip's canonicalize direction applies the pinned tiebreaker ([ACIF-CORE] §8.4); renderers rely on those tiebreakers rather than avoiding the collapse.
- **Structured-encoder rule.** Every opaque passthrough value MUST be re-serialized through the target format's structured encoder; string-splicing any value into output is non-conformant ([ACIF-CORE] §8.5).
- **Dead-value preservation.** Canonical values unreachable in the current form (a default script entry fully shadowed by constrained entries) MUST NOT be stripped at render; removing them breaks round-trip to source formats where they are required ([ACIF-HOOK] §12.3).
- **Bodies are verbatim.** Prose bodies emit byte-identically, except where an owning L1 defines a body rewrite (the command placeholder translation, [ACIF-COMMAND] §11); no renderer reflows, reformats, or re-encodes body text.

## 9. Round-Trip Properties

For a canonical form `C` rendered to target `p` and canonicalized back:

```
canonicalize(render(C, p)) == C     modulo LOSSY(type, p)
```

where `LOSSY(type, p)` is the set of documented-lossy collapse points the owning L1's tables define for that target. The set MUST be enumerable from the published tables — a renderer whose round-trip loses anything not in the enumerable set is non-conformant. Values the target re-derives by its own documented semantics (a stripped explicit MCP `type`) round-trip to identical canonical bytes and identical `body_hash` and are not lossy.

*(Informative)* Round-trip identity is what makes render-back safe to automate: a registry or install tool can verify its own renderer by re-canonicalizing the output and comparing hashes, with the documented-lossy set as the only sanctioned diff.

## 10. Per-Type Render Sections

| Content type | Render rules | Notable outcomes |
|---|---|---|
| hook | [ACIF-HOOK] §12 | OS-mechanism degradation; the one refuse outcome; dead-default preservation |
| skill | [ACIF-SKILL] §12 | Canonical entry filename; no invented frontmatter keys |
| rule | [ACIF-RULE] §11 | Activation-mode declaration translation; gate-loss degradation diagnostic |
| command | [ACIF-COMMAND] §11 | Placeholder translation; untranslated-carry diagnostic |
| agent | [ACIF-AGENT] §11 | Tool-name translation; declared names never replaced by resolved UUIDs |
| mcp_config | [ACIF-MCP] §10 | Type strip-and-restore; sorted tool-filter arrays |

An L1 revision may add rows to its own render section without amending this document; this framework is deliberately closed over classes and disciplines, not over per-type content.

## 11. Provider-Support Data *(informative)*

Which providers carry which features — the input to choosing degradation paths — is observational capability-matrix data, not normative content of this document set. The capmon project publishes per-provider capability facts conforming to ACIF's canonical vocabularies (each published canonical key reserving a `spec_ref` into these documents); a renderer or registry consuming such a matrix gets its degradation predictions from living data rather than from spec snapshots. Nothing in a capability matrix relaxes a vocabulary table: a matrix says what a provider supports, never what a name means.

The observational polarity is specific to *capability* facts, whose consumers warn and predict. Provider *placement* facts — where a provider reads a content type on disk — ground a conforming actor's MUST-behavior and are therefore frozen normative rows ([ACIF-INSTALL] Appendix A.2, with its own maintenance lane); the two matrices differ in polarity because they differ in what a stale row breaks.

## 12. Error Identifiers

This document mints no error identifiers: every render diagnostic and refuse identifier is owned by the L1 specification that defines the condition (§7). This is deliberate — a degradation's meaning is per-type, and centralizing the identifiers here would put their conditions and their definitions in different documents.

## 13. Security Considerations

**Rendered output is installed content.** A renderer's output lands in provider configuration that executes (hooks, MCP) or instructs (skills, rules, agents, commands). The structured-encoder rule (§8) is the injection defense: a canonical value crafted to break out of a string-spliced context (an interpreter flag containing format metacharacters) is inert when re-serialized through a real encoder.

**Degradation can be a security downgrade.** Dropping OS overrides, losing a `manual` activation gate, and carrying an unexpanded placeholder each change what runs or loads. The mandatory diagnostics exist so automation above the renderer — CI, install tools, policy engines — can gate on degradation rather than discover it in behavior. Suppressing the diagnostics removes the only machine-readable signal that the output means less than the input.

**Round-trip verification is cheap and worth mandating locally.** Because rendering is deterministic (§6.2) and round-trip loss is enumerable (§9), a consumer can verify any renderer's output by re-canonicalizing and comparing `body_hash` against the expected lossy set. Deployments that install rendered output automatically should do so.

**Refusal is fail-closed.** The refuse lane exists because emitting a wrong-for-some-deployment artifact is a silent misconfiguration factory; implementations MUST NOT convert a refuse outcome into a best-effort emit under an option flag (§6.1).

## 14. References

### 14.1 Normative

- [ACIF-CORE] "ACIF Core Specification", version 0.1.x. `../core/spec.md`
- [ACIF-HOOK] / [ACIF-SKILL] / [ACIF-RULE] / [ACIF-COMMAND] / [ACIF-AGENT] / [ACIF-MCP] — the six L1 interchange specifications, version 0.1.x, sibling directories under `specs/`.
- [RFC2119] Bradner, S., "Key words for use in RFCs to Indicate Requirement Levels", BCP 14, RFC 2119, March 1997. <https://www.rfc-editor.org/rfc/rfc2119>
- [RFC8174] Leiba, B., "Ambiguity of Uppercase vs Lowercase in RFC 2119 Key Words", BCP 14, RFC 8174, May 2017. <https://www.rfc-editor.org/rfc/rfc8174>

### 14.2 Informative

- [ACIF-PUBLISHER] "ACIF Publisher Record Specification", version 0.1.x. `../publisher-spec/spec.md`.
- [ACIF-REGISTRY] "ACIF Registry Specification", version 0.1.x. `../registry-spec/spec.md`.
- [CAPMON] capmon — provider capability matrix publishing per-provider facts conforming to ACIF canonical vocabularies (§11).
- [SHAPE] ACIF design record: `SHAPE.md` and `panel/platform-commands-consensus.md` in the ACIF repository — decision provenance (Decisions #24 round-trip clause, #25/#29/#30/#31 render-back targets, #33 render rules).

---

## Appendix A — Conformance Test-Vector Family (Normative)

The vectors in this family, published in the `conformance/` directory, are normatively authoritative over prose. Per-type render vectors live in their L1 families (TV-PLATFORM (o)/(p)/(r), TV-RULE (m), TV-COMMAND (a)/(b), TV-AGENT (h)/(k), TV-MCP (l)); this family carries the framework-level vectors:

**TV-RENDER-\***: (a) determinism — one canonical form, one render context, two invocations (and two independent implementations where available) → byte-identical output; (b) structured-encoder generic — an injection-shaped opaque passthrough value (quotes, braces, format metacharacters) renders encoded, never spliced, on every supported target format; (c) degradation-diagnostic pairing — for each degraded path exercised by an L1 vector, output without the paired diagnostic is non-conformant (the vector asserts the pair, not the parts); (d) round-trip closure — for each (type, target) pair claimed, `canonicalize(render(C, p))` differs from `C` only within the published `LOSSY(type, p)` set, and `body_hash` is unchanged whenever that set is empty for the exercised form.

Individual vector IDs are assigned in the conformance suite.

## Appendix B — Provenance (Informative)

Promoted 2026-07-11 from the ACIF design record: the render-back clauses distributed across Decisions #24 (strip-and-restore), #25/#29 (vocabulary render targets and tiebreakers), #30/#31 (mode and placeholder render rules), and #33 (degradation lanes, the structured-encoder rule, dead-default preservation, the refuse outcome), generalized here into the framework the per-type sections instantiate.

Newly minted at spec-promotion time (not present in the design record; flagged for review): the fidelity-class taxonomy of §7 (the design record defined the individual outcomes; the four-class framing, the one-disclosure-home rule, and the no-reclassification rule are promotion-time generalizations); the §6.1 render-context pinning and the options-don't-change-bytes rule; the §6.2 fixed-member-order requirement; the §9 enumerable-lossy-set conformance bound; and the TV-RENDER family. These items were ratified back into the design record (SHAPE.md, Spec-Promotion Ratifications section) at promotion time.
