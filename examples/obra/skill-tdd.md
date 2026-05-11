# DRAFT

# Trace: test-driven-development Skill — obra/superpowers

## Source

### skills/test-driven-development/SKILL.md (frontmatter + opening)

The full file is at `/home/hhewett/.local/src/superpowers/skills/test-driven-development/SKILL.md`.

Existing frontmatter (as published):

```yaml
---
name: test-driven-development
description: Use when implementing any feature or bugfix, before writing implementation code
---
```

That is the complete frontmatter. Two fields: `name` and `description`. No version, no
license, no author, no content type declaration.

The skill body is ~372 lines of Markdown prose: an overview section, the Iron Law, a
Red-Green-Refactor flowchart (embedded `.dot` source), worked examples with `<Good>`/
`<Bad>` tagged code blocks, a rationalization table, red-flag checklist, and a
verification checklist.

It also cross-references a sibling file:
```markdown
When adding mocks or test utilities, read @testing-anti-patterns.md to avoid common pitfalls:
```
The `@testing-anti-patterns.md` file lives in the same skill directory
(`skills/test-driven-development/testing-anti-patterns.md`). This `@` reference
is Claude Code shorthand for file inclusion — it is not a URL.

---

## L2 Publisher Metadata

Skills are `.md` files the publisher authors directly. L2 metadata is carried as
frontmatter augmentation — no sidecar required.

The augmented frontmatter the publisher would write for full L2 compliance:

```yaml
---
# Existing fields (publisher already writes these)
name: test-driven-development
description: Use when implementing any feature or bugfix, before writing implementation code

# L2 additions — what the spec would require or recommend

content_type: skill
# TBD: Is "skill" the canonical type name? The README says "skills" (plural) as a
# content category. The HIF spec says nothing about skill types. The L2 spec hasn't
# defined the content_type vocabulary yet.

version: "5.1.0"
# Sourced from package.json. There is no per-skill version — all skills in the
# package share the package version.
# TBD: Should L2 allow inheriting version from a sibling package.json?
# If not, the publisher must copy-paste the version into every SKILL.md frontmatter,
# which will drift.

license: MIT
# Sourced from package.json / .claude-plugin/plugin.json.
# Not present in current frontmatter.

author:
  name: Jesse Vincent
  email: jesse@fsck.com
# Sourced from .claude-plugin/plugin.json.
# Not present in current frontmatter.

homepage: https://github.com/obra/superpowers
# Sourced from .claude-plugin/plugin.json.

# Keywords / tags
keywords:
  - tdd
  - testing
  - workflow
  - methodology
# These would be publisher-supplied. Broader package keywords (from .claude-plugin/plugin.json):
# skills, tdd, debugging, collaboration, best-practices, workflows

# Dependencies — this skill references a sibling file
# TBD: Does L2 have a mechanism for intra-package dependencies?
# @testing-anti-patterns.md is not a separate registry item — it's a supplementary
# file within the same skill directory. The spec needs to say whether this is:
#   (a) an internal dependency (just content, not a separately installable item)
#   (b) a co-installed asset (registry delivers it alongside SKILL.md)
#   (c) out of scope (the publisher just puts it in the same directory)
supplementary_files:
  - testing-anti-patterns.md
# TBD: Field name not yet defined. "supplementary_files"? "assets"? "includes"?

# Provider compatibility
# TBD: Skills are used by Claude Code's Skill tool. The .codex-plugin/plugin.json
# references "./skills/" as does .cursor-plugin/plugin.json. But Gemini uses a
# different mechanism (GEMINI.md context file, no skills/ directory reference).
# Should L2 carry a providers list for skills too, or is "skill" implicitly
# provider-neutral?
---
```

**What the publisher would realistically add.** Jesse Vincent currently writes
`name` and `description`. Realistically, L2 would ask for `version`, `license`,
and `content_type`. Everything else (`author`, `homepage`, `keywords`) is
already in the plugin manifests and could be sourced by the registry from those
files without burdening the publisher.

**The same overlap problem as hooks.** Four plugin manifests carry `name`,
`version`, `author`, `license`, `keywords`. If L2 requires frontmatter to
repeat them, every skill's frontmatter becomes a maintenance burden that will
drift from `package.json`. The spec needs a clear merge precedence rule:
"frontmatter wins over package manifest for item-level fields; package manifest
supplies package-level fields when frontmatter is silent."

---

## L3 Registry Entry

### With L2 provided (publisher augmented frontmatter)

```yaml
# L3 registry index entry for obra/superpowers test-driven-development skill

id: obra/superpowers/test-driven-development
# TBD: Same ID scheme question as hooks. "org/repo/item-name".

content_type: skill

# Content hash computed by registry over canonical bytes
# For a skill with supplementary files, "canonical bytes" is ambiguous:
#   (a) Hash only SKILL.md (the primary file)
#   (b) Hash all files in skills/test-driven-development/ (SKILL.md + testing-anti-patterns.md)
# Option (b) is safer — a tampered testing-anti-patterns.md could mislead the agent
# even if SKILL.md is intact.
content_hash:
  algorithm: sha256  # TBD: algorithm not yet defined
  value: "TBD"       # placeholder — not computed

source_repo: https://github.com/obra/superpowers
source_path: skills/test-driven-development/SKILL.md
# TBD: source_path for a skill with supplementary files — is it the primary file
# or the directory? Recommend the directory so all files are covered.

discovered_at: "TBD"

# Publisher metadata — from frontmatter (publisher-provided)
publisher_metadata_source: publisher
name: test-driven-development
version: "5.1.0"
description: Use when implementing any feature or bugfix, before writing implementation code
license: MIT
author:
  name: Jesse Vincent
  email: jesse@fsck.com
homepage: https://github.com/obra/superpowers
keywords:
  - tdd
  - testing
  - workflow
  - methodology
supplementary_files:
  - testing-anti-patterns.md

# Registry-added fields
package_name: superpowers
verified_at: "TBD"
```

