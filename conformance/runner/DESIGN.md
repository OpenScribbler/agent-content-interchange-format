# ACIF Conformance Runner — Design

**Status:** reviewed design, 2026-07-13. Four-reviewer pass (spec-purist,
platform-vendor, karpathy, valsorda), unanimous SHIP-WITH-FIXES; all
blocking findings applied. Implementation follows this document; where the
implementation and this document disagree before PROTOCOL.md exists, this
document governs.

## 1. Goal and non-goals

The runner executes the published conformance vectors
(`conformance/vectors/*.yaml`: 165 vectors — 153 static, 10 mock-transport,
2 mock-crawl — across 11 catalogs) against an **implementation under test
(IUT)** and produces a conformance report. The specs graduate from Draft
when two independent implementations pass all vectors in their claimed
scope ([ACIF-REGISTRY] §5 and the per-spec conformance clauses).

Non-goals and honest limits:

- The runner does not replace the vectors' authority. Vectors are
  normative; the runner is tooling. When the runner and a vector disagree,
  the runner has the bug (same rule the suite README states for
  `reference/`). §4 makes this rule mechanical rather than aspirational.
- The runner does not certify anything by itself; §8 defines what a
  passing report entitles an implementer to say.
- A pass describes **the adapter's behavior**. The adapter is expected to
  be a dev-only shim linking the implementation's internal libraries — not
  the shipping binary — and no harness can technically bind the tested
  code path to the production code path. §8's graduation requirements
  (published adapter source, differential pass) narrow this gap; they do
  not close it, and nobody should read "passed" as "the product does
  this."

## 2. Shape

- Lives at `conformance/runner/` as a Python 3 package, matching the
  existing `conformance/reference/` tooling (Python + PyYAML + stdlib
  only, including `ssl` for §6). Entry point:
  `python -m runner --adapter <cmd> [--scope …] [--only TV-…]`.
- The vector catalogs are **not modified**. IDs, contents, and normative
  status are untouched. Everything runner-specific lives in the runner.
- **Order of work:** `PROTOCOL.md` (the per-op request/response schemas,
  the diagnostic object schema, and the canonical-bytes encoding) is
  written **before** the runner, and the runner's canned-adapter self-test
  validates against PROTOCOL.md's schemas. The public contract must not be
  back-filled from the runner's behavior.

## 3. The adapter contract (the public surface)

An IUT ships an **adapter**: an executable the runner spawns and speaks
line-delimited JSON to (one request object per line on stdin, one response
object per line on stdout, strictly in order, exactly one request in
flight at a time; stderr is free-form log passthrough).

Why subprocess + NDJSON: language-agnostic (the two-independent-
implementations bar makes polyglot support non-negotiable), no framework
dependencies, hand-testable (`echo '<request>' | my-adapter`).

Lifecycle rules (each of these was a support ticket waiting to happen):

- **One adapter process per run.** Invariant mode and mock-crawl
  sequencing assume a single session.
- **The adapter is stateless across requests.** Where a mock-crawl binding
  sequences two passes, cross-pass state lives runner-side and is passed
  back in the second request.
- Encoding is UTF-8, no BOM. Requests and responses may be long (inline
  fixture content rides inside JSON lines); the contract sets a
  line-length ceiling of 16 MiB, and adapter authors must not rely on
  default line-buffer sizes.
- PROTOCOL.md owns the per-request timeout (default 30 s); expiry is a
  `harness-error` on that vector.

### 3.1 Handshake

First request is always:

```json
{"op": "hello", "runner_protocol": 1}
```

Response declares identity and claimed scope:

```json
{"ok": true, "result": {"implementation": "capmon", "version": "1.4.0",
  "adapter_protocol": 1,
  "scopes": ["core", "hook", "skill", "rule", "command", "agent", "mcp"]}}
```

