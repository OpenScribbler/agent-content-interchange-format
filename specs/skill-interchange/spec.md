# Skill Interchange Format (SIF) — Draft Spec

**Version:** 0.1.0-draft
**Status:** Draft — not normative
**Derived from:** syllago canonical-keys.yaml + provider-formats/*.yaml (snapshot 2026-05-11)

---

## 1. Overview

A **skill** is a self-contained unit of agent behavior authored as a Markdown document. When installed, it expands what an AI coding tool can do without requiring changes to the host tool itself. Skills describe tasks (e.g., "deploy to staging", "summarize a PR") that an agent can invoke — either automatically when the conversation topic matches, or explicitly when the user types the skill's name.

This spec defines a **provider-neutral canonical format** for skills. It serves the same purpose for skills that the Hook Interchange Format (HIF) serves for hooks: a shared vocabulary that lets a skill authored once be understood by any conforming tool.

### 1.1 What this spec defines

- A canonical data model for skills in YAML frontmatter
- The set of canonical capability keys and what each means
- How provider-native fields map to canonical keys across 15 providers
- Carrier rules (where the canonical fields live — YAML frontmatter in the skill file itself)
- A conversion enum for provider extensions that have no canonical equivalent
- Open questions that must be resolved before this spec reaches normative status

### 1.2 What this spec does not define

- Provider-specific extension fields beyond what maps to canonical keys
- Skill discovery, installation, or registry distribution
- Cryptographic signing or provenance (see MOAT)
- Skill execution semantics or runtime behavior
- Render-back (converting from canonical form to provider-native layout) — that is an L4 concern

### 1.3 Relationship to HIF

HIF is the canonical interchange format for hooks. SIF follows the same architecture:
- Both define a per-content-type canonical vocabulary
- Both use a conversion enum (`translated | embedded | dropped | preserved | not-portable`) for provider extensions
- Both leave provider-exclusive fields in a `provider_data` escape hatch

The key structural difference: hooks require a sidecar file because the host tool owns the config file schema. Skills are Markdown files that publishers author directly — the YAML frontmatter in `SKILL.md` is the carrier. No sidecar is required.

---

## 2. Canonical Data Model

A canonical skill is represented as YAML frontmatter embedded in a Markdown file (`SKILL.md`). The Markdown body is the skill's instructional content — the text the agent reads when the skill is invoked.

### 2.1 File layout

```
<skill-name>/
  SKILL.md          # Required. YAML frontmatter + Markdown body.
  [other files]     # Optional. Supporting scripts, templates, configs.
```

The directory name is the skill's identity. When `display_name` is absent from frontmatter, implementations SHOULD use the directory name as the display name.

### 2.2 Frontmatter structure

```yaml
---
name: deploy-to-staging
description: Deploy the current branch to the staging environment.
version: 1.0.0
license: MIT
auto_invocable: true
disable-model-invocation: false
user-invocable: true
compatibility:
  min_version: "1.0"
metadata:
  team: platform
---
```

All fields are OPTIONAL unless noted. The Markdown body follows the closing `---`.

### 2.3 Canonical data model table

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Human-readable display name. If absent, directory name is used. |
| `description` | string | What the skill does. Shown in listings; drives auto-invocation matching. |
| `version` | string | Semantic version string for update detection and compatibility checks. |
| `license` | string | SPDX license identifier (e.g., `MIT`, `Apache-2.0`). |
| `auto_invocable` | bool | Whether the model can auto-invoke this skill without explicit user syntax. Default: `true` when description is present. |
| `disable-model-invocation` | bool | When `true`, prevents model from auto-invoking. Supersedes `auto_invocable`. Default: `false`. |
| `user-invocable` | bool | When `false`, hides the skill from user-facing menus (e.g., `/` command menu). The model may still invoke it. Default: `true`. |
| `compatibility` | object | Provider compatibility constraints. Schema is provider-defined; canonical shape is unspecified in this version. |
| `metadata` | object | Arbitrary key-value pairs for tooling or automation metadata. |

**Note on `auto_invocable` vs `disable-model-invocation`:** These are two sides of the same concept expressed differently by providers. `auto_invocable` is additive (capability declaration); `disable-model-invocation` is subtractive (opt-out). Both map to the same semantic. The canonical form retains both because `disable-model-invocation` is the field name used by providers that implement per-skill opt-out (Claude Code, Cursor, Codex, crush, factory-droid, pi).

---

## 3. Canonical Capability Keys

These are the keys defined in syllago's `CanonicalSkillsKeys` and `canonical-keys.yaml`. They describe capabilities in the skill content type — not field values, but behavioral/structural facts about how a provider implements skills. They are used in syllago's capability monitoring system and form the vocabulary that this spec's canonical data model is derived from.

| Canonical Key | Type | Description | Notes |
|---------------|------|-------------|-------|
| `display_name` | string | Human-readable name shown in listings; falls back to directory name if absent | Maps to `name` frontmatter field in all providers |
| `description` | string | What the skill does; drives auto-invocation decisions and is shown in help text | Required in most providers; max 1024 chars in codex/pi |
| `license` | string | SPDX license identifier | Optional; supported by open-standard providers |
| `compatibility` | object | Provider version/platform compatibility constraints | Optional; schema undefined at canonical level |
| `metadata_map` | object | Arbitrary key-value metadata for tooling | Optional; supported by open-standard providers |
| `auto_invocable` | bool | Model can auto-invoke without explicit user syntax | Equivalent to presence of description + absence of disable flag |
| `disable_model_invocation` | bool | Opt-out from model auto-invocation | Frontmatter key `disable-model-invocation` (hyphenated) in provider files |
| `user_invocable` | bool | Skill appears in user-facing menus | Frontmatter key `user-invocable` (hyphenated); default true |
| `version` | string | Semantic version for update detection | Optional; not widely supported yet |
| `project_scope` | bool | Can be installed at project scope (committed to repo) | Structural: presence of `.xxx/skills/` directory convention |
| `global_scope` | bool | Can be installed at user/personal scope (home directory) | Structural: presence of `~/.xxx/skills/` path |
| `shared_scope` | bool | Can be installed at enterprise/shared scope | Structural: organization-level distribution path |
| `canonical_filename` | string | Required or conventional filename (always `SKILL.md`, except kiro which uses `POWER.md`) | |
| `custom_filename` | bool | Whether non-standard filenames are accepted | Only factory-droid (`skill.mdx`) and pi (single-file `.md`) support this |
| `skill_bundled_resources` | bool | Skill directory may contain arbitrary co-located files beyond the primary skill file | Supporting scripts, templates, configs loaded on demand |

**Frontmatter key naming note:** The canonical key names in this spec use underscores (`disable_model_invocation`). The provider-side frontmatter keys use hyphens (`disable-model-invocation`) because YAML frontmatter keys are case-sensitive and the hyphenated form is what providers actually implement. When converting, translators must map between these forms.

---

## 4. Provider Mappings

### 4.1 Skills support status by provider

| Provider | Skills Status | Canonical Filename | Notes |
|----------|--------------|--------------------|-------|
| amp | supported | `SKILL.md` | CLI; implements Agent Skills standard |
| claude-code | supported | `SKILL.md` | CLI; implements Agent Skills standard with extensions |
| cline | supported | `SKILL.md` | IDE extension; experimental feature as of 2026-04 |
| codex | supported | `SKILL.md` | CLI; typed Go struct source; openai.yaml companion file |
| copilot-cli | supported | `SKILL.md` | CLI; implements Agent Skills standard |
| crush | supported | `SKILL.md` | CLI; implements Agent Skills standard |
| cursor | supported | `SKILL.md` | Standalone app; implements Agent Skills standard |
| factory-droid | supported | `SKILL.md` (also `skill.mdx`) | CLI; `custom_filename` supported |
| gemini-cli | supported | `SKILL.md` | CLI; implements Agent Skills standard |
| kiro | supported | `POWER.md` | Standalone app; calls content type "powers" |
| opencode | supported | `SKILL.md` | CLI; no native implementation, uses cross-provider convention |
| pi | supported | `SKILL.md` | CLI; open standard + single-file shorthand |
| roo-code | supported | `SKILL.md` | IDE extension; implements Agent Skills standard subset |
| windsurf | supported | `SKILL.md` | Standalone app; implements Agent Skills standard |
| zed | **not supported** | — | No Agent Skills loader documented |

### 4.2 Canonical field → provider native field mapping

The table below shows how each canonical key maps to provider-native frontmatter fields. "n/a" means the provider doesn't support the capability. "implicit" means the capability exists but via a structural convention rather than an explicit field.

| Canonical Key | amp | claude-code | cline | codex | copilot-cli |
|---------------|-----|-------------|-------|-------|-------------|
| `display_name` | `name` | `name` | `name` | `name` | `name` |
| `description` | `description` | `description` | `description` | `description` | `description` |
| `license` | n/a | n/a | n/a | n/a | n/a |
| `compatibility` | n/a | n/a | n/a | n/a | n/a |
| `metadata_map` | n/a | n/a | n/a | n/a | n/a |
| `auto_invocable` | implicit | implicit (description) | implicit (description) | implicit | implicit |
| `disable_model_invocation` | n/a | `disable-model-invocation` | n/a | `policy.allow_implicit_invocation` (via openai.yaml) | n/a |
| `user_invocable` | n/a | `user-invocable` | n/a | n/a | implicit (`/skill-name`) |
| `project_scope` | `.agents/skills/`, `.claude/skills/` | `.claude/skills/` | `.cline/skills/` | `.agents/skills/` | `.github/skills/`, `.agents/skills/` |
| `global_scope` | `~/.config/agents/skills/` etc. | `~/.claude/skills/` | `~/.cline/skills/` | `~/.agents/skills/` | `~/.copilot/skills/` |
| `shared_scope` | n/a | managed settings | n/a | `/etc/codex/skills/` | "coming soon" |
| `canonical_filename` | `SKILL.md` | `SKILL.md` | `SKILL.md` | `SKILL.md` | `SKILL.md` |
| `custom_filename` | n/a | n/a | n/a | n/a | n/a |
| `skill_bundled_resources` | yes (arbitrary files) | yes (`${CLAUDE_SKILL_DIR}`) | yes (`docs/`, `scripts/`, `templates/`) | yes (`openai.yaml` companion + assets) | yes (directory is unit of loading) |

| Canonical Key | crush | cursor | factory-droid | gemini-cli | kiro |
|---------------|-------|--------|---------------|------------|------|
| `display_name` | `name` | `name` | `name` | `name` | `name` |
| `description` | `description` | `description` | `description` | `description` | `description` |
| `license` | n/a | `license` | n/a | n/a | n/a |
| `compatibility` | n/a | `compatibility` | n/a | n/a | `compatibility` |
| `metadata_map` | n/a | `metadata` | n/a | n/a | `metadata` |
| `auto_invocable` | implicit | implicit | implicit | implicit | `keywords` array |
| `disable_model_invocation` | `disable-model-invocation` (inferred from standard) | `disable-model-invocation` | `disable-model-invocation` | n/a | n/a |
| `user_invocable` | n/a | implicit (when disable-model-invocation is true) | `user-invocable` | n/a | n/a |
| `project_scope` | `.crush/skills/`, `.agents/skills/` | `.cursor/skills/`, `.agents/skills/` | `.factory/skills/` | `.gemini/skills/` | UI install, no fixed path |
| `global_scope` | `~/.config/crush/skills/`, `~/.agents/skills/` | `~/.cursor/skills/`, `~/.agents/skills/` | `~/.factory/skills/` | `~/.gemini/skills/` | n/a |
| `shared_scope` | n/a | n/a | n/a | n/a | n/a |
| `canonical_filename` | `SKILL.md` | `SKILL.md` | `SKILL.md` | `SKILL.md` | `POWER.md` |
| `custom_filename` | n/a | n/a | `skill.mdx` | n/a | n/a |
| `skill_bundled_resources` | n/a (not documented) | yes (`scripts/`, `references/`, `assets/`) | yes (co-located files) | yes (`scripts/`, `references/`, `assets/`) | yes (`steering/` directory, `mcp.json`) |

| Canonical Key | opencode | pi | roo-code | windsurf |
|---------------|----------|----|----------|---------|
| `display_name` | `name` | `name` | `name` | `name` |
| `description` | `description` | `description` | `description` | `description` |
| `license` | `license` | `license` | n/a | n/a |
| `compatibility` | `compatibility` | `compatibility` | n/a | n/a |
| `metadata_map` | `metadata` | `metadata` | n/a | n/a |
| `auto_invocable` | implicit | implicit | implicit | implicit (description match) |
| `disable_model_invocation` | n/a | `disable-model-invocation` | n/a | n/a |
| `user_invocable` | n/a | n/a | n/a | `@-mention` (always; implicit) |
| `project_scope` | `.opencode/skill/` | `.pi/skills/`, `.agents/skills/` | `.roo/skills/` | `.windsurf/skills/`, `.agents/skills/` |
| `global_scope` | `~/.config/opencode/skills/` | `~/.pi/agent/skills/`, `~/.agents/skills/` | `~/.roo/skills/` | `~/.codeium/windsurf/skills/`, `~/.agents/skills/` |
| `shared_scope` | n/a | n/a | `.agents/skills/` (cross-provider convention) | system path (OS-specific enterprise path) |
| `canonical_filename` | `SKILL.md` | `SKILL.md` | `SKILL.md` | `SKILL.md` |
| `custom_filename` | n/a | yes (single `.md` file at skill root) | n/a | n/a |
| `skill_bundled_resources` | n/a | n/a | n/a | yes (arbitrary co-located files) |

### 4.3 Provider extension fields with no canonical equivalent

These are fields present in one or more providers that currently have no canonical key. They are candidates for future canonicalization or remain as `provider_data` entries.

| Provider | Extension Field | Conversion | Description |
|----------|----------------|------------|-------------|
| claude-code | `argument-hint` | `embedded` | Autocomplete hint for expected argument format (presentational) |
| claude-code | `allowed-tools` | `embedded` | Pre-approves tool calls while skill is active |
| claude-code | `model` | `embedded` | Per-skill model override |
| claude-code | `effort` | `embedded` | Per-skill effort level override |
| claude-code | `context` / `agent` | `embedded` | Subagent execution context for skill invocation |
| claude-code | `hooks` | `embedded` | Lifecycle hooks scoped to this skill's active period |
| claude-code | `paths` | `embedded` | Glob filter limiting auto-activation to matching file paths |
| claude-code | `shell` | `embedded` | Per-skill shell selection for inline command execution |
| claude-code | `arguments` | `preserved` | Named positional arguments for `$name` substitution |
| claude-code | `when_to_use` | `embedded` | Additional context for when Claude should invoke the skill |
| codex | `metadata.short-description` | `embedded` | Condensed description for compact UI |
| codex | `interface.icon_small` / `icon_large` | `dropped` | Skill card icons (via openai.yaml) |
| codex | `interface.brand_color` | `dropped` | Brand color for skill card |
| codex | `interface.default_prompt` | `embedded` | Default prompt for UI invocation |
| codex | `dependencies.tools` | `embedded` | Required MCP servers or external tools |
| codex | `policy.products` | `dropped` | Product gating (OpenAI-specific) |
| cursor | `globs` | `embedded` | Glob patterns scoping skill to specific files; no canonical equivalent |
| factory-droid | `argument-hint` | `translated` | Autocomplete hint (same concept as claude-code) |
| factory-droid | `$ARGUMENTS` substitution | `translated` | Argument substitution in skill body |
| kiro | `displayName` | `embedded` | Human-readable label separate from slug `name` |
| kiro | `keywords` | `embedded` | Keyword array for model auto-activation (alternative to description matching) |
| kiro | `# Onboarding` section | `not-portable` | First-activation onboarding instructions block |
| kiro | `mcp.json` in skill dir | `not-portable` | Bundled MCP server config inside skill directory |
| amp | `toolbox/` executables | `not-portable` | Executables in `toolbox/` auto-registered as tools |
| amp | `mcp.json` in skill dir | `not-portable` | Bundled MCP server (same concept as kiro) |

---

## 5. Carrier Rules

Skills are Markdown files that publishers author directly. Unlike hooks (where the host tool owns `settings.json`) or MCP configs (where the host tool owns `mcp.json`), a skill's canonical data has a natural home: **YAML frontmatter in `SKILL.md`**.

### 5.1 Primary carrier: YAML frontmatter

All canonical fields defined in §2 live in the YAML frontmatter block at the top of `SKILL.md`:

```
---
<canonical fields here>
---
<skill body — Markdown instructional content>
```

This is the same convention used by 14 of the 15 providers in this survey (kiro uses `POWER.md` instead of `SKILL.md` but otherwise follows the same frontmatter pattern).

### 5.2 No sidecar required

Because the carrier is the skill file itself, no additional sidecar file is required for canonical metadata. This is the L2 publisher metadata spec's "frontmatter-capable" category: publishers declare metadata inline without authoring a separate file.

The `openai.yaml` companion file used by codex is a provider-specific extension (`not-portable`) — it carries codex-specific interface and policy metadata that has no canonical equivalent in this spec.

### 5.3 Directory structure is normative

The skill's directory name is its identity. Implementations MUST NOT rename the directory during installation. The canonical form of a skill's identity is `<directory-name>`, and `display_name` frontmatter is a human-readable override, not the primary identity.

### 5.4 Supporting files are non-normative

The supporting files pattern (arbitrary co-located files beyond `SKILL.md`) is a widely-adopted convention but is not canonically specified at the file level. The `skill_bundled_resources` canonical key records whether a provider supports the pattern. How publishers structure those files (subdirectory names like `scripts/`, `templates/`, etc.) is not standardized.

### 5.5 Canonical provider slug list

When a skill is installed for a specific provider, the target provider is indicated by directory path convention rather than a field in the frontmatter. The following canonical provider slugs are defined for use in tool-side configuration and render-back:

| Slug | Provider | Notes |
|------|----------|-------|
| `amp` | Amp (Sourcegraph) | |
| `claude-code` | Claude Code (Anthropic) | |
| `cline` | Cline | |
| `codex` | Codex (OpenAI) | |
| `copilot-cli` | GitHub Copilot CLI | |
| `crush` | Crush (Charmbracelet) | |
| `cursor` | Cursor | |
| `factory-droid` | Factory Droid | |
| `gemini-cli` | Gemini CLI (Google) | |
| `kiro` | Kiro (Amazon) | Uses `POWER.md`; canonical_filename differs |
| `opencode` | OpenCode (sst) | Uses cross-provider convention only |
| `pi` | Pi (badlogic) | |
| `roo-code` | Roo Code | |
| `windsurf` | Windsurf (Codeium) | |

---

## 6. Conversion Pipeline (Sketch)

The skill conversion pipeline mirrors HIF §7 but is simpler — skills have no exit code contracts, matcher systems, or handler type variations. The essential stages:

1. **Decode** — Read `SKILL.md` frontmatter, map provider-native field names to canonical keys.
2. **Validate** — Check that required fields are present for the target provider.
3. **Encode** — Write `SKILL.md` with the target provider's expected frontmatter key names and directory path conventions.
4. **Verify** — Re-read the output and confirm round-trip fidelity.

Notable decode complexities:
- `disable-model-invocation` (hyphenated in YAML) must map to `disable_model_invocation` (underscored) in canonical form.
- Codex's `disable_model_invocation` equivalent lives in `agents/openai.yaml` (companion file), not in `SKILL.md` frontmatter.
- Kiro's auto-invocation trigger is `keywords` (array), not `description` matching — these are semantically different mechanisms mapped to the same canonical key (`auto_invocable`).
- Factory-droid's `disable-model-invocation` default is `false` (model may invoke); claude-code's is also `false`. Both match canonical default.

---

## 7. Open Questions

These are unresolved questions that must be answered before this spec can reach normative status. They are surfaced here as a research agenda.

**OQ-1: Cursor `globs` field**
Cursor supports a `globs` frontmatter array that restricts skill auto-activation to files matching the glob patterns. No other provider has an equivalent canonical key for this. Options: (a) add `activation_globs` as a new canonical key, (b) put it in `provider_data` as `not-portable`. The `paths` field in claude-code does the same thing. This may already warrant graduation to a canonical key given two providers support it.

**OQ-2: `auto_invocable` vs `disable_model_invocation` canonicalization**
These two keys express the same concept from opposite directions. The canonical data model currently carries both. A cleaner model would unify them into a single canonical key (e.g., `model_invocation: enabled | disabled`). The tradeoff: the hyphenated `disable-model-invocation` is already the de facto standard field name in the Agent Skills spec, and changing it would break existing skill files. Decision needed before normative publication.

**OQ-3: Kiro's `POWER.md` and `keywords` mechanism**
Kiro calls skills "powers" and uses `POWER.md` as the canonical filename. Its auto-invocation is keyword-based (explicit `keywords` array) rather than description-matching. Questions:
- Should this spec treat kiro as a conforming provider with a non-standard filename, or as a separate content type that happens to overlap?
- The `keywords` mechanism is semantically different from description-based matching but maps to the same `auto_invocable` key. Is that correct, or does it need its own key?

**OQ-4: `displayName` vs `name` in kiro**
Kiro uses `name` as a slug identifier and `displayName` as a separate human-readable label. Most providers collapse both into `name`. Should `display_name` (the canonical key) map to kiro's `displayName` or `name`? If kiro's `name` is a slug-style identifier and `displayName` is the human-readable label, then the canonical `display_name` maps to `displayName` and the slug identity maps to directory name — but that creates an inconsistency with all other providers where `name` is both the slug and display name.

**OQ-5: `version` key — frontmatter or out-of-band?**
The `version` canonical key is defined but no provider currently maps a native frontmatter field to it. This is likely an L2 publisher metadata field rather than a skill-identity field. Should `version` be in this spec (L1 canonical format) or deferred to the publisher metadata spec (L2)? The L1/L2 split suggests it belongs in L2.

**OQ-6: `license` and `compatibility` field schemas**
Both are declared as `type: object` in canonical-keys.yaml but no provider defines a normative schema for either. The `compatibility` field in pi has a max 500 char constraint (suggesting it's a string, not an object), while opencode and cursor accept arbitrary object maps. The canonical type needs to be settled.

**OQ-7: `shared_scope` semantics are inconsistent**
Providers map `shared_scope` to very different things:
- codex: `/etc/codex/skills/` — machine-level, all local users
- claude-code: managed settings — organization-level, cloud delivery
- windsurf: OS-specific enterprise system path — managed IT deployment
- roo-code: `.agents/skills/` (cross-provider convention) — not actually a "shared" scope in the enterprise sense

The `shared_scope` key may need to be split into `machine_scope` (all users on one machine) and `enterprise_scope` (organization-wide) to avoid conflating these.

**OQ-8: Argument substitution in skills**
Claude-code, factory-droid, and pi support argument substitution in skill bodies (`$ARGUMENTS`, `$ARGUMENTS[N]`). This is not currently a canonical key. It may belong in the commands interchange format rather than here, since skills with arguments blur the skills/commands boundary. Claude-code explicitly documents `.claude/commands/` as the legacy equivalent of `.claude/skills/`.

**OQ-9: Scope path conventions — canonical or informative?**
The install paths (e.g., `.claude/skills/`, `.agents/skills/`, `~/.gemini/skills/`) are provider-specific. This spec documents them in the provider mappings table (§4.2), but should it normatively specify the canonical cross-provider path `.agents/skills/` as the preferred install location? 12 of 14 supported providers recognize `.agents/skills/` as a project-scope discovery path. Making it normative in this spec would give registries and install tools a single portable path to target.

**OQ-10: `openai.yaml` companion file graduation**
Codex's `openai.yaml` companion file carries fields (dependencies, interface icons, product gating) with no canonical equivalent. The `tool_dependencies` field may have cross-provider relevance as skill-MCP-bundling becomes more common (amp and kiro both bundle MCP servers in skill directories). Should dependency declarations graduate to a canonical key, or remain in `provider_data`?

---

## Appendix A: Agent Skills Open Standard

Many providers reference the "Agent Skills open standard" (agentskills.io). The standard's core field set is:

```yaml
name: string        # required, ≤64 chars
description: string # required, ≤1024 chars
license: string     # optional, SPDX
compatibility: any  # optional
metadata: object    # optional
disable-model-invocation: bool  # optional
```

Providers that explicitly implement this standard: amp, claude-code, cline, codex, copilot-cli, crush, cursor, factory-droid, gemini-cli, opencode, pi, roo-code (partial), windsurf.

The canonical keys in this spec are a superset of the open standard's core fields. Fields defined in this spec but not in the open standard (`user_invocable`, `version`, `project_scope`, `global_scope`, `shared_scope`, `canonical_filename`, `custom_filename`, `skill_bundled_resources`) are syllago capability-tracking keys describing structural/behavioral facts about providers, not additional frontmatter fields for publishers to set.

---

## Appendix B: Cross-Provider Discovery Path

The path `.agents/skills/<name>/SKILL.md` (project) and `~/.agents/skills/<name>/SKILL.md` (user) is recognized by the following providers as an alias for their native discovery path:

amp, codex, copilot-cli, crush, cursor, factory-droid, gemini-cli, pi, roo-code, windsurf

This makes `.agents/skills/` the de facto portable install location. See Open Question OQ-9 for discussion of whether this should be normative in this spec.
