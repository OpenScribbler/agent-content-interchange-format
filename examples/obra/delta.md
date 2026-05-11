# DRAFT

# Delta: Hook Trace vs. Skill Trace

Comparing `hook-session-start.md` and `skill-tdd.md` to surface asymmetries in the
spec design and fields that appear naturally in the obra trace but aren't yet described
in the README's L2/L3 sections.

---

## 1. Does L2 frontmatter vs. sidecar create any asymmetry in what metadata is expressible?

**Yes, and it's significant.**

The frontmatter/sidecar split was motivated by a structural constraint: provider
harnesses own `settings.json` and `mcp.json`, so hooks and MCP configs can't embed
metadata inline. Skills can, so they use frontmatter. The rule is sensible.

But the obra trace reveals the asymmetry goes deeper than "where the bytes live":

### Frontmatter inherits implicit structure from the file it annotates

When the `SKILL.md` frontmatter says `name: test-driven-development`, the registry
knows without any additional context that this is the name of the skill described
by this file. The metadata and the content live in the same file — they are
colocated by design. The `name` field can't accidentally point to the wrong item.

A sidecar `session-start.hook.yaml` doesn't have this implicit binding. The
registry must determine which hook definition the sidecar describes. In
obra/superpowers there's only one hook, so the link is unambiguous. But a repo
with five hooks needs five sidecars, and each sidecar needs a way to declare
which hook it annotates. The spec hasn't defined this binding mechanism.

**Gap:** The L2 sidecar spec needs a field (or naming convention) that links the
sidecar to the specific hook definition it annotates.

Candidate approaches:
- Naming convention: `{event}.hook.yaml` → `session_start.hook.yaml` always
  annotates the `session_start` hook. Fragile for repos with multiple hooks
  on the same event.
- Explicit field: `annotates: session-start` (links by item name). Requires
  the item name to already exist.
- Path convention: the sidecar lives in the same directory as the hook file it
  annotates. Works for single-file hooks but unclear for multi-file hooks.

### Frontmatter supports incremental adoption; sidecars require a whole new file

A publisher with an existing `SKILL.md` can add `version: "5.1.0"` to the
existing frontmatter in 10 seconds. L2 adoption for skills requires editing
one existing file per skill.

L2 adoption for hooks requires creating a new file per hook. That's a higher
friction ask. If obra/superpowers has one hook, that's one sidecar. A repo
with ten hooks needs ten new files. The spec's "publishers do as little as
possible" principle pushes toward making sidecars optional and well-specified
enough that registries can auto-generate them.

### What fields are expressible in frontmatter but not in a sidecar, or vice versa?

In practice, both carriers can express the same field vocabulary — YAML is YAML.
The asymmetry is not in expressibility but in authoring ergonomics and binding.
Frontmatter is tighter because it's colocated; sidecars are looser because they
can annotate content the publisher didn't author (e.g., a registry can drop a
sidecar alongside content that has no metadata at all).

This is actually a useful property of sidecars: a registry implementing the
Debian overlay pattern can generate a `.hook.yaml` sidecar for third-party
content without touching the original files. Frontmatter can't be overlaid
without modifying the original file. The spec should note this distinction
explicitly: sidecars support registry overlay; frontmatter does not.

---

## 2. Does the registry entry schema need to differ between content types, or is it uniform?

**The core fields are uniform; the type-specific fields diverge.**

Fields present in both the hook and skill registry entries:
- `id`
- `content_type`
- `content_hash` (algorithm + value)
- `source_repo`
- `source_path`
- `discovered_at`
- `publisher_metadata_source`
- `name`
- `version`
- `description`
- `license`
- `author`
- `homepage`
- `verified_at`
- `package_name`

Fields present only in the hook entry:
- `event` — canonical HIF event name
- `entry` — the primary script file
- `auxiliary_files` — `run-hook.cmd` and similar required support files
- `blocking` — hook blocking behavior
- `providers` — explicit multi-provider support list
- `capabilities` — HIF capability identifiers

Fields present only in the skill entry:
- `keywords`
- `supplementary_files` — secondary `.md` files in the skill directory

**Recommendation:** Define a common L3 schema with a `content_type` discriminant
and allow type-specific extension objects. Something like:

```yaml
# Common envelope
id: ...
content_type: hook | skill | rule | command | agent | mcp_config
content_hash: ...
source_repo: ...
discovered_at: ...
# ... (common fields)

# Type-specific extension block
hook:           # present when content_type == hook
  event: ...
  entry: ...
  blocking: ...
  auxiliary_files: [...]
  capabilities: [...]

skill:          # present when content_type == skill
  keywords: [...]
  supplementary_files: [...]
```