Scope names are a closed enum pinned in PROTOCOL.md: `core`, the six L1
type names, `publisher`, `registry`, `render`. The runner selects the
vector subset the declared scopes require (per the §8 mapping table);
vectors outside the claimed scope are reported `out-of-scope`, which is
not a failure.

Protocol versioning: a single integer, both sides'. The runner **refuses
to run** on an `adapter_protocol` it does not implement — a run-level
harness error, never a best-effort continuation. Unknown fields in
requests and responses are ignored by both sides, so additive changes
never bump the integer; changes to required fields or response semantics
do. Both protocol numbers are embedded in the report.

### 3.2 Requests and responses

```json
{"op": "<operation>", "input": { … }}
```

Requests carry **no vector ID**. The catalogs are public and carry
committed expected values; a request that names its vector makes a
lookup-table adapter a one-liner. Correlation is by strict ordering;
debugging context goes to stderr.

Every response is exactly one of:

```json
{"ok": true, "result": { … }}
{"ok": false, "error": "acif.body.symlink", "diagnostics": [ … ]}
{"unsupported": true}
```

- `error` MUST be a spec-minted `acif.*` identifier; error vectors assert
  on it exact-string. Any `error` value not matching `acif.*` is scored
  `harness-error` (adapter bug), never `fail` — this is the reserved
  channel for adapter-internal errors, and top-level exception handlers
  should emit a non-`acif.*` string deliberately.
- **Non-error non-conformance verdicts** (the ~23 vectors expecting
  `conformant: false` with a `reason`, whose reasons are not spec-minted
  identifiers): the adapter returns
  `{"ok": true, "result": {"conformant": false, "reason": "…"}}`. Bindings
  assert the boolean; `reason` is **informative diagnostic text**, never
  asserted. (Spec-side roadmap item: mint identifiers for these rejection
  classes; until then the suite must not become a mint by accident.)
- `unsupported` is **per-request**, not per-op: it means the adapter
  cannot serve this request form. This is load-bearing for wide ops like
  `ingest` (§3.3) and is contract text, not a convenience.
- Field discipline, both directions: bindings assert **exactly the
  vector's expect fields** — extra unasserted fields in a `result` are
  ignored; an **asserted field absent from a result is a `fail`, never
  `unsupported`**. Absence assertions (`combined_scalar_present: false`,
  forbidden-fields vectors) are checked as absence, never satisfied by
  subset matching. Anything softer is a silent-failure factory.
- Any malformed response, crash, or timeout is a `harness-error` on that
  vector: neither pass nor fail, and the run is not claimable until
  resolved.

Diagnostics are structured objects, not strings:
`{"id": "acif.<…>", "params": { … }}`, schema pinned per-identifier in
PROTOCOL.md (several vectors assert diagnostic *payload*, e.g. the
colliding OS and entry indices, or the declared name recorded in the
tier-2 naming diagnostic). Matching discipline: every expected diagnostic
must be present with its required params, and no unexpected diagnostics
from the same `acif.*` family may appear on that response — an adapter
that sprays diagnostics does not pass diagnostic vectors.

### 3.3 Operation vocabulary (v1)

Derived from the input/expect shapes of all 165 vectors. Exact schemas
live in PROTOCOL.md (§2: written first); the vocabulary:

