# ACIF Command Interchange Specification

**Version:** 0.1.0
**Status:** Draft
**Spec ID:** [ACIF-COMMAND]

---

## Abstract

This document defines the canonical interchange form for the command content type: a user-invocable prompt template that an AI coding tool expands and submits to the model. It specifies the canonical command model, the argument-placeholder vocabulary and its rewrite rules, the command hash boundary, the passthrough frontmatter surface, capability dispositions, the advisory token-presence projection, render-back requirements, and the command error-identifier registry.

## 1. Introduction

A command (a "slash command" in most providers) is a Markdown prompt body, optionally with frontmatter, that the provider expands — substituting user-supplied arguments into placeholder tokens — and runs as a prompt. Providers differ in placeholder syntax (`$ARGUMENTS`, `{{args}}`, `${input:name}`), frontmatter dialects, and invocation surfaces; this document defines the provider-neutral canonical form, including the canonical placeholder token and the total rewrite mapping that makes `body_hash` deterministic across source dialects.

Commands are a frontmatter-bearing content type ([ACIF-CORE] §6.1). The command's canonical body is the prompt prose; its frontmatter fields are carried one-to-one as opaque passthrough (§6) — transport, not capability promotion.

The argument-placeholder vocabulary in this document is ACIF-owned normative text (Appendix A); downstream implementations conform to this document's copy.

## 2. Relationship to ACIF Core

This document is a Level 1 (L1) companion to [ACIF-CORE] and depends on it normatively. Conformance to this document requires conformance to [ACIF-CORE]; every discipline in [ACIF-CORE] §8 and the capability model in [ACIF-CORE] §9 apply to commands without restatement. This document adds command-specific requirements only; it redefines no [ACIF-CORE] term.

This document is compatible with [ACIF-CORE] version 0.1.x. Both documents are Draft maturity; changes to [ACIF-CORE] may require corresponding changes here.

## 3. Terminology

Terms defined in [ACIF-CORE] §2 are used without redefinition. Additionally:

**placeholder** — a token in the command body that the provider replaces with user-supplied arguments at invocation. The canonical token is `$ARGUMENTS` (Appendix A).

**indexed placeholder** — the `$ARGUMENTS[N]` form addressing one argument by position.

**positional form** — a shell-style argument token (`$1`, `$2`, `${@:N}`) that some providers expand; documented-unrecognized in ACIF 0.1 (Appendix A.3).

**injection directive** — a provider-native token that splices dynamic content (shell output, file contents) into the body at invocation; out of the placeholder vocabulary's scope (Appendix A.4).

**latent field** — a frontmatter field carried as opaque passthrough (§6.2) that is a candidate for future canonical promotion but is not capability vocabulary in ACIF 0.1.

## 4. Requirements Language

The key words "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHALL NOT", "SHOULD", "SHOULD NOT", "RECOMMENDED", "NOT RECOMMENDED", "MAY", and "OPTIONAL" in this document are to be interpreted as described in BCP 14 [RFC2119] [RFC8174] when, and only when, they appear in all capitals, as shown here.

## 5. Conformance

This document extends the [ACIF-CORE] §4 conformance classes with command-specific requirements and adds one class:

**Conforming canonicalizer** — additionally satisfies §6–§8 (model validation, placeholder rewrite, hash boundary).

**Conforming validator** — additionally satisfies the reject conditions of [ACIF-CORE] §9.4 as applied in §9.3, evaluated over canonical form.

**Conforming command record** — an item with `kind: command` conforms if it satisfies [ACIF-CORE] §5 and §6 of this document.

**Conforming install tool** — carries no command-specific refuse obligation; when it warns per §10.2, it MUST report `acif.command.placeholder_untranslated` verbatim ([ACIF-CORE] §8.7).

**Conforming renderer** — software that emits a provider-native form from canonical form; satisfies §11.

Registry conformance is defined in [ACIF-REGISTRY]; §10 of this document states the command-specific compute obligations and permissions a conforming registry inherits.

The test-vector families in Appendix B are normatively authoritative: an implementation that contradicts a published vector is non-conformant regardless of any prose reading.

