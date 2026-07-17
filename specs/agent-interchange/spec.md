# ACIF Agent Interchange Specification

**Version:** 0.1.0
**Status:** Draft
**Spec ID:** [ACIF-AGENT]

---

## Abstract

This document defines the canonical interchange form for the agent content type: a named, prompt-defined sub-agent persona that an AI coding tool can delegate work to, with optional tool restrictions, a model pin, and references to MCP configurations and skills. It specifies the canonical agent model, tool-name canonicalization, the agent hash boundary, derivation predicates, name-declared cross-reference resolution, render-back requirements, and the (empty) agent error-identifier registry.

## 1. Introduction

An agent is a Markdown document whose prose becomes a sub-agent's system prompt, with frontmatter declaring the agent's operational envelope: which tools it may use, which model runs it, which MCP servers and skills it draws on. Providers express agents in at least four source formats (Markdown with frontmatter, JSON, TOML, provider-specific mode files); this document defines the provider-neutral canonical form.

Agents are a frontmatter-bearing content type ([ACIF-CORE] §6.1): the sidecar is the primary carrier, and frontmatter on the source file is an opt-in supplementary layer. The agent body is prose that becomes a system prompt at runtime; ACIF 0.1 carries it opaquely.

## 2. Relationship to ACIF Core

This document is a Level 1 (L1) companion to [ACIF-CORE] and depends on it normatively. Conformance to this document requires conformance to [ACIF-CORE]; every discipline in [ACIF-CORE] §8, the capability model in [ACIF-CORE] §9, and the tool vocabulary in [ACIF-CORE] Appendix A apply to agents without restatement. This document adds agent-specific requirements only; it redefines no [ACIF-CORE] term.

This document is compatible with [ACIF-CORE] version 0.1.x. Both documents are Draft maturity; changes to [ACIF-CORE] may require corresponding changes here.

## 3. Terminology

Terms defined in [ACIF-CORE] §2 are used without redefinition. Additionally:

**tool restriction** — a declared allowlist (`tools`) or denylist (`disallowed_tools`) bounding which tools the agent may use.

**name-declared reference** — a cross-item reference authored as a bare name string (an entry of `mcp_servers` or `skills`), resolved to a target item by registry compute (§10).

**subagent-spawning agent** — an agent whose canonical `tools` list contains the canonical name `agent`, granting it the ability to spawn further sub-agents.

## 4. Requirements Language

The key words "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHALL NOT", "SHOULD", "SHOULD NOT", "RECOMMENDED", "NOT RECOMMENDED", "MAY", and "OPTIONAL" in this document are to be interpreted as described in BCP 14 [RFC2119] [RFC8174] when, and only when, they appear in all capitals, as shown here.

## 5. Conformance

This document extends the [ACIF-CORE] §4 conformance classes with agent-specific requirements and adds one class:

**Conforming canonicalizer** — additionally satisfies §6–§8 (model validation, tool-name canonicalization, hash boundary).

**Conforming validator** — additionally satisfies the reject conditions of [ACIF-CORE] §9.4 as applied in §9.3, evaluated over canonical form.

**Conforming agent record** — an item with `kind: agent` conforms if it satisfies [ACIF-CORE] §5 and §6 of this document.

**Conforming install tool** — additionally satisfies the [ACIF-CORE] §10 refusal rule as applied in §10.2.

**Conforming renderer** — software that emits a provider-native form from canonical form; satisfies §11.

Registry conformance is defined in [ACIF-REGISTRY]; §10 of this document states the agent-specific compute obligations a conforming registry inherits.

The test-vector families in Appendix A are normatively authoritative: an implementation that contradicts a published vector is non-conformant regardless of any prose reading.

## 6. Canonical Agent Model

### 6.1 Schema

The agent extension block appears below the common envelope when `kind: agent`:

```yaml
agent:
  tools: [file_read, file_edit, agent]  # OPTIONAL — allowlist; canonical tool names
                                        # ([ACIF-CORE] Appendix A)
  disallowed_tools: [shell]             # OPTIONAL — denylist; canonical tool names
  model: "claude-sonnet-5"              # OPTIONAL — provider-specific ID, opaque
  mcp_servers: ["figma"]                # OPTIONAL — name-declared references to
                                        # mcp_config items (§10.2)
  skills: ["tdd-workflow"]              # OPTIONAL — name-declared references to
                                        # skill items (§10.2)
  permission_mode: "..."                # OPTIONAL — opaque passthrough in 0.1 (§6.2)
  background: false                     # OPTIONAL — opaque passthrough in 0.1 (§6.2)

  requires: {}                          # OPTIONAL — empty/absent in 0.1 (§9)
```

### 6.2 Field requirements

**`tools`**, **`disallowed_tools`** — OPTIONAL arrays. In canonical form, entries that name general-purpose tools MUST be the canonical names of [ACIF-CORE] Appendix A; canonicalization rewrites provider-native names per that appendix's mappings and tiebreakers before any hash is computed ([ACIF-CORE] §8.2/§8.4). An entry not present in any mapping row — MCP-qualified names, provider-custom tools — passes through verbatim ([ACIF-CORE] §8.5, Appendix A.4). Array order is preserved (author-declared order; no set semantics are assigned in 0.1). Entries MUST be non-empty strings ([ACIF-CORE] §8.3).

**`model`** — OPTIONAL. A provider-specific model identifier, carried as an opaque value: no allowlist validation. Presence feeds the `model_selection` predicate (§9.1).

**`mcp_servers`**, **`skills`** — OPTIONAL arrays of name-declared references (§10.2). Entries MUST be non-empty strings.

**`permission_mode`**, **`background`** — OPTIONAL opaque passthrough in ACIF 0.1: carried verbatim for round-trip fidelity, no canonical enum minted. An owned enum with a total mapping is the recorded promotion path if these are ever made capability-bearing.

**`requires`** — OPTIONAL. The recognized `requires` vocabulary for agents is empty in ACIF 0.1 (§9); any key present is non-conformant ([ACIF-CORE] §9.4).

### 6.3 Declarative, not enforced *(informative)*

The extension block declares the agent's intended envelope; ACIF does not enforce it. Whether a provider honors `tools` restrictions or the `model` pin is provider behavior outside this document. The block's canonical value is interchange fidelity and the derivation signals of §9.

## 7. Tool-Name Canonicalization

Canonicalization rewrites provider-native tool names in `tools` and `disallowed_tools` to the canonical vocabulary before any hash is computed, applying [ACIF-CORE] Appendix A in full: the mapping rows, the write/edit-collapse tiebreaker, the legacy alias rule, and the verbatim passthrough of unparseable and MCP-style names. Reverse translation at render-back follows the same appendix (§11).

*(Informative)* The load-bearing consumer of this rule is the `subagent_spawning` predicate (§9.1): `contains(tools, "agent")` is well-defined only because every provider spelling of the spawn-subagent tool canonicalizes to the single name `agent`.

## 8. Body and Hash Boundary

### 8.1 `body_hash`

The agent's canonical body is the system-prompt prose. `body_hash` follows [ACIF-CORE] §7: single-file bodies hash the canonical text form with the frontmatter block stripped; an agent shipping co-located content files classifies multi-file per [ACIF-CORE] §7.2. The canonical entry file for classification is the agent source file itself: agents pin no canonical filename in 0.1, and the ingestion context designates which file is the source.

### 8.2 Extension-block hash coverage

Agents are frontmatter-bearing, so per [ACIF-CORE] §7.8 the extension block MUST NOT enter the `body_hash` preimage. Declared extension-block values — tool lists, `model`, reference arrays, passthrough fields — are observed faithfully into `publisher_section` **as declared** (provider-native spellings included) and covered by `metadata_hash` ([ACIF-PUBLISHER]). The vocabulary-translated form of §7 is canonical-form content that derivation predicates and projections read; it is not what `metadata_hash` is computed over.

Consequences (normative in effect, stated for clarity): editing `tools`, re-pinning `model`, or adding an `mcp_servers` entry moves `metadata_hash`, not `body_hash`; editing the prompt prose moves `body_hash` only.