| Op | Covers | In (essentials) | Out (essentials) |
|---|---|---|---|
| `ingest` | canonicalization, hashing, materialization, classification, passthrough, forbidden-fields, body error vectors | `kind`, source (`body_root` path and/or provider config / sidecar / frontmatter), context | `canonical`, `body_hash`, `metadata_hash`, `publisher_section`, `diagnostics[]` — or `error` |
| `derive_pack_id` | UUIDv5 inference | namespace, repository URL, display name | `inferred_pack_id` |
| `resolve_pack` | pack membership / rename / unresolved-declared | item, known packs | `pack_resolution`, `member_of`, `install` |
| `evaluate_requires` | three-valued `requires` evaluation | `item_requires`, `consumer_recognizes` | `evaluation`, `install` |
| `evaluate_freshness` | staleness / trust tier / clocks | record, consumer clock, policies, attestation evaluation | `staleness`, `trust_tier`, `warnings[]`, `response_hash` |
| `normalize_uri` | `source_uri` pipeline, static form | URI string | `source_uri` — or `error` |
| `fetch_uri` | `source_uri` pipeline, transport form | URL, `trust_ca` path, `resolve` map (§6) | `source_uri`, `source_status?` — or `error` |
| `derive_url_name` | URL-derived display name (tier-2) | URI, body classification | `url_derived_name`, `diagnostics[]` |
| `render` | render-back, degradation, round-trip | `canonical`, render target, invocation context | `output`, `diagnostics[]`, `lossy[]` |
| `project` | registry projections | item / canonical | `projection` |
| `resolve_reference` | cross-reference + reciprocal-entry vectors | item, registry state | `cross_reference`, emitted entries |

Notes:

- `ingest` is deliberately one wide op rather than separate
  `canonicalize`/`body_hash`/`metadata_hash` ops: real implementations
  compute these in one pass, a hash-only vector asserts on a subset of the
  result (§3.2 field discipline), and split ops would create a
  composition question ("must they agree?") that would itself need
  vectors.
- `evaluate_freshness.response_hash` exists for the byte-identity vector
  (registry §11.3: the served item response is byte-identical whether the
  attestation system is reachable). Comparing semantic projections would
  test JSON key ordering, not the MUST; a hash of the served response
  bytes is exact-string comparable without shipping the body over the
  pipe. Implementations that do not serve item responses answer
  `unsupported` for requests asserting it (registry scope requires it).
- `source_status` is OPTIONAL output ([ACIF-REGISTRY] §10.6) — emitting it
  is never required; its value, when emitted, is invariant-checked (§5).
- The canonical-bytes encoding for byte-exact assertions (the [ACIF-CORE]
  §8.6 serialization, carried verbatim or base64) is pinned in
  PROTOCOL.md, not implied.

### 3.4 Fixture materialization

File-tree fixtures (`files: {path: content}`) are **materialized by the
runner** to a fresh temp directory per vector; the request carries the
absolute `body_root`. Production canonicalizers ingest real directories,
and several vectors are unrepresentable inline — the `acif.body.symlink`
vector needs a real symlink; the NFC path-collision vector needs two
byte-distinct names on disk.

Startup capability probes, each three lines and each preventing a class of
spurious results: **byte-preserving names** (write an NFC/NFD pair; macOS
APFS fails this), **symlink creation** (Windows CI without Developer Mode
fails this), **case-sensitivity** (probed now even though no current
vector needs it; the failure mode is silent collision). A vector the
runner declines to execute because a probe failed is reported
`env-blocked` (§7) and blocks any claim over a scope containing it (§8) —
environment limitations must never become conformance loopholes.

On `fail` or `harness-error`, the vector's temp tree is kept and its path
printed in the report; on `pass` it is deleted.

## 4. Vector bindings

Vectors are heterogeneous — ~60 distinct input/expect shapes. The runner
therefore contains a **binding layer**: per-vector (family-grouped) code
mapping a vector to adapter calls plus assertions. `generate_vectors.py`
already proves this pattern at small scale. No assertion DSL: a DSL
interpreter plus 60 shapes encoded in DSL is strictly worse than 60 shapes
in plain Python.

The vectors-win rule is enforced by five mechanisms, not vigilance:

1. **Coverage self-check** — every vector ID in every catalog has exactly
   one binding; an unbound vector fails the runner's own test suite. A new
   vector cannot be silently skipped.
2. **Anti-softening self-check** — every literal `expect` value in a
   catalog (hash strings, `acif.*` identifiers, canonical-bytes strings,
   enum members) must appear verbatim in the corresponding binding's
   assertion set. A binding that drops or rewrites a committed literal
   fails CI.
