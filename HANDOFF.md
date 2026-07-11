# HANDOFF — Finish ACIF v0.1

> Written 2026-07-10 from a capmon planning session; refreshed 2026-07-10 after
> the OQ-7 close. Read this first, then SHAPE.md. Delete this file when the
> plan below is absorbed into normal working docs.

## Why ACIF is now the priority

Decision made in the capmon session (2026-07-10): **ACIF is the authority; capmon
consumes ACIF.** capmon (extracted from syllago, being inverted into a standalone
capability registry at `~/.local/src/capmon`) will publish per-provider capability
data that *conforms to* ACIF's canonical vocabularies. The canonical keys can only
evolve through ACIF spec changes. capmon's publish contract reserves a `spec_ref`
field per canonical key, to be filled as each L1 spec lands. Finishing ACIF
therefore unblocks capmon's consumer contract — ACIF first, capmon Phase 4 after.

## Current state (verified 2026-07-10, post-OQ-7 close)

- SHAPE.md carries **31 decisions**, all six extension blocks, and the
  registry-section schema. Working tree clean at `c7e3398`.
- **Steps 0–2 below are DONE.** All six vocabulary walks are panel-resolved,
  folded into SHAPE.md, and committed: MCP, agents, hooks, skills, rules
  (first 2:2 split — Decision #30, out-of-band guardrail), and commands
  (3:1 — Decision #31, derivation-vs-heuristic refinement, three-way routing).
  **OQ-7 is CLOSED six-for-six, validated** — `requires` is empty/absent for
  v0.1 on every content type.
- Panel records: `panel/{mcp,agents,hooks,skills,rules,commands}-requires-consensus.md`.
  The rules and commands docs carry the standing tests governing all future
  capability questions: the **out-of-band eligibility guardrail**, the
  **derivation-vs-heuristic refinement**, and the **three-way routing**
  (body → derivable/opaque; provider → matrix; user-environment → requires).

## The plan

### Steps 0–2 — DONE (2026-07-10)

Working tree committed; skills consensus folded into SHAPE.md (Decision #19/#21
amendments); rules and commands walks run and cascaded (Decisions #30, #31).
See the panel consensus docs and SHAPE.md's OQ-7 row for the full record.

### Queued design items (before or alongside Step 3)

- **OQ-11 — `source_uri` normative tightening** (filed 2026-07-10). Substance:
  RFC 3986, https-only, post-redirect, percent-encoding per §6.2.2, fragment
  stripped, last-path-segment normative for direct file URLs. Must land before
  TV-11+ vectors (Step 6 dependency). Likely shape: targeted mini-review
  (spec-purist ± registry-operator), not a full panel.
- **`platform_commands` batched panel** (queued since May). Reviewer set:
  registry-operator + spec-purist + valsorda + enterprise-security. Gather
  context first: grep capmon + provider-capabilities for what platform_commands
  means post-extraction (it was a HIF-era question).

### Step 3 — Close the open questions

- OQ-6: `os`/`arch` absence semantics ("all" vs "unspecified").
- OQ-8: body-content derivation generally (extended twice — now spans @-refs,
  placeholder tokens, injection directives; structured-record bar recorded;
  the never-parse branch MUST re-hear spec-purist's preserved rules dissent).
- OQ-9: two-tier freshness precedence (sidecar `expires` vs external attestation).
- OQ-10: latent-field promotion (SkillMeta + CommandMeta; uniformity constraint).
- OQ-11: source_uri tightening (above).
- Pin the literal `ACIF_PACK_NAMESPACE` UUIDv5 constant (registry-operator's
  OP-COND-1: non-negotiable before v0.1 publication).

Definition of done requires "no open OQ without an owner" — OQs may close for
v0.1 or be explicitly roadmap-deferred with owners; both satisfy it.

### Step 4 — Vocabulary repatriation (syllago → ACIF)

Decisions #25 and #29 pin canonical vocabularies by *frozen-snapshot reference to
syllago source paths* (`cli/internal/converter/toolmap.go`, `hooks.go`). Under
the new authority direction this is backwards, and those paths are going stale
(capmon extraction). Inline the pinned vocabularies into ACIF spec text as owned
normative appendices: canonical tool names, hook event vocabulary (~30 names),
handler-type enum. Syllago/capmon then conform to ACIF's copy, not vice versa.
Decisions #30 and #31 (ACIF-originated vocabularies) already established the
owned-vocab pattern to migrate to.

### Step 5 — Promote SHAPE.md into the actual specs

SHAPE.md self-describes as "not a spec — a snapshot. Promote to individual spec
files once stable." After Steps 3–4 it is stable. Ship order:
1. `specs/hooks-interchange/` — the designated exemplar, currently empty.
   Source material: SHAPE hook block + Decision #29 vocab + capmon's
   canonical-keys/provider-formats data (now at `~/.local/src/capmon` post-inversion).
2. Finish `specs/skill-interchange/spec.md` (draft exists, predates the skills walk).
3. Remaining L1 specs: rule, command, agent, mcp — from their walk consensus docs.
4. `publisher-spec/` (L2) and `registry-spec/` (L3) — the SHAPE envelope, carrier
   rules, two-section record, and registry-section schema are these specs in
   embryo; largely an extraction-and-normative-tightening job.
5. `render-back/` (L4) — spec the deterministic canonical→provider emit. Its
   provider-support decisions consume capmon's capability matrix.

### Step 6 — Conformance suite

`conformance/` directory with the full TV catalog (TV-1..10, TV-MCP-*,
TV-AGENT-*, TV-HOOK-*, TV-SKILL-*, TV-RULE-*, TV-COMMAND-*). Appendix B is
explicit: the vectors are normatively authoritative; reference scripts are
informative. Reference impls for `body_hash` already exist in
`../moat/reference/`. TV-11+ vectors are gated on OQ-11.

## Definition of done (v0.1)

Six L1 specs + L2 + L3 + L4 published; all six content-type walks recorded in
SHAPE decisions; no open OQ without an owner; namespace UUID pinned; conformance
vectors published; no normative reference to syllago/capmon internals (they
conform to ACIF, not the reverse).

## Pointers

- Panel records: `panel/*-consensus.md` (all six walks folded into SHAPE.md)
- Deferred scope: ROADMAP.md (do not let deferred items creep into v0.1)
- capmon relationship: capmon publishes provider capability *facts* conforming to
  ACIF vocabularies; the caniuse-to-MDN analogy. Its inversion plan lives in the
  capmon session/repo and does not block ACIF work.
