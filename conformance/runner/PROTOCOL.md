# ACIF Conformance Adapter Protocol

**`adapter_protocol: 1`** — this document is the public contract an
adapter is built against. The runner's protocol layer implements this
document; where they disagree, this document governs and the runner has
the bug ([DESIGN.md] §1). Requirements language per BCP 14.

An **adapter** is an executable that exposes an implementation under test
(IUT) to the runner. It is expected to be a dev-only shim linking the
IUT's internal libraries — not the shipping binary. Its source MUST be
published for a report used as graduation evidence ([DESIGN.md] §8).

## 1. Transport and lifecycle

- The runner spawns the adapter once per run and speaks line-delimited
  JSON: one request object per line on stdin, one response object per
  line on stdout, strictly in order, exactly one request in flight at a
  time. stderr is free-form log passthrough, never parsed.
- Encoding is UTF-8 without BOM. A line MAY be up to 16 MiB; adapters
  MUST NOT rely on default line-buffer sizes.
- The adapter MUST be stateless across requests. Where a test sequences
  multiple passes (mock-crawl), all cross-pass state arrives in the later
  request.
- Per-request timeout: 30 seconds. Expiry, a crash, or a malformed
  response line is scored `harness-error` on the vector being run.
- Unknown fields in a request MUST be ignored by the adapter; unknown
  fields in a response are ignored by the runner. Additive fields never
  bump `adapter_protocol`; changes to required fields or response
  semantics do. The runner refuses to run (run-level harness error) on an
  `adapter_protocol` it does not implement.

## 2. Handshake

First request, always:

```json
{"op": "hello", "runner_protocol": 1}
```

Response:

```json
{"ok": true, "result": {
  "implementation": "<IUT name>",
  "version": "<IUT version string>",
  "adapter_protocol": 1,
  "scopes": ["core", "hook"]
}}
```

`scopes` is the set of conformance scopes the IUT claims, drawn from the
closed enum: `core`, `hook`, `skill`, `rule`, `command`, `agent`, `mcp`,
`publisher`, `registry`, `render`. Scope prerequisites and the normative
scope→vector mapping live in `scopes.yaml` beside the runner
([DESIGN.md] §8). Claim strings use these tokens verbatim.

## 3. Requests and responses

Every request after the handshake is:

```json
{"op": "<operation>", "input": { … }}
```

Requests carry no vector identifier, by design. Every response is exactly
one of:

```json
{"ok": true, "result": { … }}
{"ok": false, "error": "acif.<family>.<condition>", "diagnostics": [ … ]}
{"unsupported": true}
```

Rules:

- `error` MUST match `^acif\.[a-z0-9_]+(\.[a-z0-9_]+)+$` and MUST be a
  spec-minted identifier. Error vectors assert on it exact-string. Any
  other `error` value is scored `harness-error` (adapter-internal error) —
  this is the reserved channel for the adapter's own top-level exception
  handler, and adapters SHOULD emit e.g. `"error": "adapter: <detail>"`
  deliberately on internal failure.
- **Non-conformance verdicts on record-validation forms**: return
  `{"ok": true, "result": {"conformant": false, "reason": "<text>"}}`.
  Under `adapter_protocol: 1`, `reason` is never asserted — this is
  frozen per the adapter's declared handshake protocol, never changed
  retroactively. The specs mint `reject (verdict)`-classed identifiers
  for these conditions ([ACIF-CORE] §8.7; Appendix B maps every vector
  site to its identifier); a future `adapter_protocol` revision asserts
  `reason` exact-string against them, for adapters declaring that
  revision only. *(Informative migration guidance, not an
  `adapter_protocol: 1` conformance criterion: emit the minted
  identifier as the `reason` value now and the flip is a no-op. The
  normative source for which identifier a condition takes is the owning
  spec's condition text, not Appendix B — an adapter never sees vector
  ids.)* A conforming input judged conformant returns
  `{"ok": true, "result": {"conformant": true, …}}` alongside any other
  asserted fields.
- `unsupported` is **per-request**: it means the adapter cannot serve
  this request *form* (not merely this op). It is a development
  convenience; any scope whose required set contains the vector is
  unclaimable in that run.