3. **Sabotage self-test** — the reference adapter (§9) wrapped in a
   mutator that perturbs every response (flip a hex digit in each hash,
   rename each error identifier, drop each diagnostic, negate each
   verdict); every vector the reference adapter can serve MUST **fail**
   against the sabotaged adapter. A binding that cannot be made to fail is
   not a test.
4. **Appendix-A payload-pin self-check** — every binding that asserts a
   diagnostic's `params` content must have its `(identifier, vector)`
   pair pinned in PROTOCOL.md Appendix A, and every pinned row must have
   its asserting binding. Payload assertions cannot drift from the
   published pin table in either direction.
5. **Verdict-reason gating self-check** — a scripted `adapter_protocol: 2`
   session emitting the minted identifiers (and pinned verdict params)
   passes, one emitting the pre-flip free-text reasons fails, and a
   protocol-1 session stays unasserted on `reason` — the
   never-retroactive freeze is machine-checked, not policy.

Translated bindings — behavioral negatives, invariants, anything whose
assertion is not a literal from the `expect` block — carry a **derivation
note** citing the spec clause that justifies the derived assertion
(example: the `generated_at`-conflation vector's fixture timestamps are
chosen so a conflating implementation returns `fresh` where §11.2's
72-hour default yields `stale`; the binding asserts `staleness: stale`,
derived from §11.1–§11.2). Derivation notes ship with the runner, and the
report embeds a **binding-set hash** beside the catalog hashes, so a claim
pins every interpretive artifact.

Assertion discipline: hash comparisons exact-string, error identifiers
exact-string, canonical-bytes byte-exact, diagnostics per §3.2. A vector
with multiple cases is atomic: `pass` iff every case passes.

Growth policy (also for the suite README): new vectors SHOULD reuse an
existing expect-shape; a new shape is a design decision requiring a new
binding pattern, not a drive-by. This keeps binding growth sublinear and
surfaces interpretation cost at vector-authoring time.

## 5. Execution modes

- **probe** — call op(s), assert on the response. The bulk of the suite,
  including behavioral negatives (fixtures are chosen so the conforming
  and non-conforming computations return distinguishable values; the
  binding asserts the conforming one, with a derivation note per §4).
- **invariant** — a property checked over all adapter responses observed
  during the run. Two subtypes with different pass criteria:
  - **conditional** (e.g. the `source_status`-enum vector): the guarded
    field is OPTIONAL; the property must hold over every in-scope response
    in which the field was emitted. If it was never emitted, the vector
    passes **vacuously** and the report row is annotated `pass (vacuous)`
    — the spec permits omission, and the harness must not strengthen a
    vector beyond its published normative force.
  - **paired** (e.g. degraded-render-output-carries-its-diagnostic): the
    binding names the probe vectors that exercise each trigger path. It
    passes when the property held everywhere and every trigger path whose
    owning scope is claimed was exercised by its probe; an unexercised
    claimed trigger is a `harness-error`, never a silent pass. Trigger
    paths whose owning scope is unclaimed are out of the requirement, like
    the vectors that carry them.

There is no attest mode. The one candidate (`documented_lossy`) is
mechanical instead: the adapter declares losses machine-readably
(`lossy: ["write-edit-distinction"]` in the `render` response) and the
binding asserts it like any probe. If implementation experience ever
produces a genuinely non-mechanical vector, an `attested` status can be
added to the report vocabulary then — a mode with zero members is a
reserved word for a hypothetical, and speculative slots don't stay inert.

## 6. Harness families

Three families (the suite README's "Two harness families exist" line is a
known one-word defect, fixed alongside this design; [ACIF-REGISTRY] §5
counts per-surface and is consistent as written).