### Without L2 (registry auto-generation from existing frontmatter + package manifests)

obra/superpowers today ships `name` and `description` in skill frontmatter.
The registry can source additional fields from the plugin manifests.

```yaml
# Auto-generated L3 entry — only bare frontmatter present

id: obra/superpowers/test-driven-development
content_type: skill
# TBD: How does the registry know this is a "skill"? It could infer from:
#   (a) The file is named SKILL.md (naming convention)
#   (b) It's under a skills/ directory (path convention)
#   (c) The plugin manifest lists "skills": "./skills/"
# All three work for obra/superpowers but none is a universal rule.

content_hash:
  algorithm: sha256
  value: "TBD"

source_repo: https://github.com/obra/superpowers
source_path: skills/test-driven-development/SKILL.md
discovered_at: "TBD"
publisher_metadata_source: registry

# From existing frontmatter:
name: test-driven-development
description: Use when implementing any feature or bugfix, before writing implementation code

# Inferred from package manifests:
version: "5.1.0"
# From package.json .version

license: MIT
# From .claude-plugin/plugin.json .license

author:
  name: Jesse Vincent
  email: jesse@fsck.com
# From .claude-plugin/plugin.json .author

# Inferred from repository/plugin metadata:
homepage: https://github.com/obra/superpowers
keywords:
  - skills
  - tdd
  - debugging
  - collaboration
  - best-practices
  - workflows
# From .claude-plugin/plugin.json .keywords — package-level, not skill-specific

# Fields the registry CANNOT infer without L2:
# - supplementary_files: the registry can list the directory and find
#   testing-anti-patterns.md, but can't know if it's a declared dependency
#   or an accidentally co-located file.
# - content_type: requires naming convention or plugin manifest parsing
# - per-skill keywords (vs. package-level keywords)

verified_at: "TBD"
```

---

## Questions raised

### Q1: What is the content hash boundary for a multi-file skill?

`test-driven-development/SKILL.md` cross-references `testing-anti-patterns.md`
with `@testing-anti-patterns.md`. If only `SKILL.md` is hashed:
- A tampered `testing-anti-patterns.md` passes hash verification.
- An install tool that delivers only `SKILL.md` and not the supplementary file
  will produce a skill that references a missing file.

The content hash MUST cover all files in the skill directory, not just the
primary `SKILL.md`. But the spec doesn't define this. If hash coverage is
per-file, multi-file skills are insecure. The spec needs explicit language:
"for skills with a directory structure, the content hash covers all files in
the directory."

### Q2: The `@testing-anti-patterns.md` reference is Claude Code-specific syntax.

The `@file` inclusion syntax is a Claude Code feature. If another provider
(Cursor, Codex) installs this skill, the `@testing-anti-patterns.md` reference
may not work. The L2 spec could let publishers declare whether supplementary
files are required (the skill breaks without them) or optional (referenced but
degraded gracefully on unsupported providers).

This is an L2 field gap: `supplementary_files` alone isn't enough — the spec
needs to distinguish "co-installable assets" from "provider-feature-dependent
includes."

### Q3: Per-item versioning vs. package versioning.

obra/superpowers has 14 skills and 1 hook, all at version `5.1.0` (from
`package.json`). If the `test-driven-development` skill is updated but nothing
else changes, `package.json` gets bumped and all 14 skills show a new version,
even the ones that didn't change.

For a registry that tracks per-item versions, this is noisy. An install tool
that caches `test-driven-development@5.1.0` must re-verify all skills when
`5.2.0` ships, even if only one changed.

Options:
1. Accept package versioning — all items share the package version. Simple, but
   causes spurious cache invalidation.
2. Per-item versioning in L2 frontmatter — publishers bump individual item
   versions manually. Publishers won't do this (Remy's test).
3. Registry tracks per-item content hashes and uses hash-as-identity — the
   version label is informational, hash is the truth. This is the principled
   answer, consistent with Go modules. But requires the registry to recompute
   hashes on every push and compare.

The spec should state which model it adopts. This trace reveals the ambiguity
hasn't been resolved.

### Q4: The skill directory contains exactly one "primary" file by convention but the spec doesn't define this.

`skills/test-driven-development/` contains `SKILL.md` and `testing-anti-patterns.md`.
The primary file is `SKILL.md` because that's the convention across the repo
(every skill directory has a `SKILL.md`). But this is an implicit convention,
not a spec requirement. A registry needs explicit rules:
- "The primary skill file in a skill directory MUST be named `SKILL.md`" (naming convention)
- OR "The skill directory MUST contain exactly one `.md` file with YAML frontmatter
  containing a `name` field" (content convention)
- OR "The L2 sidecar or frontmatter MUST declare the primary file" (explicit declaration)

obra/superpowers uses the first option. The spec should pick one.

### Q5: How does the registry discover skills in the first place?

The registry knows to look in `skills/` because `.claude-plugin/plugin.json`
has `"skills": "./skills/"`. But `.codex-plugin/plugin.json` also has
`"skills": "./skills/"`. If a repo ships no plugin manifest at all, the registry
would have to scan for directories named `skills/` or files named `SKILL.md`.
The spec needs a discovery rule that works without a plugin manifest.

Candidate rules (in order of reliability):
1. Explicit registry config (`.acif.yaml` or similar) declares content paths
2. Plugin manifest field (`"skills": "./skills/"`)
3. Naming convention scan: any `.md` file with `content_type: skill` frontmatter
4. Directory convention scan: any file named `SKILL.md`

For obra/superpowers, rules 2 and 4 both work. The spec should define the
precedence.