## 6. Canonical Command Model

### 6.1 Schema

The command extension block appears below the common envelope when `kind: command`:

```yaml
command:
  # Passthrough frontmatter surface — carried 1:1, values opaque (§6.2)
  allowed_tools: [Read, Edit]     # OPTIONAL
  context: fork                   # OPTIONAL
  agent: "Explore"                # OPTIONAL — latent name-based cross-type reference (§6.2)
  model: "..."                    # OPTIONAL — provider-specific ID, opaque
  disable_model_invocation: false # OPTIONAL
  user_invocable: true            # OPTIONAL
  argument_hint: "<pr-number>"    # OPTIONAL — display-only free text
  effort: "high"                  # OPTIONAL — provider enum, opaque

  requires: {}                    # OPTIONAL — empty/absent in 0.1 (§9)
```

### 6.2 The passthrough surface

The passthrough fields above are carried one-to-one as opaque passthrough ([ACIF-CORE] §8.5): no live validation, no value allowlists, no canonical enums. Transport is not promotion — none of these fields is capability vocabulary in ACIF 0.1, and their presence MUST NOT soften the orphan-key reject (§9.3). Their promotion questions are a roadmap item with recorded obligations: `allowed_tools` MUST use the [ACIF-CORE] Appendix A tool vocabulary if promoted (no second tool vocabulary); `agent` is a latent name-based cross-type reference whose promotion requires resolving name-vs-UUID against the [ACIF-CORE] §10 UUID pattern; `effort` needs an owned enum with a total mapping if promoted; `user_invocable`/`disable_model_invocation` MUST be disposed uniformly with the skill equivalents ([ACIF-SKILL] §6.2) when promoted.

*(Informative)* The passthrough surface exists because render-back needs these fields for round-trip fidelity; a minimal block would break round-trip. Values stay opaque because live validation of provider-owned values (model IDs, effort levels) is a brittle-list trap.

**`requires`** — OPTIONAL. The recognized `requires` vocabulary for commands is empty in ACIF 0.1 (§9); any key present is non-conformant ([ACIF-CORE] §9.4).

## 7. Placeholder Canonicalization

Canonicalization rewrites provider placeholder syntaxes to the canonical `$ARGUMENTS` token per the total mapping in Appendix A before `body_hash` is computed ([ACIF-CORE] §8.2). Normative properties of the rewrite:

- **Exact and deterministic.** Matching is exact-byte, case-sensitive, under the Appendix A.2 boundary rule. Rewrites are **non-markdown-aware**: a token inside a code fence is rewritten identically to one outside. *(Informative: fence-awareness would make canonical bytes depend on the implementation's Markdown parser — a cross-registry divergence of the same class the materialize-then-hash rules exist to prevent. Determinism over cleverness.)*
- **Lossy collapse disclosed.** Named-variable forms (`${input:varName}`, `${input:varName:placeholder}`) collapse to the single positional `$ARGUMENTS`; canonicalization MUST emit `acif.command.placeholder_named_arg_collapsed` (INFORMATIVE class) on each collapse, and render-back non-identity is documented (§11).
- **Positional forms documented-unrecognized.** `$1`, `$2`, `${@:N}` are carried verbatim: no rewrite, no diagnostic, no advisory signal (Appendix A.3). *(Informative: they cannot map to `$ARGUMENTS` without destroying positional semantics, and detecting them for rewrite would mutate legitimate shell content in prose. This is a disclosed false-negative of the §10.1 projection; positional canonicalization is a roadmap item gated on structured-record-grade parsing.)*
- **Injection directives out of scope.** Shell-injection and file-inclusion directives (`!{...}`, `@{...}`) are not argument substitution; they are carried verbatim and recorded as threat context (§14). This is a deliberate scope pin, not an omission.
- **No escape form.** A literal `$ARGUMENTS` in rendered output is not expressible in ACIF 0.1; no escape grammar is invented. Documented limitation.
- **Zero reject codes.** The placeholder vocabulary mints no reject identifiers — an unrecognized token passes through as opaque prose. *(Informative: this is a deliberate asymmetry with the rule activation enum ([ACIF-RULE]), which validates a closed enum over a discriminant field where unknown values corrupt semantics; here no field is being validated, so there is nothing to reject.)*

## 8. Body and Hash Boundary

### 8.1 `body_hash`

The command's canonical body is the prompt prose. `body_hash` follows [ACIF-CORE] §7, computed over the **post-rewrite** form (§7): single-file bodies hash the canonical text form with the frontmatter block stripped; a command shipping co-located content files classifies multi-file per [ACIF-CORE] §7.2.

### 8.2 Extension-block hash coverage

Commands are frontmatter-bearing, so per [ACIF-CORE] §7.8 the extension block MUST NOT enter the `body_hash` preimage. Declared frontmatter fields — the §6.1 passthrough surface — are observed faithfully into `publisher_section` and covered by `metadata_hash` ([ACIF-PUBLISHER]).

Consequences (normative in effect, stated for clarity): a `model` re-pin, an `allowed_tools` edit, or a `user_invocable` flip moves `metadata_hash`, not `body_hash`; two commands identical in body but differing in frontmatter have identical `body_hash` and different `metadata_hash`.

## 9. Capability Dispositions

The recognized `requires` vocabulary for commands is **empty** in ACIF 0.1: **no capability key of the command vocabulary is DERIVABLE** — the only vocabulary of the six content types with zero derivation predicates. Every key is disposed per [ACIF-CORE] §9.2 as follows.

### 9.1 OUT-OF-SCOPE-AT-L1: `argument_substitution` *(informative rationale)*

The `$ARGUMENTS` token lives in body prose; no canonical field carries it, and under the derivation-vs-heuristic rule ([ACIF-CORE] §9.2) a substring scan over prose is a heuristic regardless of the token being canonicalization-pinned: it false-positives on fenced-code mentions (the token is canonicalizer-*normalized*, not canonicalizer-*validated* — an occurrence in a code fence is canonical, hash-stable, and semantically inert) and false-negatives on positional-only bodies (Appendix A.3). It also derives strictly narrower than the key it would claim to derive, whose definition includes the positional forms. The body signal ships as the §10.1 advisory projection; the provider-support signal ships as a `provider_capability_coverage` row ([ACIF-REGISTRY]). Body-carried, therefore never `requires`-eligible ([ACIF-CORE] §9.3).

The contrast case is [ACIF-MCP] §9.1's `env_var_expansion`, which IS a derivation despite also scanning for a token: its domain is a pinned closed set of structured wiring fields, while this scan's domain is unstructured body prose. The line is domain structure — the same rule disposes both.

### 9.2 OUT-OF-SCOPE-AT-L1: `builtin_commands` *(informative rationale)*

Whether a provider ships built-in commands is a provider-side namespace fact — not authored on the item, not derivable from any body. It surfaces as a `provider_capability_coverage` row. Recorded severity finding: **HIGH in the shadowing direction** — a published command whose name collides with a provider builtin resolves to the wrong handler silently (silent semantic corruption, not a safe no-op). A normative shadowing check is infeasible in 0.1 — builtin name-sets vary per provider release and per plan, a brittle-list trap — so the countermeasures are registry-discretion lint (§10.3) and a roadmap builtin-namespace entry. The reverse direction (a body invoking a missing builtin) degrades to a no-op; LOW.

### 9.3 Orphan keys

Any `requires.<key>` on a command item is non-conformant ([ACIF-CORE] §9.4) — four distinct reject reasons, one outcome: `requires.argument_substitution` (considered-and-disposed), `requires.builtin_commands` (OUT-OF-SCOPE key), `requires.handler_types` (foreign-type key), `requires.disable_model_invocation` (latent-field match; presence of the matching §6.1 field MUST NOT soften the reject). An unrecognized key evaluated by a consumer follows the three-valued rule ([ACIF-CORE] §9.5).

## 10. Registry Projections

### 10.1 Advisory token-presence projection

A registry MAY compute an advisory argument-token-presence signal per command item:

```yaml
advisory:
  argument_substitution_token:
    present: true
    method: "substring-canonical-v1"
```

- **Scan:** exact, case-sensitive, byte-deterministic, non-markdown-aware, over the frontmatter-stripped canonical body, using the Appendix A.2 boundary rule.
- **Shape:** `{present: bool, method: <string>}`. The method stamp is REQUIRED when the projection is emitted; a per-item confidence score MUST NOT be emitted (a single deterministic method has constant confidence — a score would be noise). No forms-set is emitted in 0.1.
- **Status:** advisory — never a D_K, never sets `derivable`, never gates conformance or install. Disclosed imprecision, both directions: false-positive on fenced-code mentions; false-negative on positional-only bodies.

### 10.2 Degradation warning (install-time)

Install tools SHOULD warn — reporting `acif.command.placeholder_untranslated` — when installing a command whose advisory projection has `present: true` to a provider absent from the `argument_substitution` coverage row. The degradation is graceful (the token renders as literal text), so this obligation is SHOULD-warn, never refuse: the refuse lane is reserved for `requires` ([ACIF-CORE] §9.5).

### 10.3 `provider_capability_coverage` and shadowing lint

Registries MUST surface provider-coverage rows for `argument_substitution` and `builtin_commands` from capability-matrix data ([ACIF-REGISTRY]). A registry MAY emit a builtin-shadowing collision advisory for a command whose name matches a known provider builtin; when emitted, the diagnostic MUST name the provider(s) and the colliding name. The check itself is discretionary in 0.1 (§9.2).

## 11. Render-Back Requirements

These requirements bind conforming renderers; the general render-back framework is [ACIF-RENDER].

- **Placeholder translation.** Rendering to a provider with a placeholder mapping row (Appendix A.1) emits that provider's native form. Rendering the canonical token to a provider with no row carries `$ARGUMENTS` verbatim, and the renderer MUST emit `acif.command.placeholder_untranslated` for the carry. Round-trip through the named-variable collapse is documented-lossy: `${input:filename}` canonicalizes to `$ARGUMENTS` and renders back as the target's generic form, not the original variable name.
- **Frontmatter projection.** Passthrough fields (§6.1) MUST be re-serialized through the target format's structured encoder ([ACIF-CORE] §8.5); string-splicing is non-conformant.
- **Body fidelity.** Outside placeholder translation, the body is emitted byte-verbatim — positional forms and injection directives included (§7).

## 12. Cross-References

The `agent` field is a latent name-based reference and is NOT a load-bearing cross-reference in ACIF 0.1: it is opaque passthrough (§6.2), registries do not resolve it, and the [ACIF-CORE] §10 refusal rule does not apply to it. Promotion to a UUID-based reference is a recorded roadmap obligation (§6.2).

## 13. Error Identifiers

| Identifier | Class | Condition |
|---|---|---|
| `acif.command.placeholder_named_arg_collapsed` | diagnostic (INFORMATIVE) | Named-variable placeholder collapsed to `$ARGUMENTS` at canonicalization (§7) |
| `acif.command.placeholder_untranslated` | diagnostic (render MUST-emit; install-time SHOULD-warn) | Canonical token carried verbatim to a target with no mapping row (§11), or token-present item installed to a non-supporting provider (§10.2) |

This vocabulary deliberately mints no reject identifiers (§7). The two obligations on `placeholder_untranslated` bind different actors for different acts — the renderer emitting output, and the install tool predicting degradation — and never bind the same actor twice for one act.

## 14. Security Considerations

**The body is a prompt.** A command body becomes model instructions on invocation; injection content in it is load-bearing. Unlike always-on rules, a command fires only when invoked — the invocation gate bounds exposure but does not remove it.

**Injection directives are provider-conditional detonation.** A shell-injection directive (`!{...}`) in a command body executes shell commands on providers that support it and renders as literal text everywhere else: the same bytes are a payload on one install target and prose on another. ACIF carries these directives verbatim (§7) and does not model them; the blast radius is scoped by the install target's coverage row, and registries should treat directive-bearing bodies as a moderation-priority class. File-inclusion directives (`@{...}`) are the same shape with the rule-import exfiltration profile ([ACIF-RULE] §14).

**Builtin shadowing is silent misdirection.** §9.2's HIGH finding: a command named to collide with a provider builtin hijacks an invocation the user believes is built-in. No canonical field can prevent this; the registry-side lint and the roadmap namespace entry are the countermeasures.

**Stealth commands.** A command with `user_invocable: false` (hidden from user menus) that remains model-invocable is a low-visibility execution path. The field is opaque passthrough in 0.1; its promotion (with uniform skill/command disposition) is the recorded path to making this filterable.

**Placeholder expansion is user input.** `$ARGUMENTS` splices raw user input into the prompt at a position the author chose. This is the command mechanism working as designed; authors and moderation should treat placeholder positions as untrusted-input sinks.

**Metadata is self-asserted.** Everything in [ACIF-CORE] §11 applies.

## 15. References

### 15.1 Normative

- [ACIF-CORE] "ACIF Core Specification", version 0.1.x. `../core/spec.md`
- [RFC2119] Bradner, S., "Key words for use in RFCs to Indicate Requirement Levels", BCP 14, RFC 2119, March 1997. <https://www.rfc-editor.org/rfc/rfc2119>
- [RFC8174] Leiba, B., "Ambiguity of Uppercase vs Lowercase in RFC 2119 Key Words", BCP 14, RFC 8174, May 2017. <https://www.rfc-editor.org/rfc/rfc8174>

### 15.2 Informative

- [ACIF-SKILL] "ACIF Skill Interchange Specification", version 0.1.x. `../skill-interchange/spec.md` — the uniformity constraint on invocability fields.
- [ACIF-RULE] "ACIF Rule Interchange Specification", version 0.1.x. `../rule-interchange/spec.md` — the enum-with-rejects counterpart discipline and the import threat profile.
- [ACIF-PUBLISHER] "ACIF Publisher Record Specification", version 0.1.x. `../publisher-spec/spec.md`.
- [ACIF-REGISTRY] "ACIF Registry Specification", version 0.1.x. `../registry-spec/spec.md`.
- [ACIF-RENDER] "ACIF Render-Back Specification", version 0.1.x. `../render-back/spec.md`.
- [SHAPE] ACIF design record: `SHAPE.md` and `panel/commands-requires-consensus.md` in the ACIF repository — decision provenance (Decisions #12, #23 as refined, #31).

---

## Appendix A — Canonical Argument-Placeholder Vocabulary (Normative)

This appendix is ACIF-owned normative text; implementations conform to this copy. It is normative for the canonical token, the mapping rows, the boundary rule, and the scope exclusions.

### A.1 Canonical token and total mapping

Canonical token: `$ARGUMENTS`, with the indexed form `$ARGUMENTS[N]` (N a non-negative decimal integer).

| Source form | Provider provenance | Canonical | Fidelity |
|---|---|---|---|
| `$ARGUMENTS` / `$ARGUMENTS[N]` | claude-code and compatibles | identity | Lossless |
| `{{args}}` | gemini-cli | `$ARGUMENTS` | Lossless |
| `${input:varName}` | VS Code family | `$ARGUMENTS` | **Lossy** — named → single positional; MUST emit `acif.command.placeholder_named_arg_collapsed` |
| `${input:varName:placeholder}` | VS Code family | `$ARGUMENTS` | **Lossy** — as above |

`body_hash` is computed post-rewrite (§8.1). Any token not in this table is not a placeholder and passes through as opaque prose — zero reject codes (§7).

### A.2 Token boundary rule

Matching is exact-byte and case-sensitive. `$ARGUMENTS` is recognized when the immediately following byte is not in `[A-Za-z0-9_]`: end-of-body qualifies; `[` qualifies (so `$ARGUMENTS[N]` is recognized); `$ARGUMENTSFOO` is not recognized. The same boundary rule governs the §10.1 advisory scan.

### A.3 Positional forms — documented-unrecognized

`$1`, `$2`, `${@:N}` and kin are carried verbatim: no rewrite, no diagnostic, no advisory signal. They cannot collapse to `$ARGUMENTS` without destroying positional semantics, and rewriting them would mutate legitimate shell content in bodies. This is a disclosed false-negative of the advisory projection. Positional canonicalization is a roadmap item gated on structured-record-grade body parsing.

### A.4 Scope exclusions

`!{...}` (shell-command injection) and `@{...}` (file inclusion) are dynamic-content-injection directives, not argument substitution: outside this vocabulary, carried verbatim, recorded as threat context (§14).

## Appendix B — Conformance Test-Vector Families (Normative)

The vectors in these families, published in the `conformance/` directory, are normatively authoritative over prose. Family definition:

**TV-COMMAND-\***: (a) placeholder canonicalization — `{{args}}` → `$ARGUMENTS`; identity forms; `body_hash` post-rewrite; render-back to a `{{args}}` target and a `${input:}` target; render-back to a no-row target carries `$ARGUMENTS` verbatim + MUST `acif.command.placeholder_untranslated`; (b) lossy named collapse — `${input:filename}` and `${input:message}` → same canonical body → **identical `body_hash`**; `placeholder_named_arg_collapsed` emitted; render-back non-identity documented; (c) token boundary — `$ARGUMENTS` recognized; `$ARGUMENTS[0]` recognized; `$ARGUMENTSFOO` not; end-of-body recognized; (d) fenced-code behavior — a token inside a code fence is rewritten and scanned identically to one outside (non-markdown-aware pin); (e) no-escape-literal — literal-intent `$ARGUMENTS` is still the placeholder; (f) unrecognized positional — body with only `$1`/`${@:N}` → carried verbatim, no rewrite, no advisory signal; (g) injection directives out of scope — `!{shell}` / `@{file}` → not placeholders, carried verbatim; (h) frontmatter stripped from `body_hash` — same body, different `model`/`allowed_tools` → identical `body_hash`; (h′) hash boundary companion — the same frontmatter change moves `metadata_hash` ([ACIF-CORE] §7.8); (i) empty `requires` conformant; (j) orphan-key reject, four distinct reject reasons — `requires.argument_substitution`, `requires.builtin_commands`, `requires.handler_types`, `requires.disable_model_invocation` (latent match, no softening); (k) unknown-key three-valued evaluation; (l) *(conditional)* builtin-shadowing advisory — a command named `/compact` → registry MAY emit a collision advisory; the vector tests the diagnostic shape if emitted, not whether it is emitted; (m) advisory projection shape — `{present, method: "substring-canonical-v1"}`, no confidence score, no forms-set.

Individual vector IDs are assigned in the conformance suite.

## Appendix C — Provenance and Preserved Positions (Informative)

Promoted 2026-07-11 from the ACIF design record: the command extension block and Decisions #12, #23 (commands application, derivation-vs-heuristic refinement, three-way routing) and #31 of `SHAPE.md`, with the full deliberation record in `panel/commands-requires-consensus.md` — the final walk of the capability series, closing the `requires` question six-for-six.

Preserved positions recorded for future revision: registry-operator's DERIVABLE-with-totality minority position (the advisory projection ships the same installer join, so the practical loss was the `derivable` flag, not the signal; his existence-proof framing — a deterministic advisory scan at registry scale is evidence a structured import grammar could run too — is input to the reference-grammar roadmap item); spec-purist's conditional body-token discipline (the authorship test, boundary-precise, disclosed-imprecision — the recorded design if body-content derivation is ever legitimized, which requires a structured canonical record, never a prose scan promoted to a predicate); Remy's sparse-vocabulary caveat (two keys is the weakest evidence in the series; the validation weight rests on the rules walk).

Newly minted at spec-promotion time (not present in the design record; flagged for review): the identifier `acif.command.placeholder_untranslated` and its dual-actor obligation (§10.2/§11 — the design record described the render warning and the install-time SHOULD-warn without naming an identifier; the template discipline requires SHOULD-warn obligations to carry one); the §10.3 requirement that a discretionary shadowing advisory, when emitted, names the provider(s) and colliding name; and the TV-COMMAND (h′)/(m) vectors. These items were ratified back into the design record (SHAPE.md, Spec-Promotion Ratifications section) at promotion time.