- **static** (153) — request/response only.
- **mock-transport** (4) — the vectors' semantics are `https://`-URL
  semantics: downgrade detection distinguishes an `http://` **hop**, and a
  runner that rewrote URLs to `http://127.0.0.1` would emit requests that
  are themselves `scheme_forbidden` — untestable as transport behavior and
  a test-only URL path inside the adapter, which is precisely the
  divergence class this family exists to catch. Therefore the mock
  terminates **real TLS** (stdlib `ssl`) under a **per-run ephemeral CA**,
  and the `fetch_uri` request carries two production-grade knobs:
  `trust_ca` (path to the CA bundle) and `resolve` (hostname → address
  map, e.g. `{"old.example.com": "127.0.0.1:4443"}`) — the
  `SSL_CERT_FILE` / `curl --resolve` pattern, standard fetcher
  configuration rather than special-case code, no trust-store mutation. A
  plain-HTTP listener also runs so downgrade vectors can present an actual
  insecure hop to refuse. Addresses pin `127.0.0.1` (never `localhost`,
  which may resolve `::1`); ports are ephemeral and passed in the request;
  one vector's double at a time, torn down after each. TLS negotiation
  itself is not under test and PROTOCOL.md says so.
  **Coverage note:** the §10.4 composition ambiguity is resolved
  (permanent-prefix rule, SHAPE Decision #35: record the request URL of
  the first temporary redirect, else the final resolved URL) and the
  family now pins it: TV-URI-w (temp-then-permanent freeze), TV-URI-x
  (prefix endpoint, not crawl-seed), TV-URI-y (consecutive permanents
  fold; 308 representative), TV-URI-z (perm-temp-perm sandwich),
  TV-URI-m2 (post-freeze downgrade still rejects), TV-URI-l3 (303
  temporary-class representative). Record-time re-dereference is not
  separate coverage: under Decision #35 it is the composition rule's
  by-construction outcome, not a distinct post-crawl check.
- **mock-crawl** (2) — the runner sequences two passes with changed mock
  state and asserts across the pair; cross-pass state lives runner-side
  (§3 statelessness).

## 7. Report

Machine-readable `report.json` plus a human table. Per-vector status:
`pass | fail | unsupported | out-of-scope | env-blocked | harness-error`
(`pass` may carry the `vacuous` annotation, §5). Failures embed expected
vs. observed **and the exact NDJSON request line(s) sent**, so the
developer inner loop is: vector fails → `--only TV-X` → pipe the printed
request into the adapter by hand.

The report embeds everything a claim pins: adapter `hello` identity and
both protocol numbers, runner version, catalog content hashes,
binding-set hash, environment probe results, and the exact adapter
invocation. The human table **leads with the scopes not passed or not
claimed** — a `core`-only pass over 40 vectors must be un-mistakable as
such, never a wall of green.

## 8. Claim discipline

- **The required-vector set is defined by a normative, machine-readable
  scope→vector-ID mapping table** shipped with the runner (many-to-many:
  `core.yaml` carries publisher- and registry-owned vectors;
  `platform.yaml` is hook-owned but type-general; several vectors cite two
  owning specs). The §4 coverage self-check also verifies every vector ID
  appears in at least one scope. Scope prerequisites: each L1 scope
  requires `core`; `publisher` and `registry` require `core`; `render`
  requires `core` and at least one L1 scope. A scope's required set is the
  transitive union over its prerequisites of the table's entries. Without
  this table, "passed a scope" is a predicate two implementers can
  evaluate differently — the exact disagreement this discipline exists to
  prevent.
- A scope is **passed** when every vector in its required set is `pass`
  (vacuous passes count; invariant vectors included): zero `fail`, zero
  `unsupported`, zero `env-blocked`, zero `harness-error`.
- **Single-run atomicity:** a scope claim cites exactly one report — one
  runner invocation, one adapter identity, one catalog-hash set, one
  environment. Results MUST NOT be stitched across runs, adapter versions,
  or machines.
