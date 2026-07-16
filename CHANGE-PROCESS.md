# ACIF Change Process

ACIF is a published format with a conformance suite and downstream
consumers (capmon's `canonical-keys.yaml` explicitly defers
post-publication key changes to "ACIF's change process" — this document
is that process). It defines the change classes, who initiates each, what
each requires, and what a change does to the vector suite and to standing
conformance reports.

This document is process, not specification: where it states constraints
on canonical bytes or vectors, those constraints restate obligations the
specs and [conformance/runner/DESIGN.md](conformance/runner/DESIGN.md)
already carry.

## Change classes

### Class A — coverage facts (no ACIF change)

An observation about which provider supports what: a provider adds
frontmatter support, drops an event, changes a default. These are
provider-matrix facts. They live in capmon's capability matrix and
surface through registry projections (`provider_capability_coverage`);
they never touch an ACIF spec, appendix, or vector. The vast majority of
provider changes are Class A.

### Class B — mapping-table rows (mechanical amendment)

A new provider, or a new provider sub-mode, that maps to an **existing**
canonical value: one row in a normative mapping appendix (e.g. the rule
activation-mode table, [ACIF-RULE] Appendix A.2; the hook event and
platform tables, [ACIF-HOOK] appendices). The runtime symptom of a
missing row is a totality-net diagnostic (`*_unmappable` — e.g.
`acif.rule.activation_mode_unmappable`, `acif.hook.platform_unmappable`)
firing on real content.

**The classification test.** A Class B row **never moves existing
canonical bytes**. The classification is decided by one observation, not
a counterfactual: run the current canonicalizer on the exact source form
the proposed row targets.

- If it **rejects with the totality-net diagnostic** for that appendix,
  the form has no canonical image today; the row extends the recognized
  domain, and no already-canonical record's hash can change. This is
  Class B.
- If it **canonicalizes cleanly**, the form is already mapped; a row
  that changes its result moves that input's bytes. That is Class C
  wearing a disguise, and gets Class C treatment.
- If it **rejects with any other diagnostic** (e.g. `*_invalid` — a bad
  enum *value* rather than an unmapped *mechanism*), resolving it
  requires new vocabulary, not a mapping row. That is Class C.

**Cadence.** Class B rows land **batched** — accumulate filed rows and
land them as one amendment commit citing the `acif-change` issues they
close. Batching is a review-overhead convenience, not a correctness
gate: the guarantees (never-move-bytes, totality-net evidence) hold per
row, so any single row MAY land as a batch of one. A batch lands on
cadence **or** when any open row's diagnostic exceeds a firing
volume/duration threshold, whichever comes first — a hot row is never
starved by a quiet batch. Ordering within a batch needs no rule: rows
are additive and order-independent. The open window is
degraded-but-safe, not an outage — the totality net catches the
unmapped form as a diagnostic with a defined fallback; what the window
degrades is canonicalization completeness, never availability.

No reviewer subset is required for Class B; the review is the
totality-net evidence (the diagnostic fired on real provider content)
plus the classification test above.

Each row SHOULD land with an additive conformance vector exercising the
new source form through the mapping (suite growth rules below). A row
without a vector is legal but unpinned — prose the suite cannot yet
contradict, and invisible to report-currency comparison until its
vector lands.

### Class C — vocabulary changes (full design treatment)

A new canonical concept: a new enum member, a new canonical key, a new
field, a new diagnostic identifier. The graduation trigger is **2+
provider evidence** — the concept exists natively in at least two
providers' formats (a single-provider concept stays in
`provider_extensions` passthrough).

Class C follows the mint discipline in full. The ACIF maintainer — not
the filer — convenes the response:

1. A SHAPE.md decision row (numbered, with rationale and rejected
   alternatives) — identifiers and vocabulary are never invented ad hoc.
2. A targeted reviewer subset (3–4 reviewers chosen for the question) or
   full panel, per the question's weight.
3. Spec edits in the owning document, normative appendix updates, and
   the vector/binding/selftest work the decision names.
4. An explicit **vector-impact inventory** (below).

### Suite-defect repairs (`repair`)

A repair corrects a published vector or binding whose expectation was
unachievable by any conforming implementation — the suite disagreed with
the specs it tests. Repairs are neither Class B (they change existing
vector or binding content, not add rows) nor Class C (they mint no
vocabulary; the corrected expectation is what the specs already
required). The evidence standard is a demonstration that a conforming
implementation fails the vector as published, normally a failing run
plus the spec-clause derivation of the correct expectation.

A repair's manifest entry uses `change_class: repair` and its note MUST
name the repaired vectors. Because a repair changes what existing
vectors assert, consumers of superseded reports SHOULD treat a repair
entry like a Class C entry for the catalogs it touches: claims about
the repaired vectors were claims against defective expectations, so
re-verification of the affected scope is warranted.

