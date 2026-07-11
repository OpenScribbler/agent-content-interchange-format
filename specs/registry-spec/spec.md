# ACIF Registry Specification

**Version:** 0.1.0
**Status:** Draft
**Spec ID:** [ACIF-REGISTRY]

---

## Abstract

This document defines the Level 3 layer of the Agent Content Interchange Format: the conformance requirements for registries. It specifies the `registry_section` schema, the change-signal surfaces, registry-computed projections (derived capabilities, the advisory tier, provider capability coverage, install-scope capabilities), cross-reference resolution, the `source_uri` validation and normalization pipeline, the freshness model, and the registry error-identifier registry.

## 1. Introduction

A registry discovers items at their sources, canonicalizes them, records them as published records ([ACIF-PUBLISHER]), and serves them to consumers — install tools, sync tools, discovery surfaces, and policy engines. Everything a registry adds to a record lives in `registry_section`; this document is the schema and the compute contract for that section, plus the two consumer-facing disciplines that make registries interchangeable: a deterministic provenance pointer (`source_uri`) and a freshness model with clean clock separation.

## 2. Relationship to ACIF Core and the Lower Layers

This document is the Level 3 (L3) companion to [ACIF-CORE] and depends normatively on [ACIF-CORE], [ACIF-PUBLISHER], and the six L1 interchange specifications (whose derivation predicates and projections it computes). It redefines no term from those documents.

This document is compatible with [ACIF-CORE] version 0.1.x. All documents are Draft maturity.

## 3. Terminology

Terms defined in [ACIF-CORE] §2 and [ACIF-PUBLISHER] §3 are used without redefinition. Additionally:

**crawl** — a registry's fetch of an item's source; `fetched_at` is stamped at crawl time.

**projection** — a registry-computed, consumer-facing view derived from canonical form.

**advisory tier** — the projection tier for heuristic signals: method-stamped, imprecision-disclosed, never gating (§8.3).

**item-sidecar clock** — the `fetched_at`/`expires` pair: the only input to item staleness (§11).

**response-envelope clock** — the `generated_at`/`max_staleness` pair describing response assembly, never item staleness (§11).

**trust tier** — the attestation axis: `attested | unattested`, consumer-evaluated, orthogonal to freshness (§11.3).

## 4. Requirements Language

The key words "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHALL NOT", "SHOULD", "SHOULD NOT", "RECOMMENDED", "NOT RECOMMENDED", "MAY", and "OPTIONAL" in this document are to be interpreted as described in BCP 14 [RFC2119] [RFC8174] when, and only when, they appear in all capitals, as shown here.

## 5. Conformance

**Conforming registry** — satisfies every MUST and MUST NOT in this document, the registry-addressed requirements of [ACIF-CORE] and [ACIF-PUBLISHER], and the per-type registry obligations stated in the L1 specifications ([ACIF-HOOK] §13, [ACIF-SKILL] §13, [ACIF-RULE] §12, [ACIF-COMMAND] §10, [ACIF-AGENT] §10, [ACIF-MCP] §11).

`source_uri` conformance (§10) is tested at the registry-emit boundary across **two harness families** — static string vectors and mock-transport vectors — and MUST NOT be claimed on the static vectors alone. Freshness conformance (§11) likewise includes a mock-crawl vector.

The test-vector families in Appendix A are normatively authoritative: an implementation that contradicts a published vector is non-conformant regardless of any prose reading.

## 6. The `registry_section` Schema

Every registry-emitted record carries a `registry_section`; it is never sourced from publisher declarations. Fields, as they apply to the six interchange content types (the pack-record variant follows the schema block):