- Field discipline: the runner asserts exactly the fields the vector's
  `expect` block requires. Extra fields in `result` are ignored. An
  asserted field absent from `result` is a `fail`, never `unsupported`.
  Absence assertions are checked as absence.

### 3.1 Diagnostics

A diagnostic is a structured object, never a bare string:

```json
{"id": "acif.<family>.<condition>", "params": { … }}
```

`params` keys for every identifier whose payload the vectors assert are
pinned in Appendix A; the runner's Appendix-A payload-pin self-check
verifies Appendix A covers every payload-asserting vector, and that every
pinned row has its asserting vector. Matching discipline:
every expected diagnostic MUST be present with its required params, and no
unexpected diagnostic from the same `acif.<family>` may appear on that
response.

### 3.2 Canonical bytes

Where a response carries canonical serialized form (`canonical_bytes`,
render `output`), the field is the exact [ACIF-CORE] §8.6 canonical-JSON
byte sequence (or the render target's emitted bytes) carried as a UTF-8
JSON string; the runner compares the re-encoded UTF-8 bytes byte-exact.
Hash fields (`body_hash`, `metadata_hash`, `response_hash`) are lowercase
hex SHA-256 digests carried without the `sha256:` prefix unless the spec
field itself carries one; compared exact-string.

## 4. Operations

`input.kind` values use the [ACIF-CORE] §5.1 `kind` enum. Timestamps are
RFC 3339 UTC strings. UUIDs are lowercase canonical form.

### 4.1 `ingest`

One ingestion pass: classification, canonicalization, hashing,
publisher-section extraction, diagnostics. Request `input`:

| Field | Req | Meaning |
|---|---|---|
| `kind` | yes | content type under ingestion |
| `body_root` | when a body exists | absolute path to the materialized body directory ([DESIGN.md] §3.4) |
| `entry_file` | with `body_root` where the type has one | body-root-relative entry file |
| `provider_config` | for provider-native sources | `{"provider": "<tag>", "path": "<name>", "content": <parsed JSON/YAML value or verbatim string>}` |
| `sidecar` | for ACIF-authored sources | the sidecar document as a JSON value |
| `context` | no | ingestion context: `pack_id`, `inferred_pack_id`, `source_root` semantics, `install_target_os`, etc. — keys defined per assertion need, ignored when unrecognized |

Response `result` (assert-relevant fields; all optional per §3 field
discipline):

| Field | Meaning |
|---|---|
| `canonical` | the canonical record as a JSON value |
| `canonical_bytes` | §3.2 canonical serialization, when byte-exact assertion applies |
| `body_hash` | body hash per [ACIF-CORE] §7 |
| `metadata_hash` | metadata hash per [ACIF-CORE] §7.8 |
| `publisher_section` | faithfully-observed publisher section |
| `classification` | `single-file` \| `multi-file` per [ACIF-CORE] §7.2 |
| `conformant` / `reason` | §3 verdict transport, for record-validation forms |
| `installable` | boolean install-disposition summary on record-validation forms (e.g. a pack-less item is first-class: `conformant: true, installable: true`) |
| `diagnostics` | §3.1 |

Pack-manifest form: `kind: "pack"` with `manifests` (array of
`{"source": "<manifest filename>", …provider manifest fields}`) requests
pack-identity reconciliation ([ACIF-PUBLISHER] §9.1) →
`result`: `canonical_source`, `canonical_display_name`, `diagnostics`
(`acif.publisher.pack_source_conflict` with Appendix A params on
conflict).

Rejections use the error response with the spec-minted identifier
(`acif.body.symlink`, `acif.body.path_collision`, `acif.body.empty`,
`acif.hook.script_file_missing`, `acif.hook.script_path_invalid`, …).

### 4.2 `derive_pack_id`

UUIDv5 pack-identity inference ([ACIF-PUBLISHER] §9.4).
`input`: `namespace`, `repository_url`, `display_name` →
`result`: `inferred_pack_id`.

### 4.3 `resolve_pack`

Pack-membership resolution ([ACIF-PUBLISHER] §8.3).
`input`: `item` (with `publisher_section` / `registry_section`),
`known_packs` (array of pack records; MAY be empty) →
`result`: `pack_resolution` (`declared` | `inferred` | `unresolved` |
`none`), `member_of` (UUID, when resolved), `install` (the install
disposition string the vectors assert, e.g.
`refuse-unless-operator-opt-in`).

### 4.4 `evaluate_requires`

Three-valued `requires` evaluation ([ACIF-CORE] §9).
`input`: `item_requires` (the `requires` slot as declared),
`consumer_recognizes` (array of capability keys the consumer knows) →
`result`: `evaluation` (per-key or overall, as declared by the spec's
three-valued model), `install` (disposition string).

### 4.5 `evaluate_freshness`

Staleness and trust-tier computation ([ACIF-REGISTRY] §11).
`input`: `record`, `consumer_clock`, optional `policies`,
`attestation_evaluation`, `declared_tolerance_seconds` →
`result`: `staleness`, `trust_tier`, `warnings` (array of §3.1
diagnostics; a stale evaluation on the default lane carries
`acif.registry.stale` with its Appendix-A-pinned `expires` param),
`response_hash` (lowercase hex SHA-256 of the served item
response bytes — the [ACIF-REGISTRY] §11.3 byte-identity probe; IUTs that
do not serve item responses answer `unsupported` for request forms that
require it).

### 4.6 `normalize_uri`

Static `source_uri` normalization pipeline ([ACIF-REGISTRY] §10.3).
`input`: `uri` → `result`: `source_uri` — or an error response
(`acif.source_uri.*`).

### 4.7 `fetch_uri`

Transport-form `source_uri` resolution ([ACIF-REGISTRY] §10.4–§10.6). The
IUT MUST perform real fetches through its own client stack.
`input`:

| Field | Meaning |
|---|---|
| `url` | the logical URL to fetch, as in the vector (`https://…`) |
| `trust_ca` | absolute path to the runner's per-run ephemeral CA bundle (PEM); the fetcher MUST trust exactly this bundle for the run |
| `resolve` | hostname → `"127.0.0.1:<port>"` map the fetcher MUST honor (the `curl --resolve` pattern); TLS SNI/verification still uses the logical hostname |

`result`: `source_uri` (the recorded canonical value), optional
`source_status` — or an error response (`acif.source_uri.*`, including
`acif.source_uri.redirect_downgrade` and `acif.source_uri.redirect_limit`). TLS negotiation itself is not
under test; the knobs exist so that scheme semantics are real, not
rewritten ([DESIGN.md] §6).

### 4.8 `derive_url_name`

Tier-2 URL-derived display name ([ACIF-REGISTRY] §10.5).
`input`: `uri`, `body_classification`, optional `frontmatter_name` →
`result`: `url_derived_name`, `diagnostics`.

### 4.9 `render`

Render-back to a provider target ([ACIF-RENDER]; per-type render
sections). `input`: `canonical`, `target` (provider tag), optional
`invocation` (render context) →
`result`: `output` (§3.2 bytes-as-string), `diagnostics` (§3.1 — includes
the degradation-pairing diagnostics), `lossy` (array of documented-lossy
tokens, e.g. `write-edit-distinction`).

### 4.10 `project`

Registry projection ([ACIF-REGISTRY] §8; per-type projection sections).
`input`: `item` (or canonical record), `projection` (which projection,
when the request is for one) → `result`: `projection` (the projected
value), or `conformant`/`reason` verdict transport for
projection-validation forms.

Pinned projection: `"projection": "script_selection"` evaluates the
per-OS selection rule ([ACIF-HOOK] §7.3) — `input` additionally carries
`targets` (array of OS enum members) →
`result`: `{"selection": {"<os>": "<selected path>" | "none"}, "diagnostics": […]}`
(`acif.hook.script_no_platform_match` on a no-match target).

Pinned projection: `"projection": "derived_capabilities"` evaluates the
per-type derivation predicates D_K ([ACIF-REGISTRY] §8.1; the L1 specs'
"DERIVABLE keys" sections) over the supplied record →
`result`: `{"derived_capabilities": {"<capability key>": true | false}}`.
The catalogs spell expected outcomes as the labels
`derivable-true` / `derivable-false`; bindings translate label ↔ boolean
(a derivation-noted translation, [DESIGN.md] §4) — the label vocabulary is
the vectors', the wire vocabulary is boolean.

### 4.11 `resolve_reference`

Cross-reference resolution ([ACIF-REGISTRY] §9).
`input`: `item`, `registry_state` (the known-items table the vector
supplies) → `result`: `cross_reference` (object or array),
`reciprocal_entries` (emitted reciprocal records, where asserted),
`install` (disposition string, where resolution outcome determines one).

Pinned `cross_reference` object schema: `source_path`, `declared_name`,
`target_kind`, `resolution` (`resolved` | `unresolved` | `revoked`),
`target_id` (when resolved; for name-declared references — UUID-authored
references MAY omit it, [ACIF-REGISTRY] §9). An unresolved or revoked
reference carries the §3.1 diagnostic `acif.registry.reference_unresolved`
([ACIF-REGISTRY] §12) whose `params` include `declared_name`.

### 4.12 `evaluate_install`

Install-time disposition over a record the vector supplies fully formed
([ACIF-HOOK] §11 coverage-gap rule; [ACIF-CORE] §10 / [ACIF-REGISTRY] §9
revoked-reference refusal). `input`: `item` (or canonical record),
optional `install_target_os` → `result`: `install` (disposition string,
e.g. `refuse-unless-operator-opt-in`, `proceed`), `diagnostics`.

### 4.13 `reconcile_frontmatter`

Publisher-side frontmatter CI reconciliation ([ACIF-PUBLISHER] §7).
`input`: `sidecar_value` (canonical declared values),
`source_frontmatter` (what the source file carries), `mode` (`default` |
`overwrite`) → `result`: `action` (`add-silently` | `leave-untouched` |
`block` | `overwrite`), `diagnostics`
(`acif.publisher.frontmatter_conflict` accompanies `block` and
`overwrite`-with-log outcomes).

## Appendix A — Pinned diagnostic params

Populated in lockstep with the bindings; the Appendix-A payload-pin
self-check fails if a vector asserts a diagnostic payload not pinned
here, or if a row here has no asserting vector.

Payload-pinned (a vector asserts params content):

| Identifier | Required params | Asserting vector |
|---|---|---|
| `acif.hook.script_platform_ambiguous` | `os` (colliding OS tag), `entries` (colliding entry indices, input order) | TV-PLATFORM-f |
| `acif.source_uri.filename_conflict` | `declared_name`, `url_derived_name` | TV-URI-o2 |
| `acif.publisher.pack_source_conflict` | `sources` (conflicting manifest filenames), `values` (conflicting values, same order) | TV-L2-f |
| `acif.rule.activation_degraded` | `mode_lost` (the canonical mode the render loses), `effective_behavior` (the target's effective loading behavior) | TV-RULE-m |
| `acif.registry.reference_unresolved` | `declared_name` (the declared reference string as written) | TV-AGENT-j |
| `acif.registry.stale` | `expires` (the effective `E_sidecar` as an RFC 3339 timestamp; compared as an instant, not byte-wise — any valid serialization of the instant passes) | TV-FRESH-a |
| `acif.registry.stale` | `expires` (as above; here `E_sidecar` is the computed default window, `fetched_at + 72h`) | TV-FRESH-h |

Identifier-only (vectors assert presence of the id; `params` MAY be empty
and is not asserted): `acif.command.placeholder_named_arg_collapsed`,
`acif.command.placeholder_untranslated`,
`acif.hook.platform_filename_inferred`,
`acif.hook.platform_filename_uninferable`,
`acif.hook.platform_override_dropped`,
`acif.hook.platform_shell_os_proxy`,
`acif.hook.script_no_platform_match`,
`acif.mcp.server_name_unconventional`,
`acif.publisher.frontmatter_conflict`,
`acif.source_uri.filename_conflict` (when asserted id-only),
`acif.rule.activation_mode_unmappable`.

Every identifier here is spec-minted; this table never mints. The
anti-softening self-check reconciles it against both the catalogs and the
specs' Error Identifiers sections.

Reserved param shapes (assertion deferred to the `adapter_protocol`
revision that asserts verdict reasons; pinned now so day-one emitters
carry the payload and the detail survives the flip):

| Identifier | Required params | Deferred asserting site |
|---|---|---|
| `acif.envelope.forbidden_field` | `field` (the offending reserved name) | TV-6 |
| `acif.requires.orphan_key` | `key` (the offending `requires` key) | the six §9.4 orphan-key vectors (Appendix B) |

## Appendix B — Verdict-reason identifier map (informative)

Flip mechanics for runner binding authors: every `{conformant: false}`
vector site, its current catalog reason string, and the spec-minted
identifier the flip will assert. This table is NOT the normative source
for adapter authors — an adapter never sees vector ids; it emits from the
owning spec's condition text ([ACIF-CORE] §5.1–§5.2, §8.7, §9.4;
[ACIF-REGISTRY] §8.3, §8.5, §11.2). The many-to-one rows are deliberate:
[ACIF-CORE] §9.4 defines one uniform reject, so six catalog strings map
to `acif.requires.orphan_key` — at the flip, the catalog strings survive
as informative annotations (they keep failure output legible) and the
per-case discrimination lives in each case's input key.

| Vector site | Catalog reason string | Minted identifier |
|---|---|---|
| TV-6 | `forbidden-field effective_version` | `acif.envelope.forbidden_field` |
| TV-11 case_1 | `kind-not-in-closed-enum` | `acif.envelope.kind_invalid` |
| TV-11 case_2 | `id-not-uuid-v4` | `acif.envelope.id_invalid` |
| TV-11 case_3 | `version-not-semver` | `acif.envelope.version_invalid` |
| TV-11 case_4 | `license-spdx-not-identifier` | `acif.envelope.license_spdx_invalid` |
| TV-L3-b | `missing-provenance-tag` | `acif.registry.provenance_tag_missing` |
| TV-L3-c | `missing-method-stamp` | `acif.registry.method_stamp_missing` |
| TV-FRESH-f | `rfc3339-explicit-offset-required` | `acif.registry.timestamp_offset_missing` |
| TV-FRESH-k | `response-envelope-clock-is-not-a-staleness-input` | *retired at the flip* — reframed as a behavioral `staleness: stale` assertion (the `implementation_behavior` confession input is dropped; no identifier is minted, because no conforming implementation can detect and report its own clock conflation) |
| TV-SKILL-b `foreign` | `foreign-type-key` | `acif.requires.orphan_key` |
| TV-SKILL-b `latent_match` | `latent-field-presence-does-not-soften` | `acif.requires.orphan_key` |
| TV-RULE-i case_1 | `considered-and-rejected-candidate` | `acif.requires.orphan_key` |
| TV-RULE-i case_2 | `derivable-key-never-requires` | `acif.requires.orphan_key` |
| TV-RULE-i case_3 | `foreign-type-key` | `acif.requires.orphan_key` |
| TV-COMMAND-j case_1 | `considered-and-disposed` | `acif.requires.orphan_key` |
| TV-COMMAND-j case_2 | `out-of-scope-key` | `acif.requires.orphan_key` |
| TV-COMMAND-j case_3 | `foreign-type-key` | `acif.requires.orphan_key` |
| TV-COMMAND-j case_4 | `latent-field-presence-does-not-soften` | `acif.requires.orphan_key` |
| TV-AGENT-c `on_agent` | `derivable-key-never-requires` | `acif.requires.orphan_key` |
| TV-AGENT-c `on_rule` | `foreign-type-key` | `acif.requires.orphan_key` |
| TV-MCP-g `on_mcp_item` | `derivable-key-never-requires` | `acif.requires.orphan_key` |
| TV-MCP-g `on_skill_item` | `foreign-type-key` | `acif.requires.orphan_key` |
| TV-HOOK-b | `derivable-key-never-requires` | `acif.requires.orphan_key` |
