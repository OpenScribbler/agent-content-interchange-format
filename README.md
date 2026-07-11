# ACIF — Agent Content Interchange Format

A set of layered specifications for describing, distributing, and rendering AI
agent content — hooks, skills, rules, commands, sub-agents, and MCP
configurations — across the AI coding tool ecosystem.

**Status: ACIF 0.1 (Draft) — the full specification set and conformance suite
are published in this repository.**

## Why this exists

AI agent content is published in provider-native formats. A "hook" for one
tool, the same hook for a second tool, and the same hook for a third are three
different files even when they invoke identical behavior. There is no
provider-neutral way to:

1. **Describe** what an agent content item *is* — its canonical form, identity, and change signal
2. **Distribute** it through a registry that doesn't care which provider it targets
3. **Render** it back into one or more provider-native shells

ACIF pulls those concerns apart into layered specs that can be adopted
incrementally.

## Not a vendor plugin or marketplace system

ACIF is **not** a plugin format, a marketplace schema, or a distribution
mechanism for any single provider. It is a direct, open-source,
provider-agnostic alternative to those systems.

Vendor plugin and marketplace systems tie content authors to one vendor's
distribution path: that vendor's roadmap, discovery surface, installation
flow, and terms. ACIF treats those systems as the status quo it competes with,
not as authoritative inputs to its design:

- ACIF's carrier model, hashing, and discovery rules are designed around the **content itself** — the `SKILL.md` directory, the rule file, the MCP wiring — not around any vendor's plugin manifest.
- Vendor plugin and marketplace manifests are not authoritative in ACIF's content-source model. Where a plugin manifest appears in the pack-inference precedence chain ([ACIF-PUBLISHER] §9.1) it contributes a *name*, nothing more.
- The "publish once, render to N tools" model deliberately routes around distribution lock-in: publishers describe content in a neutral format; registries serve it without vendor approval; render-back emits provider-native files for whichever tools the consumer actually uses.

The six content types — **hook, skill, rule, command, agent, mcp_config** —
are co-equal and are the units that should be portable.

## The specification set

| Layer | Spec | Defines |
|---|---|---|
| Core | [`specs/core/`](specs/core/spec.md) — **[ACIF-CORE]** | Common envelope, carrier model, identity + `body_hash` change signal, canonicalization disciplines, capability (`requires`) model, canonical tool vocabulary |
| L1 | [`specs/hooks-interchange/`](specs/hooks-interchange/spec.md) — **[ACIF-HOOK]** | Canonical hook model, event vocabulary (39 events), per-OS script selection, sidecar-only hash preimage |
| L1 | [`specs/skill-interchange/`](specs/skill-interchange/spec.md) — **[ACIF-SKILL]** | Activation model + materialization, body classification, discovery tiers |
| L1 | [`specs/rule-interchange/`](specs/rule-interchange/spec.md) — **[ACIF-RULE]** | Activation-mode vocabulary (first ACIF-owned enum), glob consistency, prose opacity |
| L1 | [`specs/command-interchange/`](specs/command-interchange/spec.md) — **[ACIF-COMMAND]** | Argument-placeholder vocabulary + rewrite, passthrough frontmatter surface |
| L1 | [`specs/agent-interchange/`](specs/agent-interchange/spec.md) — **[ACIF-AGENT]** | Agent envelope (tools/model/MCP/skills), tool-name canonicalization, name-declared references |
| L1 | [`specs/mcp-interchange/`](specs/mcp-interchange/spec.md) — **[ACIF-MCP]** | Transport-default materialization, MCP wiring hash preimage |
| L2 | [`specs/publisher-spec/`](specs/publisher-spec/spec.md) — **[ACIF-PUBLISHER]** | Two-section published record, `publisher_section` + `metadata_hash`, frontmatter reconciliation, pack model + inference algorithm |
| L3 | [`specs/registry-spec/`](specs/registry-spec/spec.md) — **[ACIF-REGISTRY]** | `registry_section` schema, change-signal surfaces, projections, `source_uri` pipeline, freshness model |
| L4 | [`specs/render-back/`](specs/render-back/spec.md) — **[ACIF-RENDER]** | Deterministic render function, fidelity classes, degradation diagnostics, round-trip bounds |

Each layer is independently adoptable; every document declares its
dependencies and conformance classes explicitly.

## Conformance suite

[`conformance/`](conformance/README.md) publishes the test-vector catalog —
150 vectors across 11 families. **The vectors are normatively authoritative
over prose**: an implementation that contradicts a published vector is
non-conformant regardless of any prose reading. Reference implementations
under `conformance/reference/` are informative.

## Design principles (short form)

- **`body_hash` is the change signal.** Content identity and change detection ride a pinned content-hash algorithm, not version strings. Version is advisory; hashes are dispositive.
- **Canonicalize, then hash.** Provider dialects converge on canonical bytes — vocabularies translated, defaults materialized, one rule in one place — so two implementations can never disagree about what changed.
- **Structure is the provenance.** Publisher-declared and registry-computed data live in different record sections; there are no per-field trust markers to forge or forget.
- **Capabilities are derived, not declared.** Every walked capability is either derivable from canonical structure or out of scope; the `requires` slot is empty across all six types in 0.1, reserved for genuinely out-of-band environmental pins.
- **Degradation is loud.** Rendering to a less-capable provider is allowed, but every semantic loss carries a named, machine-readable diagnostic.

## Relationship to other projects

- **MOAT** — the informative provenance of the `body_hash` algorithm ([ACIF-CORE] §7 restates it as ACIF-owned normative text) and one candidate filler of the registry-layer attestation slot. ACIF names no external integrity system normatively; the slot is deliberately agnostic.
- **capmon** — a provider capability matrix that publishes per-provider facts *conforming to* ACIF's canonical vocabularies (the caniuse-to-MDN analogy). Authority direction: ACIF owns the vocabularies; capmon and the syllago converter conform to ACIF's copies, not the reverse.

## Design record

`SHAPE.md` is the historical design record — 34 decisions, the open-question
ledger, and the spec-promotion ratifications — with full panel deliberations
under `panel/`. Where the record and a spec disagree, the spec governs.
Deferred work lives in `ROADMAP.md` (roadmap items, not version commitments).

## Layout

```
specs/
  core/                  # [ACIF-CORE]
  hooks-interchange/     # [ACIF-HOOK]      (L1)
  skill-interchange/     # [ACIF-SKILL]     (L1)
  rule-interchange/      # [ACIF-RULE]      (L1)
  command-interchange/   # [ACIF-COMMAND]   (L1)
  agent-interchange/     # [ACIF-AGENT]     (L1)
  mcp-interchange/       # [ACIF-MCP]       (L1)
  publisher-spec/        # [ACIF-PUBLISHER] (L2)
  registry-spec/         # [ACIF-REGISTRY]  (L3)
  render-back/           # [ACIF-RENDER]    (L4)
conformance/             # normative test vectors + informative reference impls
SHAPE.md                 # historical design record (Decisions #1–#34)
panel/                   # panel consensus records behind the decisions
ROADMAP.md               # deferred scope
examples/                # end-to-end traces over real-world content
```
