# Hook-scope graduation evidence — differential pass at core + hook (acif-5lk)

**2026-07-16.** Second DESIGN.md §8 differential pass between two
independent implementations of ACIF 0.1, and the first to cover the
**hook scope**: zero disagreements across 381 comparable generated
trials (127 of them hook-scope), seed-deterministic and re-runnable.
Both static suite reports and the differential report are checked in
beside this packet in `differential-hook-evidence-2026-07-16/`.

This is graduation *evidence*, not a graduation: §8 graduation requires
two implementations passing **all** scopes, and impl #2 claims core +
hook only. The published suite remains the normative claim basis.

**Why hook first** (adr/0001-differential-witness-principle.md): hook
§7.4 mechanisms are all shape *predicates*, which the static
`source-mechanisms.yaml` export cannot decide — a differential second
witness is load-bearing exactly there. With this pass, a hook
canonicalizer readback is two-impl-witnessed rather than a syllago
echo; per the differential-witness principle this is what allows a
machine-authoritative already-mapped verdict on hook class-B
candidates (capmon-dgn's named-token path uses the static export; its
hook shape-predicate path uses a probe whose trust rests on this pass).

## Implementations under test

| | impl #1 | impl #2 |
|---|---|---|
| IUT | syllago (`hello`: syllago 0.0.0-dev) | acif-ts (`hello`: acif-ts 0.1.0) |
| Language / lineage | Go / Anthropic (Fable-specified, in-repo) | TypeScript / clean-room: core by GPT-5.5 (Codex), hook scope by Gemini 3.5 Flash (agy), both against spec text only — hook/platform vector catalogs off-limits to the implementer, every diff Fable-reviewed |
| Source (published) | https://github.com/OpenScribbler/syllago @ `b9e68324` | https://github.com/OpenScribbler/acif-ts @ `9ef2cca` |
| Adapter | `cli/cmd/acif-adapter` (Go shim, built `-buildvcs=false`) | `bin/acif-adapter.ts` (bun) |
| `adapter_protocol` | 2 | 2 |
| Claimed scopes | all ten | core, hook |

## Static suite baselines (suite 6, 170 vectors)

- **syllago**: all ten scopes pass — 170/170 `pass`, zero
  fail/unsupported/env-blocked/harness-error.
  Report: `syllago-static-report.json`.
- **acif-ts**: core and hook scopes pass — 170/170 `pass` across all
  catalogs (core, hook, and platform catalogs assert in-scope;
  remaining catalogs exercise the shared envelope/requires surface).
  Report: `acif-ts-static-report.json`.

## Differential run

- **Invocation:** `python3 -m conformance.runner differential
  --adapter-a <syllago shim> --adapter-b "bun …/bin/acif-adapter.ts"
  --seed 20260716 --count 400 --report differential-report.json`
- **Runner:** 0.1.0-stage1, runner_protocol 2, at spec-repo commit
  `5e1ce95` — the commit introducing the four hook trial families.
- **Environment:** one machine (WSL2 Linux), Python 3.14.3, bun 1.3.5,
  go 1.23.4; all env probes ok.
- **Result: clean.** 400 trials: **381 agree, 0 disagree**, 19
  uncomparable, 0 unsupported-in-required-families, 0 harness errors.
  The 19 uncomparable are all `normalize_uri` — informative until both
  implementations claim registry scope.

Per family (trials generated deterministically from the seed; inputs
did not exist before this run):

| Family | Surface exercised | Trials | Outcome |
|---|---|---|---|
| body | core §7 body hashing over fresh multi-file bodies | 109 | all agree |
| sidecar | core §8.6 canonical bytes + §7.8 metadata hash | 65 | all agree |
| envelope | core §9 envelope rejects (kind/id/version/spdx/forbidden) | 55 | all agree |
| pack_id | publisher §9.4 UUIDv5 inference | 25 | all agree |
| **hook_sidecar** | [ACIF-HOOK] §7.1/§7.2 os-set canonicalization + pinned rejects (empty/invalid os, default & platform ambiguity), §8.2 absent-type materialization, inline-content line-ending convergence, §9 body_hash over inline scripts | 47 | all agree |
| **hook_mechanism** | §7.4 shape predicates: per-os-key-map (incl. alias, osx→darwin, executable-identity merge, passthrough-without-base malformed), dual-shell-fields (closed-set + empty malformed, shell-OS-proxy diagnostic), filename-extension-convention (every extension class incl. uninferable), unknown-token totality net; compares canonical handlers, provenance rollup, diagnostic ids | 41 | all agree |
| **hook_body** | §9.2 referenced-file manifest over materialized bodies (unicode + space paths, unreferenced-file exclusion, auxiliary_files) and missing-file rejects | 25 | all agree |
| **hook_provider_event** | Appendix A.1 provider-native event spellings drawn from a ten-provider alias table (incl. the copilot-cli `errorOccurred` multi-match §8.1 tiebreak) + unrecognized spellings | 14 | all agree |
| normalize_uri | registry URI normalization (informative) | 19 | uncomparable (impl #2 does not claim registry) |

## Comparison-discipline notes

- **Mechanism-only ingests do not compare `canonical_bytes`.** The
  event of the envelope synthesized for a mechanism-only
  `provider_config` ingest is an identified spec-precision gap (filed
  in the acif tracker, batched with the extension case-sensitivity
  gap); the family compares `canonical.handlers`, the §7.5 provenance
  rollup, and diagnostic ids instead. When the gap is fixed the family
  can graduate to full canonical-bytes comparison.
- **provider_config forms do not compare verdict-field presence.**
  PROTOCOL §4.1 scopes `conformant`/`reason` to record-validation
  forms and makes all result fields optional; syllago emits
  `conformant: true` on provider_config ingests, acif-ts omits it —
  both conforming, so presence asymmetry is adapter plumbing, not a
  semantic disagreement.
- Diagnostic comparison is by sorted id set (`diagnostics_ids`),
  insensitive to ordering and message prose.

## Re-running

Same seed + count at spec commit `5e1ce95` reproduces the trial set
byte-for-byte (modulo fixture paths). Build the syllago shim from
`b9e68324` (`go build -buildvcs=false -o acif-adapter
./cmd/acif-adapter` in `cli/`), run acif-ts at `9ef2cca` via
`bun bin/acif-adapter.ts`.