## 9. Capability Dispositions and Derivation Predicates

The recognized `requires` vocabulary for agents is **empty** in ACIF 0.1. Every capability key of the agent vocabulary is disposed per [ACIF-CORE] §9.2 as follows.

### 9.1 DERIVABLE keys

| Key | D_K over canonical body B (post-translation, §7) |
|---|---|
| `tool_restrictions` | `len(B.tools) > 0 OR len(B.disallowed_tools) > 0` |
| `model_selection` | `B.model != ""` (strict emptiness, [ACIF-CORE] §8.3) |
| `per_agent_mcp` | `len(B.mcp_servers) > 0` |
| `subagent_spawning` | `contains(B.tools, "agent")` — `agent` is the canonical spawn-subagent name ([ACIF-CORE] Appendix A) |

Each predicate produces `{derivable-true, derivable-false}` per the boolean discipline; each cites a single canonical field. The `tool_restrictions` predicate is the one sanctioned compound form: both conjuncts cite single canonical arrays with pinned absent/empty/null semantics — absent, `[]`, and a null-valued field all yield length zero.

### 9.2 OUT-OF-SCOPE-AT-L1 keys *(informative rationale)*

`definition_format` is a meta-property: the canonical body *is* the format, and the source-format zoo is an [ACIF-RENDER] concern. `invocation_patterns` (@-mention vs slash vs auto-delegate) is provider picker UX — authors write a name and description; the provider chooses the surface; prose leakage of invocation intent is soft preference, not structured declaration. `agent_scopes` is install-location-determined: scope *compatibility* surfaces through `install_scope_capabilities` ([ACIF-REGISTRY]), and the on-disk locations themselves live in the provider install-target matrix ([ACIF-INSTALL] Appendix A.2). Under the out-of-band guardrail ([ACIF-CORE] §9.3) none is `requires`-eligible.

### 9.3 Orphan keys

Any `requires.<key>` on an agent item — including every key named in §9.1 and §9.2 — is non-conformant ([ACIF-CORE] §9.4). An unrecognized key evaluated by a consumer follows the three-valued rule ([ACIF-CORE] §9.5).

## 10. Registry Projections and Cross-Reference Resolution

### 10.1 `derived_capabilities`

A conforming registry MUST compute the four §9.1 predicates for every agent item at ingest and expose them per [ACIF-REGISTRY], alongside `body_size_bytes` ([ACIF-REGISTRY]) — agent prose becomes a system prompt, and the size field cost-bounds moderation scans of it.

### 10.2 Name-declared reference resolution

`mcp_servers` and `skills` entries are name-declared references: the author writes a bare name; no UUID is authored. A conforming registry MUST resolve each entry at compute time into the [ACIF-CORE] §10 state vocabulary (`declared | resolved | unresolved | revoked`), emitting one `cross_references` entry per declared name with the source path (e.g., `agent.mcp_servers[0]`), the declared name, the expected target kind, the resolved target's `id` when resolution succeeds, and a diagnostic naming the missing or revoked target otherwise (`acif.registry.reference_unresolved`; [ACIF-REGISTRY] §9 pins the record shape, §12 the identifier).

Install tools MUST refuse agent items carrying any `unresolved` or `revoked` reference unless the operator has explicitly opted in ([ACIF-CORE] §10).

*(Informative)* This is the name-first variant of the cross-reference pattern: hook→skill activation ([ACIF-HOOK]) authors the UUID directly and the name is advisory; agents author names because that is what every observed source format carries, and resolution is registry compute. The `declared` state exists precisely for the name-authored-but-not-yet-resolved condition.

## 11. Render-Back Requirements

These requirements bind conforming renderers; the general render-back framework is [ACIF-RENDER].