- **The claim string is minted here:** a conforming claim is exactly
  "conforms to ACIF 0.1, scopes: <handshake tokens, verbatim>". Registry
  scope inherently includes the mock-transport and mock-crawl families via
  the mapping table (never static-only, per [ACIF-REGISTRY] §5).
- `unsupported` is a development dashboard, not a conformance state: it
  blocks the claim for any scope whose required set contains that vector.
- **Verification is reproducibility, not signature.** A report is
  self-asserted and trivially editable; there is no authority to sign it
  and a signature nobody verifies is a filing cabinet. A claimable report
  embeds everything needed to re-run it (§7), and re-running is how a
  claim is checked.
- **Graduation** (Draft → final) cites the pair of reports from two
  independent implementations passing all scopes, and additionally
  requires: (a) each implementation's **adapter source is published** —
  the adapter is where the shim-vs-product gap lives, and readable
  adapters are the only defense; (b) a **differential pass**: the runner
  generates randomized equivalence-preserving inputs (fresh bodies through
  `ingest`, fresh URI strings through `normalize_uri`) and the two IUTs
  must agree with each other. The pair is its own oracle — this smuggles
  no informative reference implementation into normative status — and it
  kills the lookup-table adapter class outright: you cannot pre-compute
  answers to inputs that did not exist yesterday. The published 165 remain
  the normative claim basis; the differential pass is graduation evidence
  only. Implementation: `conformance/runner/differential.py`, invoked as
  `python -m conformance.runner differential --adapter-a … --adapter-b …
  --seed … --count … [--report …]` — trials are generated
  deterministically from the seed, so a report is re-runnable the same
  way a static report is (§7).

## 9. Bootstrap and validation of the runner itself

First adapter: a thin wrapper over `conformance/reference/acif_hash.py`
(informative reference impl). It implements the hash surface of `ingest`
and answers `unsupported` for the ten other ops and for `ingest` request
forms it cannot serve. Expected honest outcome: hash-bearing vectors pass;
ingest vectors asserting fields the wrapper genuinely computes but gets
wrong **fail** (per §3.2, a missing asserted field is a fail — the wrapper
does not get to dodge assertions per-field); everything else
`unsupported`. This validates runner mechanics — fixture materialization,
protocol, exact-match assertions, unsupported accounting — without
pretending to be implementation #1.

Runner self-tests, all CI-gating: the five §4 checks (coverage,
anti-softening, appendix-a payload pins, verdict-reason gating,
sabotage), the canned-adapter protocol round-trip validated against
PROTOCOL.md schemas, the scope-table totality check (§8), the
suite-manifest head check (CHANGE-PROCESS.md), the
capability-vocabulary sync check (`capability-vocabulary.yaml` against
the L1 specs' Capability Dispositions sections — the published export
downstream copies diff against, per CHANGE-PROCESS.md), and the report
schema check.

## 10. Review record

Four reviewers (spec-purist, platform-vendor, karpathy, valsorda),
2026-07-13, unanimous SHIP-WITH-FIXES; all blocking findings applied
above. The four originally-open questions closed unanimously: wide
`ingest` (kept, with the §3.2 field discipline that makes it sound);
per-spec scope names (kept, rigor lives in the §8 mapping table);
`fetch_uri` with loopback (kept, upgraded to real TLS with standard knobs
— the one inter-reviewer conflict, adjudicated on the grounds that
rewritten `http://` URLs are themselves `scheme_forbidden` and a URL-map
would pin header bookkeeping rather than transport behavior);
single-integer protocol version (kept, with refuse-on-mismatch and
unknown-field tolerance pinned).

Filed outside this design: suite follow-up for transport-composition
vectors and the registry §10.4 chain-composition clarification (§6);
spec-side roadmap item to mint identifiers for the non-error
non-conformance rejection classes (§3.2); the suite README harness-family
count fix (§6).
