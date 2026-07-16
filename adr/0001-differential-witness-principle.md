# ADR 0001 — The Differential-Witness Principle

**Status:** Accepted (2026-07-16)
**Deciders:** Working group, on convergent recommendation of the acif-zgc
review subset (spec-purist, valsorda, registry-operator), ratified
2026-07-15 under standing trust delegation.

## Principle

> **No scope's class-B verdict is machine-authoritative until that scope
> is differentially clean — two independent implementations agree.**

A *class-B verdict* is a machine judgment that a provider source
mechanism is (or is not) covered by a normative mapping table — the
judgment that drives Class B filings under
[CHANGE-PROCESS.md](../CHANGE-PROCESS.md). A scope is *differentially
clean* when the conformance runner's differential mode
([conformance/runner/DESIGN.md](../conformance/runner/DESIGN.md) §8)
shows two independent implementations in full agreement over that
scope's vector catalog.

## Context

The conformance architecture already refuses to let any single
implementation define conformance: vectors are normatively authoritative
over prose, and the runner's differential pass is graduation evidence,
not a formality. But that discipline had a gap on the *inbound* path.

Automated gap detection (capmon's curator pipeline) wants to confirm a
candidate spec gap by running a canonicalizer and reading back the
diagnostic: a totality-net reject (`*_unmappable`) is Class B evidence
per the CHANGE-PROCESS classification test. When only one implementation
covers a scope, that readback silently substitutes **one
implementation's switch statement** for the normative appendix as the
mapped-ness oracle — the exact single-source-of-truth collapse the
differential harness exists to kill. At the time of this decision,
syllago was the sole implementation of the rule and hook scopes; the
2026-07-14 171/171 differential pass
([conformance/evidence/differential-core-evidence-2026-07-14.md](../conformance/evidence/differential-core-evidence-2026-07-14.md))
was core-scope only.

The two confirmation directions are not symmetric:

- **Already-mapped** (rejecting a false gap candidate) is sound today:
  if the current canonicalizer maps the form cleanly, the form has a
  canonical image regardless of how many implementations witness it.
- **Genuinely-unmapped** (confirming a true gap) is where a single
  implementation's bug — a missing switch arm the spec actually covers —
  becomes a machine-filed spec change. This direction is what the
  principle gates.

## Decision

Downstream machine confirmation treats a class-B verdict as
machine-authoritative **only** for scopes that are differentially clean.
For any other scope, a genuinely-unmapped verdict is filed as
`unconfirmed/needs-human` with pinned evidence (protocol version,
implementation, export revision), never as a confirmed classification.
Degraded confirmation paths (probe unavailable, version skew, timeout)
fail toward `unconfirmed`, never toward closure or suppression.

The principle binds the trust model, not the tooling: it holds for any
future consumer of class-B verdicts, not only capmon.

## Consequences

- Full-scope parity in a second implementation (acif-ts) is **ACIF's
  graduation debt**, not a downstream feature request. A spec witnessed
  by one implementation isn't a spec yet; each scope the second
  implementation cannot witness is a scope where gap confirmation stays
  human-gated.
- The hook scope is the acute case: its §7.4 source mechanisms are
  shape-predicates that cannot be decided from a static export, so a
  running second witness is load-bearing exactly there (task acif-5lk).
- The named-token subset of source mechanisms is decidable against a
  deterministic spec export (task acif-e5z) without invoking any
  implementation; the export path and this principle together bound how
  much trust a canonicalizer readback ever carries.
- This ADR records the decision. Promoting the principle into
  CHANGE-PROCESS.md as normative process text is a separate, future
  change; nothing in CHANGE-PROCESS.md is amended by this record.
