# First graduation evidence — differential pass at core scope (acif-43d)

**2026-07-14.** First DESIGN.md §8 differential pass between two
independent implementations of ACIF 0.1: zero disagreements across 171
comparable generated trials. Both static suite reports and the
differential report are checked in beside this packet in
`differential-core-evidence-2026-07-14/`.

This is graduation *evidence*, not a graduation: §8 graduation requires
two implementations passing **all** scopes, and impl #2 claims core only.
The published suite remains the normative claim basis.

## Implementations under test

| | impl #1 | impl #2 |
|---|---|---|
| IUT | syllago (`hello`: syllago 0.0.0-dev) | acif-ts (`hello`: acif-ts 0.1.0) |
| Language / lineage | Go / Anthropic (Fable-specified, in-repo) | TypeScript / GPT-5.5 (clean-room via Codex) |
| Source (published) | https://github.com/OpenScribbler/syllago @ `f5397e7e` | https://github.com/OpenScribbler/acif-ts @ `1a09a95` |
| Adapter | `cli/cmd/acif-adapter` (Go shim, built `-buildvcs=false`) | `bin/acif-adapter.ts` (bun) |
| `adapter_protocol` | 2 | 2 |
| Claimed scopes | all ten | core |

Both adapters declare protocol 2, so verdict `reason` values were
asserted exact-string against the Decision #36 minted identifiers in the
static runs and compared exact-string in the differential.

## Static suite baselines (suite 5, 166 vectors)

- **syllago**: all ten scopes requested, all passed — 166/166 `pass`
  (2 vacuous conditional invariants — one in command.yaml, one in
  uri.yaml), zero
  fail/unsupported/env-blocked/harness-error. This is also the
  protocol-2 redeclare verification: syllago now passes with reasons
  asserted, statuses identical to its protocol-1 Stage 4 run.
  Report: `syllago-static-report.json`.
- **acif-ts**: core scope requested and passed — 13/13 `pass`
  (TV-1..TV-13), everything else out-of-scope.
  Report: `acif-ts-static-report.json`.

## Differential run

- **Invocation:** `python3 -m conformance.runner differential
  --adapter-a <syllago shim> --adapter-b "bun …/bin/acif-adapter.ts"
  --seed 20260714 --count 200 --report differential-report.json`
- **Runner:** 0.1.0-stage1, runner_protocol 2, at spec-repo commit
  `7bca940` (the commit introducing the differential mode; suite 5).
  (Hash re-pinned 2026-07-14: the repo's history was rewritten before
  publication to remove local working-history paths; file contents at
  the cited commit are unchanged.)
- **Environment:** one machine (WSL2 Linux), Python 3.14.3, bun 1.3.5,
  go 1.23.4; all env probes ok.
- **Result: clean.** 200 trials: **171 agree, 0 disagree**, 29
  uncomparable, 0 unsupported-in-required-families, 0 harness errors.

Per family (trials are generated deterministically from the seed;
inputs did not exist before this run):

| Family | Surface exercised | Trials | Outcome |
|---|---|---|---|
| body | fresh file trees through `ingest` → `body_hash`, `classification` (incl. root-sidecar exclusion, nested/unicode names, frontmatter) | 61 | all agree |
| sidecar | fresh publisher sections → `metadata_hash`, `canonical_bytes` (JCS: shuffled key order, unicode, quotes/backslashes/newlines, nested `license`) | 52 | all agree |
| envelope | fresh single-defect records → `conformant`, `reason`, `params.field` (invalid kind/UUID/SemVer/SPDX, the four forbidden fields) | 30 | all agree |
| pack_id | fresh `derive_pack_id` inputs under the pinned namespace → `inferred_pack_id` (UUIDv5) | 28 | all agree |
| normalize_uri | fresh URI strings | 29 | uncomparable — acif-ts claims core only and answers `unsupported`; informative until both IUTs claim registry |

Spot-check confirms no vacuous agreement: every `agree` trial compared
concrete values (hex digests, canonical byte strings, minted
identifiers, derived UUIDs) — zero all-absent field sets.

## What this kills

The two implementations share no code, no author, and no model lineage;
the differential inputs were generated fresh from the seed at run time.
Agreement on 171 never-before-seen inputs across the hashing, JCS
canonicalization, envelope-verdict, and UUIDv5 surfaces is not
reproducible by a lookup-table adapter, and byte-identical
`canonical_bytes` agreement pins the JCS implementations against each
other rather than against authored expectations.

## Reproduction

Re-run with the same seed against the pinned commits; the trial set is
identical. `--seed 20260714 --count 200`.