```yaml
registry_section:
  body_hash:                          # REQUIRED — [ACIF-CORE] §7
    algorithm: sha256
    value: "abc123..."
  body_size_bytes: 4096               # REQUIRED — byte count of the canonical body input
                                      # to the body_hash algorithm
  metadata_hash:                      # REQUIRED iff publisher_section present ([ACIF-PUBLISHER] §6)
    algorithm: sha256
    value: "def456..."
  attestation_hash:                   # OPTIONAL — slot for an external integrity/attestation
    algorithm: sha256                 # system; which system fills it is out of ACIF's scope
    value: "ghi789..."
  cross_references: [...]             # OPTIONAL — §9
  derived_capabilities:               # OPTIONAL — §8.1/§8.2
    from_canonical: {...}
    advisory: {...}                   # §8.3
  provider_capability_coverage: {...} # §8.4
  install_scope_capabilities: {...}   # §8.5
  inferred_pack_id: "b2c3d4e5-..."   # OPTIONAL — [ACIF-PUBLISHER] §9; present iff
                                      # publisher pack_id absent AND a pack was inferred
  pack_resolution: "inferred"         # OPTIONAL — declared | inferred | unresolved
  inference_version: "v0.1"           # REQUIRED when inferred_pack_id present
  fetched_at: "2026-05-11T18:00:00Z"  # REQUIRED — RFC 3339 with explicit offset, crawl time
  expires: "2026-05-14T18:00:00Z"     # OPTIONAL — §11.2
  source_uri: "https://..."           # REQUIRED — §10
  source_status: "live"               # OPTIONAL — live | moved | gone | unreachable (§10.6)
  publisher_declared: true            # REQUIRED — true iff publisher_section was populated
  publisher_metadata: "declared"      # OPTIONAL INFORMATIVE — declared | auto-generated | unknown
  generated_at: "2026-05-11T18:00:00Z" # OPTIONAL — response-envelope clock (§11)
  max_staleness: "PT1H"               # OPTIONAL — advertised freshness contract (ISO 8601 duration)
```

`publisher_metadata: declared` means the registry observed a declaration surface at crawl time; it does not mean the publisher cryptographically attested anything. Registries MUST NOT write to source files; all registry-generated metadata lives in sidecars, and the root-only sidecar exclusion of [ACIF-CORE] §7.5 governs hashing.

**Pack-record variant.** For `kind: pack` records the schema above is modified: `body_hash` and `body_size_bytes` MUST be absent (packs carry no canonical body, [ACIF-PUBLISHER] §8.2); `metadata_hash` follows [ACIF-PUBLISHER] §8.2 (present for declared packs, absent for inferred packs); and the section additionally carries `items` — the computed member list, one entry per item satisfying the membership predicate ([ACIF-PUBLISHER] §8.3), each entry the member's `id`. `items` is OUTPUT of the predicate, recomputed on every relevant change; publishers never author it. The provenance and freshness fields (`source_uri`, `source_status`, `fetched_at`, `expires`, `publisher_declared`, `generated_at`, `max_staleness`) apply to pack records as to item records.

## 7. Change-Signal Surfaces

`body_hash` is the canonical per-item change signal and is dispositive ([ACIF-CORE] §6.2). A conforming registry:

- MUST expose `body_hash` in **every** consumer-facing item response — never gated behind attestation, entitlement, or view.
- MUST expose `body_size_bytes` alongside it.
- MUST provide a per-pack tuple-set endpoint returning, for each member item, `(item_id, body_hash, metadata_hash_if_present, version_if_declared)` — one request per pack, not N item requests.

The tuple's `metadata_hash` member is null/absent exactly when the item has no `publisher_section`. *(Informative: `metadata_hash` joins the tuple because, under the [ACIF-CORE] §7.8 coverage model, a declared extension-block re-target on a frontmatter-bearing item moves only `metadata_hash` — a sync tool polling `body_hash` alone would miss the same change class that `body_hash` catches for sidecar-only types. Six-co-equal requires the polled surface to see both.)*

## 8. Projections

Every projection in §8.1, §8.4, and §8.5 is a derivation — correct by construction over canonical structure or over the registry's own capability-matrix data. Only §8.3 carries heuristics, and only under its constraints.

### 8.1 `derived_capabilities.from_canonical`

At ingest, a conforming registry MUST evaluate every DERIVABLE key's predicate D_K (as defined by the item's L1 specification) over the canonical body and expose the boolean results. Set-valued companions ride alongside the booleans, not instead of them — e.g., the distinct handler types observed on a hook, the declared activation mode and bounded globs of a rule ([ACIF-RULE] §12.1), the transport-type set of an MCP configuration, and the hook `os_coverage` projection ([ACIF-HOOK] §13.1).

Bounded-projection discipline: set-valued projections over closed small vocabularies (OS tags, transport types, handler types) are carried whole; projections over unbounded publisher arrays (globs) MUST be bounded per the owning L1 rule — never fan unbounded publisher input into polled response surfaces.