## Suite and report impact

The conformance suite (165 vectors at this writing) is normatively
authoritative over prose, and conformance reports pin the exact catalog
content hashes and binding-set hash they ran against. Those facts drive
the impact rules:

- **Class B is additive-only.** New vectors may land; existing vectors'
  ids, inputs, and expectations are untouched. Implementations see new
  vectors appear on their next run; nothing they previously passed
  changes meaning. A report superseded only by Class B changes is
  subset-valid: everything it claims passed still passes.
- **Class C must inventory expectation flips.** A vocabulary change can
  flip existing vectors' expectations — the canonical example: a vector
  asserting that a string rejects against a closed enum breaks the day
  that string joins the enum. The decision row MUST enumerate every
  existing vector whose expectation the change touches; those amendments
  are part of the change, not collateral discovered later. A Class C
  with an empty inventory says so explicitly. This obligation is
  enforced at review time, not by tooling: any vector whose `expect`
  block changes in the landing commit but is absent from the cited
  inventory blocks the merge. (A future runner self-check MAY mechanize
  this; until then the check is the reviewer's.)
- **Standing reports stay valid; they may stop being current.** A report
  is a permanent claim about the catalog and binding-set hashes it pins.
  A suite change never invalidates it retroactively — it supersedes it.
  Supersession is **scoped to the catalogs whose hash moved**: a report
  is stale only with respect to pinned catalogs the manifest shows
  changed; a Class B batch that grows only `rule.yaml` leaves a
  hook-only report fully current.
- **The suite manifest makes currency computable.**
  [conformance/suite-manifest.yaml](conformance/suite-manifest.yaml) is
  the published, monotonic artifact consumers compare a report's pinned
  hashes against: one entry per suite change, carrying the suite
  sequence number, per-catalog content hashes, binding-set hash, the
  change class of the bump, and a supersession link. The distinction it
  enables is the operational one: a report superseded across
  **Class B-only** entries is safe to accept with a staleness note; a
  report superseded across a **Class C** entry whose inventory touches a
  catalog the report pins needs re-verification. The runner selftest
  fails if the manifest head drifts from the working tree, so a suite
  change cannot land without its manifest entry. Consumers of
  conformance claims (registries, graduation evaluations) SHOULD require
  claims against the current manifest head and MAY accept superseded
  claims with the gap visible; ACIF does not enforce this on consumers.

## Signal path (inbound)

capmon monitors provider behavior continuously; ACIF-relevant findings
route here as GitHub issues labeled `acif-change`, filed automatically
on either trigger:

- a totality-net diagnostic firing on real provider content (missing
  Class B row), or
- a `provider_extensions` concept crossing the 2+ provider graduation
  threshold (Class C candidate).

The filing carries capmon's proposed classification (`class-b` /
`class-c`); triage here may reclassify — the classification test, not
the filer's label, decides what a change is.

**Filing discipline** (requirements on the filer, i.e. capmon's
automation):

- **Dedup key:** one open issue per distinct
  `(diagnostic id, provider, unmapped source-form value)`. Re-fires
  update a count and last-seen timestamp on the existing issue; they
  never open a new one.
- **Threshold:** file only after the source form is observed on
  multiple distinct content items — a single garbled output is not a
  spec gap.
- **Staleness:** if a form stops being observed for a defined window,
  the issue is auto-marked stale, so a batch does not land a vector for
  a source form no provider still emits.
- **Graduation debounce:** the 2+ provider trigger applies the same
  threshold per provider — a brief coincidence across two providers
  does not trip a Class C filing.

## Source-of-truth rule

ACIF's normative appendices are the source of truth for canonical
vocabulary and mapping tables. Every derived copy — capmon's
`docs/spec/canonical-keys.yaml` today, any registry's vocabulary
projection tomorrow — is downstream: **if a derived copy disagrees with
the appendices, the derived copy has a bug.** The machine-readable
comparison target is `conformance/capability-vocabulary.yaml` — the
published projection of the L1 specs' Capability Dispositions sections,
kept current by the runner selftest's capability-vocabulary sync check
(spec-prose parsing happens once, at the authority; downstream checks
never parse markdown). Its companion `conformance/diagnostic-ids.yaml`
is the parallel projection of the L1 specs' Error Identifiers sections,
grouped by disposition class and kept current by the diagnostic-ids sync
check; downstream derives the Class B totality-net set from it as the
reject-class ids ending `_unmappable`. Each derived consumer owns its own drift check
(for capmon: a CI diff of its copy against that export, failing capmon's
CI, never ACIF's). Outbound propagation is
deliberately out of scope here: ACIF changes vocabulary through this
process and does not chase its copies; the drift checks are how copies
learn they are behind.
