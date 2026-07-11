# ACIF MCP Configuration Interchange Specification

**Version:** 0.1.0
**Status:** Draft
**Spec ID:** [ACIF-MCP]

---

## Abstract

This document defines the canonical interchange form for the MCP configuration content type: a set of Model Context Protocol server definitions that an AI coding tool launches or connects to. It specifies the canonical server model, transport-type default materialization, the MCP `body_hash` preimage, derivation predicates, render-back requirements, and the MCP error-identifier registry.

## 1. Introduction

An MCP configuration wires one or more MCP servers into a provider: for each named server, the command or URL to reach it, its transport type, environment, and tool-filtering settings. Providers carry this wiring in provider-owned configuration files with differing dialects and defaulting behavior — in particular, the transport type is frequently implicit. This document defines the provider-neutral canonical form, with transport defaults materialized so that canonical bytes, and therefore `body_hash`, are deterministic.

MCP configurations are a **sidecar-only** content type ([ACIF-CORE] §6.1): the provider owns the native configuration file, so no frontmatter surface exists. The canonical sidecar is the only carrier, and the wiring it carries participates in `body_hash` (§8).

This document constrains ACIF's carriage of MCP server wiring only; it does not define or amend the Model Context Protocol itself.

## 2. Relationship to ACIF Core

This document is a Level 1 (L1) companion to [ACIF-CORE] and depends on it normatively. Conformance to this document requires conformance to [ACIF-CORE]; every discipline in [ACIF-CORE] §8 and the capability model in [ACIF-CORE] §9 apply to MCP configurations without restatement. This document adds MCP-specific requirements only; it redefines no [ACIF-CORE] term.

This document is compatible with [ACIF-CORE] version 0.1.x. Both documents are Draft maturity; changes to [ACIF-CORE] may require corresponding changes here.

## 3. Terminology

Terms defined in [ACIF-CORE] §2 are used without redefinition. Additionally:

**server** — one named entry of the `servers` map: the wiring for a single MCP server.

**server name** — the map key naming a server; a within-item identifier (§6.2).

**transport type** — the canonical `type` field of a server: one of `{stdio, sse, streamable-http}`.

**stdio server** — a server the provider launches as a local process (`command` + `args`).

**remote server** — a server the provider connects to by URL (`sse` or `streamable-http` transport).

## 4. Requirements Language

The key words "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHALL NOT", "SHOULD", "SHOULD NOT", "RECOMMENDED", "NOT RECOMMENDED", "MAY", and "OPTIONAL" in this document are to be interpreted as described in BCP 14 [RFC2119] [RFC8174] when, and only when, they appear in all capitals, as shown here.

## 5. Conformance

This document extends the [ACIF-CORE] §4 conformance classes with MCP-specific requirements and adds one class:

**Conforming canonicalizer** — additionally satisfies §6–§8 (model validation, transport materialization, hash preimage).

**Conforming validator** — additionally satisfies the reject conditions in §6–§7 evaluated over canonical form, without re-applying defaults.

**Conforming MCP configuration record** — an item with `kind: mcp_config` conforms if it satisfies [ACIF-CORE] §5 and §6 of this document.

**Conforming install tool** — additionally satisfies the [ACIF-CORE] §9.5 refusal rule as it applies to MCP items.

**Conforming renderer** — software that emits a provider-native form from canonical form; satisfies §10.

Registry conformance is defined in [ACIF-REGISTRY]; §11 of this document states the MCP-specific compute obligations a conforming registry inherits.

The test-vector families in Appendix A are normatively authoritative: an implementation that contradicts a published vector is non-conformant regardless of any prose reading.

## 6. Canonical MCP Model

### 6.1 Schema

The MCP extension block appears below the common envelope when `kind: mcp_config`:

```yaml
mcp:
  servers:                              # REQUIRED — map: server name → wiring (§6.2)
    figma:
      type: stdio                       # REQUIRED in canonical form — materialized (§7)
      command: "npx"                    # stdio transport
      args: ["-y", "@figma/mcp-server"] # order significant (§8.3)
      env: {FIGMA_TOKEN: "${FIGMA_TOKEN}"}
      # Remote-transport fields: url, headers
      # Additional canonical fields carried 1:1: oauth (opaque), cwd,
      # includeTools, excludeTools, disabledTools, autoApprove, disabled, ...

  requires: {}                          # OPTIONAL — empty/absent in 0.1 (§9)
```