- The agent body is emitted byte-verbatim.
- Canonical tool names are translated to provider-native names per [ACIF-CORE] Appendix A; canonical names with no mapping row for the target emit verbatim ([ACIF-CORE] §8.5). Round-trips through providers with collapsed write/edit names are documented-lossy per that appendix.
- Opaque passthrough fields (`model`, `permission_mode`, `background`, and any carried provider-native field) MUST be re-serialized through the target format's structured encoder ([ACIF-CORE] §8.5).
- Name-declared references render as the declared names; renderers MUST NOT substitute resolved UUIDs into provider-native output.

## 12. Error Identifiers

This document mints no error identifiers. Agent canonicalization has no closed enum to validate — tool names not in the mapping pass through, `model` and the passthrough fields are opaque — so no reject condition exists beyond the [ACIF-CORE] envelope and capability rules, and the diagnostics for reference resolution are defined where the compute lives ([ACIF-REGISTRY]). *(Informative: the deliberate contrast is [ACIF-RULE], which validates a closed discriminant enum and therefore rejects; the asymmetry rationale is the same as [ACIF-COMMAND] §7's zero-reject-codes note.)*

## 13. Security Considerations

**The body is a system prompt.** Agent prose is injected as a sub-agent's system prompt with whatever tool envelope the block declares; injection content in it is load-bearing and executes with the agent's tool access, not the user's attention. Agents and skills are the two highest-value prose-injection surfaces in this document set; `body_size_bytes` exists to cost-bound scanning them.

**Tool restrictions are self-asserted scope, not sandboxing.** `tools`/`disallowed_tools` declare intent; nothing in ACIF verifies a provider enforces them. A consumer that treats a declared denylist as a security boundary has no basis for doing so (§6.3).

**Subagent spawning is an amplifier.** An agent whose `tools` contains `agent` can delegate to further sub-agents, multiplying any injected instruction's reach. The `subagent_spawning` projection (§9.1) exists so installers and policy engines can gate on it — a fleet policy such as "no spawning agents from unreviewed publishers" is implementable from canonical structure.

**Name-declared references can be squatted.** `mcp_servers` and `skills` resolve by name at the registry; a malicious item published under a popular declared name is the resolution-layer analog of typosquatting. The four-state resolution with install-time refusal on `unresolved`/`revoked` (§10.2) is the countermeasure lane; resolution policy (which candidate wins a name) is registry-scoped and out of scope here.

**Model pinning is unverified.** A `model` value naming a weaker or unexpected model changes the agent's behavior envelope; the value is opaque and self-asserted.

**Metadata is self-asserted.** Everything in [ACIF-CORE] §11 applies.

## 14. References

### 14.1 Normative

- [ACIF-CORE] "ACIF Core Specification", version 0.1.x. `../core/spec.md`
- [RFC2119] Bradner, S., "Key words for use in RFCs to Indicate Requirement Levels", BCP 14, RFC 2119, March 1997. <https://www.rfc-editor.org/rfc/rfc2119>
- [RFC8174] Leiba, B., "Ambiguity of Uppercase vs Lowercase in RFC 2119 Key Words", BCP 14, RFC 8174, May 2017. <https://www.rfc-editor.org/rfc/rfc8174>

### 14.2 Informative

- [ACIF-HOOK] "ACIF Hook Interchange Specification", version 0.1.x. `../hooks-interchange/spec.md` — the UUID-authored cross-reference counterpart.
- [ACIF-SKILL] "ACIF Skill Interchange Specification", version 0.1.x. `../skill-interchange/spec.md`.
- [ACIF-COMMAND] "ACIF Command Interchange Specification", version 0.1.x. `../command-interchange/spec.md` — the zero-reject-codes asymmetry note.
- [ACIF-RULE] "ACIF Rule Interchange Specification", version 0.1.x. `../rule-interchange/spec.md`.
- [ACIF-PUBLISHER] "ACIF Publisher Record Specification", version 0.1.x. `../publisher-spec/spec.md`.
- [ACIF-REGISTRY] "ACIF Registry Specification", version 0.1.x. `../registry-spec/spec.md`.
- [ACIF-RENDER] "ACIF Render-Back Specification", version 0.1.x. `../render-back/spec.md`.
- [SHAPE] ACIF design record: `SHAPE.md` and `panel/agents-requires-consensus.md` in the ACIF repository — decision provenance (Decisions #23, #25, #26, #27, #28).

---

## Appendix A — Conformance Test-Vector Families (Normative)

The vectors in these families, published in the `conformance/` directory, are normatively authoritative over prose. Family definition:

**TV-AGENT-\***: (a) empty `requires` conformant; (b) unknown-key three-valued evaluation; (c) orphan-key reject — any DERIVABLE key (e.g., `requires.tool_restrictions`) on an agent item is non-conformant; a recognized-elsewhere key on a non-agent item likewise rejects under per-type scoping; (d) `D_K` tool_restrictions — `tools: [file_read]` → derivable-true; both arrays absent/empty → derivable-false; `disallowed_tools`-only → derivable-true; (e) `D_K` model_selection — non-empty → true; absent/empty → false; (f) `D_K` per_agent_mcp — same shape over `mcp_servers`; (g) `D_K` subagent_spawning — `tools: [agent]` → true; `tools: [file_read, file_edit]` → false (locks the canonical-name pin); (h) tool-name canonicalization — a source declaring provider-native spawn names (`Agent`, `task`, `spawn_agent`, `use_subagent`, legacy `Task`) canonicalizes to `tools: [agent]`; the translation affects canonical form and its predicates, `body_hash` (prose) is unaffected, and the declared raw spellings ride `metadata_hash` ([ACIF-CORE] §7.8); render-back translates to the target's native name; (i) hash boundary — re-pinning `model` with body bytes unchanged moves `metadata_hash` and MUST NOT move `body_hash`; editing prompt prose moves `body_hash` and MUST NOT move `metadata_hash`; (j) name-declared resolution — `mcp_servers: ["figma"]` with a resolvable target → `cross_references` entry with `resolution: resolved` + target `id`; with no target → `unresolved` + diagnostic naming `figma`; install MUST refuse unless opted in; (k) write/edit-collapse round-trip — canonical `file_edit` survives a round-trip through a collapsing provider; the collapse is documented-lossy per [ACIF-CORE] Appendix A.2.

Individual vector IDs are assigned in the conformance suite.

## Appendix B — Provenance and Preserved Positions (Informative)

Promoted 2026-07-11 from the ACIF design record: Decisions #23 (agents application), #25, #26, #27, and #28 of `SHAPE.md`, with the full deliberation record in `panel/agents-requires-consensus.md` (unanimous empty-`requires` verdict; the walk that originated the three-way disposition, the tiebreaker rule, and the registry projection decisions).

The design record carried no drawn agent extension block; the §6.1 schema was drafted at spec-promotion time from the canonical fields the record references — `tools`/`disallowed_tools`, `model`, `mcp_servers`, `skills` (Decisions #23/#28), and `permission_mode`/`background` (named as canonical fields in the panel's deferred items). Field names are the snake_case forms of the referenced struct fields. This schema was ratified back into the design record (SHAPE.md, Agent Extension Block) at promotion time.

Preserved positions and roadmap items: agent handoff/delegation chains as a structured capability candidate (today prose-expressed; runs through the derivability test if a provider structures it); per-agent permission-policy promotion (`permission_mode` enum-of-values — needs an owned enum with total mapping if promoted); provider-specific agent surfaces (tool aliases, welcome messages, keyboard shortcuts) handled under the general passthrough rule rather than per-provider drop lists; cross-registry federation of resolution state (registry-scoped in 0.1).

Newly minted at spec-promotion time (flagged for review): the §6.2 pins that `tools` order is preserved with no set semantics, that entries are non-empty strings, and that `permission_mode`/`background` are opaque passthrough; the §8.2 clarification that `metadata_hash` covers declared (untranslated) spellings while predicates read the translated canonical form; the §11 rule that renderers never substitute resolved UUIDs into provider output; and the TV-AGENT (h)–(k) vector reshaping (the design record's "body_hash post-translation" phrasing was vacuous for a frontmatter-carried array and is restated in hash-boundary terms).

Amended after the second independent review (2026-07-11): the §8.1 entry-file statement that agents pin no canonical filename.