### 8.2 Zero author burden

Projections are registry-computed only: they MUST NOT be stored in or sourced from `publisher_section`, and their presence or absence never changes an item's conformance.

### 8.3 The advisory tier

A registry MAY compute heuristic signals (e.g., the command token-presence scan, [ACIF-COMMAND] §10.1) under `derived_capabilities.advisory`, subject to all of:

- method-version-stamped (`method: "<name>-v<N>"`), with the stamp REQUIRED on every emitted entry;
- both error directions documented in the owning specification;
- never sets `derivable`, never gates conformance, canonicalization, or install;
- no per-item confidence scores.

An advisory signal that cannot meet all four constraints MUST NOT be emitted.

### 8.4 `provider_capability_coverage`

Registries MUST surface, per canonical capability key disposed provider-matrix by an L1 specification, the set of providers supporting it — a shared capability-matrix fact computed once, not per-item. Rows in 0.1: `file_imports`, `hierarchical_loading`, `cross_provider_recognition`, `auto_memory` (rules); `argument_substitution`, `builtin_commands` (commands); per-event provider recognition (`event_provider_coverage`, hooks). Proxy mechanisms MUST NOT be recorded as support. *(Informative: matrix contents are observational snapshot data; registries should publish the matrix's provenance — source and crawl date — alongside the rows so consumers can judge staleness.)*

### 8.5 `install_scope_capabilities`

An OPTIONAL projection surfacing install-scope compatibility (project/global/user/managed and equivalents). Each entry MUST carry a provenance tag:

```yaml
install_scope_capabilities:
  global:  {supported: true,  source: canonical}
  project: {supported: true,  source: install_context}
  managed: {supported: false, source: publisher_claim}
```

`source` ∈ `{canonical, publisher_claim, install_context}` — derived from the canonical body, asserted by the publisher unverified, or determined by the install mechanism. Without the tag, consumers cannot distinguish a derived scope from a claim; emitting an entry without `source` is non-conformant. Provider-matrix facts (e.g., hierarchical loading) do not belong here — none of the three tags can honestly source one; they live in §8.4.

## 9. Cross-Reference Resolution

For every declared cross-item reference in a canonical body — UUID-authored (hook `activation_target`, skill `hook_ref`) or name-declared (agent `mcp_servers`/`skills`) — a conforming registry MUST resolve the reference at compute time into the [ACIF-CORE] §10 state vocabulary and emit one `cross_references` entry:

```yaml
cross_references:
  - source_path: "agent.mcp_servers[0]"  # JSON path to the reference site
    declared_name: "figma"               # the string the publisher wrote (name-declared refs)
    target_kind: mcp_config              # expected content type of the target
    target_id: "a1b2c3d4-..."            # REQUIRED iff resolution: resolved
    resolution: resolved                 # declared | resolved | unresolved | revoked
    diagnostic: ""                       # REQUIRED for unresolved | revoked — names the
                                         # missing or revoked target
```

Reciprocal entries: for hook-activated skills, the registry MUST emit the skill-side entry (`source_path: "skill.activation.hook_ref"`, `target_kind: hook`) reciprocal to the hook-side `activation_target` entry, so the relationship is discoverable from both ends ([ACIF-SKILL] §13.2). Install-tool refusal on `unresolved`/`revoked` is [ACIF-CORE] §10; the registry's obligation is the resolution and the diagnostic.

## 10. `source_uri`

### 10.1 Framing: provenance, never identity

`registry_section.source_uri` is a registry-scoped fetch pointer, scoped to `(fetched_at, body_hash)`. It MUST NOT be an input to `body_hash`, `metadata_hash`, or any UUID derivation, and MUST NOT be used as a cross-registry join key — cross-registry identity is `body_hash`; grouping is `inferred_pack_id`. Two conforming registries MAY record different `source_uri` values for byte-identical content.

Content with no https-dereferenceable URL is out of scope for conforming 0.1 records; no sentinel value exists.

### 10.2 Validity and scheme

The emitted `source_uri` MUST be a valid RFC 3986 absolute URI with a non-empty authority (violation: `acif.source_uri.malformed`; absence of the field: `acif.source_uri.missing`). The scheme MUST be a member of a closed allowlist whose 0.1 content is exactly `{https}` (violation: `acif.source_uri.scheme_forbidden`; `javascript:`, `data:`, `file:`, `vbscript:`, and `blob:` are rejected by construction). Userinfo MUST NOT be present (`acif.source_uri.userinfo_present` — this also rejects scp-style `git@` forms, which additionally fail RFC 3986 parsing as `malformed`). The host is recorded in A-label form; an unconvertible internationalized name is `malformed` (a full IDNA2008 profile is a roadmap item). Roadmap-reserved scheme candidates (`oci`, `ipfs`, private-origin `http` with an explicit insecure-origin flag) are not valid in 0.1.

### 10.3 Normalization pipeline (order normative)

The registry MUST apply exactly this pipeline, in exactly this order, before emitting:

1. Parse as RFC 3986; reject `malformed` on failure.
2. Reject on userinfo.
3. Case normalization (RFC 3986 §6.2.2.1): lowercase scheme and host; uppercase percent-encoding hex digits. **Path case is preserved, never folded.**
4. Scheme gate (§10.2 allowlist).
5. Percent-decode unreserved characters (RFC 3986 §6.2.2.2).
6. Dot-segment removal (RFC 3986 §6.2.2.3). *(Steps 5 before 6 is load-bearing: `%2E%2E` must decode and then collapse; the reversed order leaves encoded dot-segments in emitted records — a cross-registry divergence with a path-traversal flavor.)*
7. Scheme-based normalization (RFC 3986 §6.2.3): strip default port `:443`; empty path becomes `/`.
8. Remove any fragment.
9. Query prohibition: the emitted value MUST NOT contain a query (`acif.source_uri.query_present`); a dangling `?` is removed. *(Informative: this eliminates the credential class — signed tokens, presigned parameters — by construction; origins whose fetch requires a query are unrepresentable in 0.1, with publisher-declared paths as the roadmap home.)*
10. Single-file trailing-slash check (§10.5).

The pipeline MUST be idempotent: `normalize(normalize(u)) == normalize(u)` byte-for-byte. This pipeline and the pack-inference URL canonicalization ([ACIF-PUBLISHER] §9.3) are different pipelines for different contracts and MUST NOT share an implementation.

### 10.4 Redirect semantics: canonical resolution, not final-URL

While fetching, the registry follows redirects but records by these rules:

- A **permanent** redirect (301, 308) is an origin asserting an identity move: record the redirect target.
- A **temporary** redirect (302, 303, 307) is delivery mechanics: record the **requested** URL; a redirect-injected signed query is never persisted.
- Every hop MUST be https (`acif.source_uri.redirect_downgrade`).
- The chain is bounded by `ACIF_SOURCE_URI_MAX_REDIRECTS = 10`; exceeding it, or a loop, is `acif.source_uri.redirect_limit`.
- At record time, the recorded value MUST NOT re-dereference to a permanent redirect.

**Re-crawl stability invariant:** if `body_hash` is unchanged and no permanent redirect was observed, `source_uri` is byte-identical across crawls. *(Informative: this is what makes byte-for-byte conformance vectors authorable and `fetched_at` legible; recording final URLs would churn the field on every load-balancer and signed-asset rotation.)*

### 10.5 Direct-file URLs

For items whose body classifies single-file ([ACIF-CORE] §7.2), the path MUST NOT end in `/` (`acif.source_uri.direct_file_trailing_slash`), and the last path segment — post-pipeline, case-sensitive — is the URL-derived filename feeding tier-2 fallback discovery ([ACIF-SKILL] §9) deterministically. On conflict between the URL-derived name and a frontmatter-declared name, the registry MUST record **both** and emit `acif.source_uri.filename_conflict` — never silently override. Multi-file items point at a directory root; a trailing slash is legitimate and no filename semantics apply.

### 10.6 `source_status`

OPTIONAL, set at crawl time: `live | moved | gone | unreachable` — `moved` on an observed permanent redirect, `gone` on a definitive origin 404/410, `unreachable` on transport-level failure. Dead links become a consumer signal instead of silent staleness.

## 11. Freshness

### 11.1 Three clocks, never blended

Freshness and attestation validity are orthogonal axes that are never combined, and three clocks exist:

1. **Item-sidecar clock** (`fetched_at`/`expires`) — the ONLY input to item staleness.
2. **Attestation clock** — the external system's validity window, evaluated by consumers under that system's own rules; never a staleness input.
3. **Response-envelope clock** (`generated_at`/`max_staleness`) — response assembly metadata. Computing item staleness from `generated_at` is **non-conforming** (response assembly can be arbitrarily later than crawl).

No combined effective-staleness scalar exists; attestation validity is never folded into `expires`; no single trust ordering between stale-but-attested and fresh-but-unattested is published — a policy MAY require fresh, attested, both, or neither. *(Informative: both checks run independently, so neither axis can mask the other — most-restrictive-wins behavior without any combined value existing.)*

### 11.2 The staleness predicate

An item is **stale** at consumer time `T` (UTC) iff `T > E_sidecar`, where `E_sidecar = expires` when present, else `fetched_at + 72h`. `fetched_at` is REQUIRED, so the predicate is total. All freshness fields MUST be RFC 3339 timestamps with an explicit offset; an offsetless timestamp is malformed. Clock-skew tolerance, if an implementation applies any, MUST be explicit, bounded, and fail-closed: a borderline instant evaluates stale. *(Informative: fail-closed is the conformance-tested property of the three — TV-FRESH (g); "explicit" and "bounded" describe how a tolerance must be declared, not independently vectorable behavior.)*

`expires < fetched_at` is a malformed window: `acif.registry.expires_before_fetched_at` (fix-forward). It is distinct from an `expires` legitimately already in the past, which is well-formed, evaluates stale, and is conforming to serve — an honest crawl backlog is not an error.

### 11.3 The attestation axis

The attestation trust tier is `{attested, unattested}`, consumer-evaluated. A lapsed, unreachable, or unverifiable attestation degrades the tier and MUST NOT set the staleness bit — content bytes are unchanged; losing attestation means the extra assurance cannot be proven, never that content went stale. The registry MUST NOT parse the external attestation manifest, MUST NOT bake any combined value, and its item response MUST be **byte-identical whether or not the attestation system is reachable**. Fresh-but-unattested is the normal state: no warning, no error.

### 11.4 Consumer lanes

Staleness is a state flag on the warn lane: consumers SHOULD warn on stale items; install MAY proceed. Install tools MUST provide an operator opt-in that escalates staleness to refuse. Silent-block by default and silent-ignore are both non-conformant. *(Informative: the stale-plus-attested combination warrants the stronger consumer diagnostic — staleness is the window in which an upstream-revoked attestation can still read valid; a content-revocation feed keyed on `body_hash` is the roadmap item.)*

## 12. Error Identifiers

| Identifier | Class | Condition |
|---|---|---|
| `acif.source_uri.missing` | reject (record-emit) | No `source_uri` on an emitted record (§10.2) |
| `acif.source_uri.malformed` | reject (record-emit) | Not a valid RFC 3986 absolute URI with authority; unconvertible IDN host (§10.2) |
| `acif.source_uri.scheme_forbidden` | reject (record-emit) | Scheme outside the closed allowlist (§10.2) |
| `acif.source_uri.userinfo_present` | reject (record-emit) | Userinfo component present (§10.2) |
| `acif.source_uri.query_present` | reject (record-emit) | Query present in the emitted value (§10.3) |
| `acif.source_uri.redirect_downgrade` | reject (record-emit) | Non-https hop in the redirect chain (§10.4) |
| `acif.source_uri.redirect_limit` | reject (record-emit) | Redirect chain exceeds 10 hops, or loops (§10.4) |
| `acif.source_uri.direct_file_trailing_slash` | reject (record-emit) | Single-file item URL path ends in `/` (§10.5) |
| `acif.source_uri.filename_conflict` | diagnostic (MUST-emit) | URL-derived filename ≠ frontmatter-declared name; both recorded (§10.5) |
| `acif.registry.expires_before_fetched_at` | reject (record-emit) | Malformed freshness window (§11.2) |

Reject-class identifiers here bind the registry at the record-emit boundary: a record failing the condition MUST NOT be emitted as conforming. All are fix-forward ([ACIF-CORE] §8.7).

## 13. Security Considerations

**The registry is a chosen trust root.** Everything in `registry_section` is the registry's assertion. This document constrains those assertions to be deterministic and testable (the pipeline, the invariant, the clock separation) precisely so consumers can hold registries to them; nothing here makes a registry honest.

**`attestation_hash` is a slot, not a system.** ACIF names no external integrity system and evaluates no attestation. The byte-identical-response rule (§11.3) exists so an attestation-service outage cannot flip a served index stale — and so no registry can quietly couple its availability to a third party's.

**The query prohibition is credential hygiene by construction.** Signed URLs, capability tokens, and presigned parameters cannot appear in conforming records (§10.3), and temporary-redirect targets — where signing injections live — are never persisted (§10.4).

**The identity firewall prevents provenance capture.** Because `source_uri` never feeds identity or joins (§10.1), a registry that records a mirror URL cannot fork an item's identity, and a hostile origin cannot poison cross-registry deduplication — identity stays with `body_hash`.

**Staleness is the revocation gap.** A stale record whose upstream has revoked or replaced content still serves the old bytes honestly (`body_hash` still matches those bytes). The freshness lanes surface the window; closing it requires the roadmap revocation feed.

**Self-asserted metadata rules apply.** Everything in [ACIF-CORE] §11 and [ACIF-PUBLISHER] §11 applies to what registries observe and re-serve.

## 14. References

### 14.1 Normative

- [ACIF-CORE] "ACIF Core Specification", version 0.1.x. `../core/spec.md`
- [ACIF-PUBLISHER] "ACIF Publisher Record Specification", version 0.1.x. `../publisher-spec/spec.md`
- [ACIF-HOOK] / [ACIF-SKILL] / [ACIF-RULE] / [ACIF-COMMAND] / [ACIF-AGENT] / [ACIF-MCP] — the six L1 interchange specifications, version 0.1.x, sibling directories under `specs/`.
- [RFC2119] Bradner, S., "Key words for use in RFCs to Indicate Requirement Levels", BCP 14, RFC 2119, March 1997. <https://www.rfc-editor.org/rfc/rfc2119>
- [RFC3339] Klyne, G., Newman, C., "Date and Time on the Internet: Timestamps", RFC 3339, July 2002. <https://www.rfc-editor.org/rfc/rfc3339>
- [RFC3986] Berners-Lee, T., Fielding, R., Masinter, L., "Uniform Resource Identifier (URI): Generic Syntax", STD 66, RFC 3986, January 2005. <https://www.rfc-editor.org/rfc/rfc3986>
- [RFC8174] Leiba, B., "Ambiguity of Uppercase vs Lowercase in RFC 2119 Key Words", BCP 14, RFC 8174, May 2017. <https://www.rfc-editor.org/rfc/rfc8174>

### 14.2 Informative

- [ACIF-RENDER] "ACIF Render-Back Specification", version 0.1.x. `../render-back/spec.md`.
- [SHAPE] ACIF design record: `SHAPE.md`, `panel/source-uri-consensus.md`, and `panel/freshness-consensus.md` in the ACIF repository — decision provenance (Decisions #13, #17, #26, #27, #28, #32, #34).

---

## Appendix A — Conformance Test-Vector Families (Normative)

The vectors in these families, published in the `conformance/` directory, are normatively authoritative over prose.

**TV-URI-\*** — two harness surfaces, both required; conformance MUST NOT be claimed on the static vectors alone. *Static string vectors:* (a) case normalization — `HTTPS://GitHub.IO/A%3ab` → `https://github.io/A%3Ab` (scheme+host folded, percent-hex uppercased, path case preserved); (b) decode-unreserved — `a%2Db%7Ec` → `a-b~c`; (c) reserved-not-decoded — `%2F` unchanged; (d) ordered encoded-dot-segment — `/x/%2E%2E/y` → `/y` (pins decode-then-collapse); (e) literal dot-segments — `/a/./b/../c` → `/c`; (f) default-port removal — `:443` stripped, `:8443` kept; (g) empty path → `/`; (h) fragment stripped; (i) query prohibition — `?token=x` → `acif.source_uri.query_present`; dangling `?` removed; (j) scheme gate — `http://` → `scheme_forbidden`; `git@github.com:o/r.git` → `malformed`; `javascript:`/`data:`/`file:` → `scheme_forbidden`; (k) userinfo → `userinfo_present`; (o) direct-file last segment — single-file item at `.../my-skill.md` ⇒ tier-2 fallback name `my-skill`; (o′) filename conflict — URL-derived ≠ frontmatter name ⇒ both recorded + `filename_conflict`; (p) single-file trailing slash → `direct_file_trailing_slash`; (q) multi-file directory URL — trailing slash conformant, no filename semantics; (r) idempotency — `normalize(normalize(u)) == normalize(u)` byte-for-byte; (s) hash exclusion — identical body, different `source_uri` ⇒ identical `body_hash` AND `metadata_hash`. *Mock-transport vectors:* (l) permanent resolution — 301 ⇒ target recorded; (l′) temporary preservation — 302 to a signed URL ⇒ requested URL recorded, signed query never persisted; (m) downgrade — any `http://` hop → `redirect_downgrade`; (n) chain > 10 or loop → `redirect_limit`; (t) re-crawl stability — same body twice through a temporary-redirect chain ⇒ byte-identical `source_uri`; (u) *(conditional)* `source_status` shape — if emitted, value ∈ `{live, moved, gone, unreachable}`.

**TV-FRESH-\*** — static vectors with an injected consumer clock `T`, plus one mock-crawl vector: (a) sidecar past + attestation valid → stale, tier attested, default policy warns (not refuses), no combined scalar anywhere in the record; (b) sidecar fresh + attestation lapsed → fresh, tier degrades to unattested, staleness bit NOT set; (c) `attestation_hash` present + manifest unreachable → tier unattested, freshness unaffected, response **byte-identical** to the reachable case; (d) `expires` absent → `fetched_at + 72h`; `T` at +71h fresh, +73h stale; (e) `expires < fetched_at` → `acif.registry.expires_before_fetched_at`, vs. already-past `expires` → well-formed, stale, conforming to serve; (f) offsetless timestamp in any freshness field → malformed; (g) fail-closed skew — `T` within declared tolerance of `E_sidecar` ⇒ stale; (h) lanes — stale + default policy → warn + state flag, install proceeds; operator opt-in → refuse; (i) fresh-but-unattested → no warning, no error; (j) *(mock-crawl)* unchanged `body_hash`, `fetched_at` advanced → fresh again on the crawl axis while a lapsed attestation still degrades the tier; (k) staleness computed from `generated_at` → non-conforming.

**TV-L3 additions** *(promotion-time)*: (a) tuple endpoint shape — `(item_id, body_hash, metadata_hash_if_present, version_if_declared)`; `metadata_hash` null exactly when `publisher_section` absent; (b) `install_scope_capabilities` entry without a `source` tag → non-conformant; (c) advisory entry without a `method` stamp → non-conformant.

Individual vector IDs are assigned in the conformance suite.

## Appendix B — Provenance and Preserved Positions (Informative)

Promoted 2026-07-11 from the ACIF design record: the registry-section schema and Decisions #13, #17, #26, #27, #28, #32, and #34 of `SHAPE.md`, with deliberation records in `panel/source-uri-consensus.md` and `panel/freshness-consensus.md` (the project's two-reviewer mini-review format).

Preserved positions recorded for future revision: post-redirect **final-URL recording was considered and rejected** on operational scale evidence (signed expiring asset URLs, delivery-host churn, geographic divergence) — if a future revision revisits redirect semantics, that evidence is the bar to clear; spec-purist's freshness dissent — an OPTIONAL informative `attestation_valid_until` mirror for offline consumers, with his absence semantics as the recorded design and the constraint that it MUST NOT be a staleness input — is the roadmap valve; the `min(sidecar, attestation)` blended-expiry strawman was rejected from both directions (unimplementable and operationally vacuous-or-storm) and its rejection is load-bearing for §11.

Newly minted at spec-promotion time (not present in the design record; flagged for review): the §7 tuple-endpoint amendment adding `metadata_hash_if_present` (Decision #17 defined the tuple before the [ACIF-CORE] §7.8 coverage model existed; without the member, declared-metadata re-targets are invisible on the one polled surface — the spec-purist hash-boundary consult recommended the addition); the §8.5 rule that a provenance-tag-less `install_scope_capabilities` entry is non-conformant (the design record described the tag without the reject); the §8.3 rule that an advisory entry without a method stamp is non-conformant; and the TV-L3 vectors. These items were ratified back into the design record (SHAPE.md, Spec-Promotion Ratifications section) at promotion time.