The server wiring envelope is carried one-to-one: fields beyond those this document constrains (`type`, `command`, `url`) are opaque passthrough ([ACIF-CORE] §8.5), preserved for round-trip fidelity.

### 6.2 Field requirements

**`servers`** — REQUIRED, one or more entries; an absent or empty `servers` map MUST be rejected with `acif.mcp.servers_missing`.

**Server names** — within-item identifiers, treated as opaque strings for any cross-reference resolution ([ACIF-CORE] §10; an agent's `mcp_servers` entries resolve against these names at the registry). Names SHOULD match `^[a-zA-Z][a-zA-Z0-9_-]*$`; a canonicalizer SHOULD report `acif.mcp.server_name_unconventional` (INFORMATIVE) for a non-matching name and MUST NOT reject on it. *(Informative: the MCP protocol specification is silent on configuration-level server names; this constraint fills the gap without contradicting future MCP working-group decisions, which take precedence over this recommendation if they land.)*

**`type`** — REQUIRED in canonical form on every server; §7 defines materialization. MUST be a member of the closed enum `{sse, stdio, streamable-http}`, matched by exact byte comparison ([ACIF-CORE] §8.3); any other declared value MUST be rejected with `acif.mcp.transport_type_invalid`.

**`requires`** — OPTIONAL. The recognized `requires` vocabulary for MCP configurations is empty in ACIF 0.1 (§9); any key present is non-conformant ([ACIF-CORE] §9.4).

## 7. Transport Default Materialization

The canonicalizer MUST materialize an explicit `type` on every server before `body_hash` is computed ([ACIF-CORE] §8.1), by exactly this rule:

| Input state | Canonicalizer action |
|---|---|
| `type` present | Use as-is (after §6.2 validation) |
| `type` absent, `command` present, `url` absent | Materialize `type: stdio` |
| `type` absent, `url` present, `command` absent | Materialize `type: streamable-http` |
| `type` absent, both `command` and `url` present | MUST reject `acif.mcp.transport_default_ambiguous` |
| `type` absent, neither present | MUST reject `acif.mcp.transport_default_undetermined` |

Validators consume the post-default canonical form and MUST NOT re-apply defaults. Where the default cannot be determined unambiguously, canonicalization rejects — never guesses ([ACIF-CORE] §8.1).

*(Informative)* This is the original materialize-then-hash rule of the document set — one rule, one place — later paralleled by skill and rule activation defaults. Without it, two consumers applying different default logic to the same source produce different canonical bytes and divergent `body_hash` values.

## 8. The MCP `body_hash` Preimage

MCP configurations are sidecar-only, so [ACIF-CORE] §7.7 and §7.8 apply: the extension block is wiring, its hash home is `body_hash`, and this section pins the exact construction, parallel to [ACIF-HOOK] §9.

### 8.1 Inputs

All inputs are taken from the post-canonicalization form: after §7 materialization and §6.2 validation.

### 8.2 File manifest

The referenced-file set of an MCP configuration is **empty** in ACIF 0.1: no canonical MCP field names a bundled file (command paths, `cwd`, and environment-file references address the consuming machine, not the published body). Let `DH` be the string `sha256:` followed by the lowercase hex SHA-256 of the empty byte string. *(Informative: the manifest slot is retained, at constant value, so the sidecar-only preimage shape is identical across content types and a future field that does bundle files extends rather than reshapes the preimage.)*

### 8.3 Wiring serialization

Let `W` be the canonical JSON serialization ([ACIF-CORE] §8.6, RFC 8785) of the complete canonical `mcp` extension-block object with absent fields omitted. There is no field-level selection: every canonical and passthrough field of every server enters `W`.

Array ordering in `W` ([ACIF-CORE] §8.6):

- `args` — order significant, preserved (command-line argument order is semantics).
- `includeTools`, `excludeTools`, `disabledTools`, `autoApprove` (and any other tool-filter list) — sets, not sequences: in canonical form their elements MUST be sorted by raw UTF-8 byte order and MUST NOT contain duplicates.
- Any other passthrough array — order preserved (provider-owned semantics are opaque; reordering opaque content is not safe).

Server map keys and object members are ordered by RFC 8785 itself.

### 8.4 Preimage and value

```
preimage        = UTF8(DH) || 0x0A || W || 0x0A
body_hash.value = lowercase-hex( SHA-256(preimage) )
body_hash.algorithm = sha256
```

Consequences (normative in effect, stated for clarity): flipping a transport type, editing `command` or `args`, changing an `env` value or `url`, and toggling any tool-filter entry each move `body_hash`; a source with explicit `type: stdio` and a source with `type` absent plus `command` canonicalize to identical bytes and identical `body_hash`. Envelope metadata declared in a publisher-authored sidecar rides `metadata_hash` over an envelope-only `publisher_section` ([ACIF-CORE] §7.8), never `body_hash`.

## 9. Capability Dispositions and Derivation Predicates

The recognized `requires` vocabulary for MCP configurations is **empty** in ACIF 0.1. Every capability key of the MCP vocabulary is disposed per [ACIF-CORE] §9.2 as follows.

### 9.1 DERIVABLE keys

| Key | D_K over canonical body B (post-materialization, §7) |
|---|---|
| `transport_types` | `∃ s ∈ B.servers . s.type != ""` — constant derivable-true on a conforming record (`type` is REQUIRED in canonical form); the predicate exists as a disposition, not a signal. The set of distinct transport types observed is a registry projection (§11.1), not the predicate output. |
| `oauth_support` | `∃ s ∈ B.servers . s.oauth present` |
| `env_var_expansion` | `∃` an occurrence of the `${VAR}` token syntax in a value of the closed field set `{command, args[i], env.<key>, url, headers.<key>}` of any server — exactly these fields; opaque passthrough values are excluded from the scan domain |
| `tool_filtering` | `∃ s ∈ B.servers . (s.includeTools present ∨ s.excludeTools present ∨ s.disabledTools present)` |
| `auto_approve` | `∃ s ∈ B.servers . s.autoApprove present` |

Each predicate produces `{derivable-true, derivable-false}` per the boolean discipline. *(Informative)* The `env_var_expansion` predicate scans field **values**, but its domain is the pinned closed field set above — canonical wiring fields validated at canonicalization, with an exact token grammar — a derivation over structured wiring, not the prose-scan heuristic the derivation-vs-heuristic rule ([ACIF-CORE] §9.2) bars. The distinction is domain structure, not scan mechanics; the same rule bars the command placeholder scan, whose domain is unstructured body prose ([ACIF-COMMAND] §9.1).

### 9.2 OUT-OF-SCOPE-AT-L1 keys *(informative rationale)*

`marketplace` is registry-inference territory (aggregators observe the canonical block and project their own listings; the publisher is the wrong source of truth for cross-marketplace identity). `enterprise_management` is organization-policy surface, outside the publish pipeline. `resource_referencing` is provider UX. Under the out-of-band guardrail ([ACIF-CORE] §9.3) none is `requires`-eligible; none is author-declared.

Roadmap candidates recorded: `env_file_reference` and `path_variable_expansion` are wiring-observable today (an `envFile` field; literal `${userHome}`-style tokens in wiring values) and become `requires` candidates only if a future provider moves the capability out of the wiring.

### 9.3 Rejected sub-blocks *(informative)*

Three optional sub-blocks were considered for this extension block and cut: `marketplace_listings` (ownership inversion — aggregator-pulls, never publisher-pushes), `enterprise` (no honest equilibrium for a self-asserted managed-default flag; free-text notes unmoderable at registry scale), and `advisory` (a works-fine-without-it silent-failure shape). Their absence is a design decision, not a gap.

### 9.4 Orphan keys

Any `requires.<key>` on an MCP item — including every key named in §9.1 and §9.2 — is non-conformant ([ACIF-CORE] §9.4); `requires.transport_types` on a **non**-MCP item rejects identically under per-type scoping. An unrecognized key evaluated by a consumer follows the three-valued rule ([ACIF-CORE] §9.5).

## 10. Render-Back Requirements

These requirements bind conforming renderers; the general render-back framework is [ACIF-RENDER].

- Renderers MAY strip the explicit `type` for target formats that do not surface it; the strip is safe because re-canonicalization re-applies the single §7 default rule and reproduces identical canonical bytes. This strip-and-restore round-trip MUST be deterministic.
- All passthrough values — `env` values, `headers`, `oauth` contents, provider-owned fields — MUST be re-serialized through the target format's structured encoder ([ACIF-CORE] §8.5); string-splicing is non-conformant.
- Tool-filter arrays render in canonical (sorted) order; no obligation exists to restore a source ordering.

## 11. Registry Projections

The projections in this section are computed by registries over the canonical body ([ACIF-REGISTRY] defines the response surface).

### 11.1 `derived_capabilities`

A conforming registry MUST compute the five §9.1 predicates for every MCP item at ingest, with the set of distinct transport types observed carried alongside the `transport_types` boolean as a set-valued projection.

### 11.2 Moderation signals *(informative)*

The highest-value scan surfaces for MCP items are structural, not prose: `stdio` servers name a command the provider executes; `autoApprove` lists pre-authorize tool calls. Registries should treat the §11.1 projections as the moderation pre-filter they are.

## 12. Error Identifiers

| Identifier | Class | Condition |
|---|---|---|
| `acif.mcp.servers_missing` | reject | `servers` absent or empty (§6.2) |
| `acif.mcp.transport_type_invalid` | reject | Declared `type` outside the closed enum, or inexact byte form (§6.2) |
| `acif.mcp.transport_default_ambiguous` | reject | `type` absent with both `command` and `url` present (§7) |
| `acif.mcp.transport_default_undetermined` | reject | `type` absent with neither `command` nor `url` present (§7) |
| `acif.mcp.server_name_unconventional` | diagnostic (INFORMATIVE) | Server name outside the SHOULD pattern (§6.2) |

Reject-class identifiers make canonicalization fail; the INFORMATIVE diagnostic never gates ([ACIF-CORE] §8.7). All reject diagnostics for authoring errors are fix-forward.

## 13. Security Considerations

**stdio wiring is an execution grant.** A `stdio` server's `command`/`args` is a program the provider launches, typically at session start with no per-run user gesture — operationally the most privileged wiring in this document set. `body_hash` binds the command line and environment (§8.4), so swapping a command after review fires the change signal; nothing, however, verifies what the command does. Package-manager invocations (`npx`-style) add a supply-chain hop the hash cannot see: the wiring is bound, the fetched package is not.

**Environment blocks reference credentials.** `env` values conventionally carry `${VAR}` expansions rather than literal secrets; a literal credential in a published `env` block is publicly exposed by publication. Registries should treat literal-looking secrets in wiring as a moderation and disclosure event. The `env_var_expansion` projection identifies expansion-dependent items; expansion semantics are provider-owned.

**`autoApprove` launders consent.** A pre-approved tool list bypasses the provider's per-call permission prompts — a published config can arrive with consent already granted for the server's most dangerous tools. The `auto_approve` projection exists so installers and policies can gate on it; installing an `autoApprove`-bearing config deserves the same scrutiny as granting the permissions by hand.

**Remote servers move data.** `sse`/`streamable-http` wiring points the provider's context at an external endpoint; `headers` can carry bearer tokens. Endpoint trust is out of ACIF's scope; the canonical form makes the endpoint legible for policy.

**Server-name squatting.** Agents resolve `mcp_servers` references by these names ([ACIF-AGENT] §10.2); a config publishing a well-known name is the resolution-layer typosquatting shape. Resolution policy is registry-scoped.

**Metadata is self-asserted.** Everything in [ACIF-CORE] §11 applies.

## 14. References

### 14.1 Normative

- [ACIF-CORE] "ACIF Core Specification", version 0.1.x. `../core/spec.md`
- [RFC2119] Bradner, S., "Key words for use in RFCs to Indicate Requirement Levels", BCP 14, RFC 2119, March 1997. <https://www.rfc-editor.org/rfc/rfc2119>
- [RFC8174] Leiba, B., "Ambiguity of Uppercase vs Lowercase in RFC 2119 Key Words", BCP 14, RFC 8174, May 2017. <https://www.rfc-editor.org/rfc/rfc8174>
- [RFC8785] Rundgren, A., Jordan, B., Erdtman, S., "JSON Canonicalization Scheme (JCS)", RFC 8785, June 2020. <https://www.rfc-editor.org/rfc/rfc8785>

### 14.2 Informative

- [MCP] Model Context Protocol specification, revision 2025-06-18. <https://modelcontextprotocol.io/specification/2025-06-18> — the protocol whose server wiring this document carries; silent on configuration-level server names as of that revision.
- [ACIF-HOOK] "ACIF Hook Interchange Specification", version 0.1.x. `../hooks-interchange/spec.md` — the sibling sidecar-only preimage instantiation.
- [ACIF-AGENT] "ACIF Agent Interchange Specification", version 0.1.x. `../agent-interchange/spec.md` — the name-declared reference consumer.
- [ACIF-PUBLISHER] "ACIF Publisher Record Specification", version 0.1.x. `../publisher-spec/spec.md`.
- [ACIF-REGISTRY] "ACIF Registry Specification", version 0.1.x. `../registry-spec/spec.md`.
- [ACIF-RENDER] "ACIF Render-Back Specification", version 0.1.x. `../render-back/spec.md`.
- [SHAPE] ACIF design record: `SHAPE.md` and `panel/mcp-requires-consensus.md` in the ACIF repository — decision provenance (Decisions #23, #24).

---

## Appendix A — Conformance Test-Vector Families (Normative)

The vectors in these families, published in the `conformance/` directory, are normatively authoritative over prose. Family definition:

**TV-MCP-\***: (a) default materialization — `type` absent + `command` → canonical `type: stdio`; `type` absent + `url` → canonical `type: streamable-http`; `body_hash` matches the published reference; (b) ambiguous reject — `type` absent + both `command` and `url` → `acif.mcp.transport_default_ambiguous`; (c) undetermined reject — neither → `acif.mcp.transport_default_undetermined`; (d) `body_hash` stability — explicit `type: stdio` and absent-`type`-with-`command` produce identical canonical bytes and identical `body_hash`; (e) empty `requires` conformant; (f) unknown-key three-valued evaluation; (g) orphan-key reject — `requires.transport_types` on an `mcp_config` item (DERIVABLE key) and on a `skill` item (foreign-type key) both reject; (h) invalid transport — `type: websocket` and `type: Stdio` (case variant) → `acif.mcp.transport_type_invalid`; (i) empty servers — absent and `{}` → `acif.mcp.servers_missing`; (j) `D_K` battery — oauth_support, env_var_expansion (`${FIGMA_TOKEN}` in `env` → true; no token anywhere → false), tool_filtering, auto_approve, each true/false; (k) wiring-hash coverage — editing one `args` element, flipping one `env` value, and re-pointing `url` each move `body_hash`; (k′) determinism — two sources differing only in tool-filter array order or server-key order yield byte-identical canonical form and identical `body_hash` (§8.3); (l) strip-and-restore — render to a no-`type` target format, re-canonicalize → identical canonical bytes and `body_hash`; (m) server-name diagnostic — name `9figma` → `acif.mcp.server_name_unconventional` (INFORMATIVE), item accepted.

Individual vector IDs are assigned in the conformance suite.

## Appendix B — Provenance and Preserved Positions (Informative)

Promoted 2026-07-11 from the ACIF design record: the MCP extension block and Decisions #23 (MCP application) and #24 of `SHAPE.md`, with the full deliberation record in `panel/mcp-requires-consensus.md` (the first capability walk; unanimous; origin of the derivability principle and the named-error-code discipline).

Preserved positions and roadmap items: `env_file_reference` and `path_variable_expansion` as future `requires` candidates if the capability ever leaves the wiring; the marketplace identity model and enterprise/org-policy surface, both cut from the publisher schema with the ownership rationale recorded (§9.3); MCP working-group precedence over the server-name recommendation (§6.2).

Newly minted at spec-promotion time (not present in the design record; flagged for review): the error identifiers `acif.mcp.servers_missing`, `acif.mcp.transport_type_invalid`, and `acif.mcp.server_name_unconventional` (the design record carried only the two Decision #24 codes); the §8 preimage pinning (the design record's Decision #33 amendment established that sidecar-only preimages cover the whole extension block but pinned the exact serialization only for hooks; this document instantiates it for MCP, including the empty-manifest constant and the §8.3 array-ordering pins required by [ACIF-CORE] §8.6); and the §9.1/§9.2 restatement of the design record's "all eight keys DERIVABLE" summary sentence as 5 DERIVABLE / 3 OUT-OF-SCOPE-AT-L1 — the consensus document's own per-key table classifies `marketplace`, `enterprise_management`, and `resource_referencing` as out-of-band concerns, and this document applies the mature three-way vocabulary to that substance (the `requires` result is unchanged: empty). These items were ratified back into the design record (SHAPE.md, Spec-Promotion Ratifications section) at promotion time.