This is cleaner than flattening type-specific fields into the common envelope,
which would produce a sparse record for any given content type.

---

## 3. Fields that appear naturally in the obra trace but aren't in the README's L2/L3 descriptions

The README describes L2 as covering: "version label, dependencies, runtime
requirements, license, content type, capabilities." The README describes L3 as
covering: "indexes content from publisher repos, computes `content_hash` over
canonical bytes, auto-generates publisher metadata, serves content."

Fields found in the obra trace that the README doesn't mention:

### `entry` (hook-specific)

Which file in a multi-file hook is the primary executable? obra/superpowers
has `session-start` (script), `run-hook.cmd` (wrapper), `hooks.json` (Claude
format), `hooks-cursor.json` (Cursor format). The registry needs to know which
is the item's "entry point" for L4 render-back and for content hash boundary
decisions. Neither L2 nor L3 in the README mentions this.

### `auxiliary_files` / `supplementary_files`

Both content types have secondary files that are required for correct behavior:
- Hook: `run-hook.cmd` is required on Windows; omitting it means silent failure
- Skill: `testing-anti-patterns.md` is cross-referenced from `SKILL.md`

The README doesn't describe this concept at all. Without it, the content hash
boundary is underspecified, and install tools might deliver incomplete content.

### `providers` / provider compatibility

The README mentions L4 render-back ("one canonical hook → hooks.json +
hooks-cursor.json") but says nothing about publisher-declared provider support.
The obra trace shows the hook explicitly supports `claude-code`, `cursor`, and
`copilot-cli` (via runtime detection), but NOT `gemini-cli`. A registry that
tries to render-back for Gemini would produce incorrect output.

Publishers need a way to declare "this hook works on providers X, Y, Z" and
"this skill is meaningful only for providers that support the Skill tool."

### `package_name` / package context

obra/superpowers is a package. Its 14 skills and 1 hook are distributed together
and versioned together. Individual registry entries for `test-driven-development`
and `session-start` should carry a `package_name: superpowers` or similar field
so an install tool can say "install superpowers" and get all items, or "install
obra/superpowers/test-driven-development" and get one skill.

The README describes content at item granularity but doesn't describe the
package/bundle concept at all. obra/superpowers surfaces this gap directly.

### `source_path` (directory vs. file)

For the skill, `source_path` is `skills/test-driven-development/SKILL.md`
(or `skills/test-driven-development/` for the directory). For the hook,
`source_path` is `hooks/` — a directory, not a single file. The README says
"indexes content from publisher repos" but doesn't specify whether source_path
is file-granular or directory-granular. The ora trace shows both are needed,
and the answer differs by content type.

### `publisher_metadata_source` (registry transparency)

Neither the README's L2 nor L3 description mentions telling downstream consumers
whether the metadata was publisher-supplied or registry-generated. This matters
because auto-generated metadata is less reliable. An install tool making trust
decisions needs to know if it's reading publisher intent or registry inference.

---

## 4. Summary: what the obra trace reveals about the spec design

| Issue | Hook trace | Skill trace | Spec gap |
|-------|-----------|-------------|----------|
| Sidecar binding mechanism | Unclear how sidecar links to hook definition | N/A (colocated) | L2 needs sidecar-to-item binding rule |
| Multi-file content hash boundary | `hooks/` directory: 4 files, unclear which are in scope | `test-driven-development/`: 2 files, both in scope | L3 needs explicit hash boundary rules per content type |
| Per-item vs. package versioning | Package version only (`5.1.0`) | Package version only (`5.1.0`) | L2/L3 need versioning model: inherit or per-item |
| Auxiliary / supplementary files | `run-hook.cmd` required, not declared | `testing-anti-patterns.md` referenced, not declared | Both L2 specs need a mechanism for secondary files |
| Provider compatibility | Explicit (3 providers supported, 1 not) | Implicit (skills/ listed in 3 of 4 plugin manifests) | L2 needs provider compatibility field for both types |
| Package/bundle concept | No per-item mechanism; all items are in `superpowers` | Same | L3 needs package-level grouping in the index |
| Discovery mechanism | From plugin manifest `.hooks` field | From plugin manifest `.skills` field + naming convention | L3 auto-discovery rule not yet defined |
| Overlap with existing plugin manifests | `.claude-plugin/plugin.json` carries most package metadata | Same | Spec needs merge/precedence rule vs. existing manifests |
