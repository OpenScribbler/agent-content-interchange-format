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

- **OQ-11 — `source_uri` normative tightening — DONE** (resolved 2026-07-10,
  same day it was filed): Decision #32 via the project's first two-reviewer
  mini-review (spec-purist + registry-operator). Post-redirect final-URL
  recording was rejected on scale evidence; TV-11+ is unblocked. See
  `panel/source-uri-consensus.md`.
- **`platform_commands` batched panel — DONE** (run 2026-07-10, resolved
  2026-07-11): Decision #33 (per-OS script selection + canonicalization, third
  ACIF-owned vocabulary), Decisions #6/#19 amended (closed OS enum; hook wiring
  folded into the body_hash preimage — the panel's ship-blocker find), OQ-6
  resolved (absent = all). provider_capability_coverage row deferred, gated on
  capmon data. See `panel/platform-commands-consensus.md`.

### Step 3 — Close the open questions — DONE (2026-07-11)

**No open OQ without an owner: satisfied.** OQ-1..7, 9, 11 resolved; OQ-6
resolved via Decision #33; OQ-8 and OQ-10 are owned ROADMAP.md deferrals;
namespace pinned. The definition-of-done clause for OQs is fully met.

- OQ-6: DONE — resolved by Decision #33 (absent = all; platform_commands panel).
- OQ-8: DONE for v0.1 — never-parse adopted as the v0.1 answer; the grammar
  question is an owned ROADMAP.md deferral ("Body-content reference grammar")
  carrying the structured-record bar, the OP-COND-RULES-4/-5 lints, and the
  binding never-parse dissent re-hearing obligation.
- OQ-9: DONE — Decision #34 (orthogonal freshness axes; the min() strawman
  rejected from both directions; zero new fields; first resolution adopted
  under Holden's standing delegation). See `panel/freshness-consensus.md`.
- OQ-10: DONE — owned ROADMAP.md deferral ("Latent-field promotion") carrying
  the uniformity constraint and all recorded promotion obligations.
- `ACIF_PACK_NAMESPACE`: PINNED — `93516344-00e5-419b-a230-6e8b1d02f87d`
  (Appendix A.4); TV-3 reference UUID computed and recorded. OP-COND-1 closed.

Definition of done requires "no open OQ without an owner" — OQs may close for
v0.1 or be explicitly roadmap-deferred with owners; both satisfy it.

### Step 4 — Vocabulary repatriation (syllago → ACIF) — DONE (2026-07-11)

**Appendix C** (SHAPE.md) now carries the ACIF-owned canonical vocabularies:
C.1 tool names (17 — full per-provider mapping, reverse-translation
tiebreakers, matcher discipline, MCP tool-name formats), C.2 hook events
(exactly 39, not the estimated ~30), C.3 handler-type enum with the
absent-type→command legacy residual. Decisions #25/#29 amended — authority
direction inverted; syllago/capmon conform to ACIF's copy. Transcription
verified mechanically against syllago @ cf047f52 (byte-exact, both tables).
Remaining syllago/capmon mentions in SHAPE.md are informative provenance
only — the no-normative-reference clause of the definition of done is met.

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
`../moat/reference/`. The TV-11+ slot is occupied by TV-URI-* (Decision #32);
its OQ-11 gate is resolved.

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
