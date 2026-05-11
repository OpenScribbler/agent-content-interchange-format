# DRAFT

# End-to-End Trace: obra/superpowers

This directory traces two concrete content items from the `obra/superpowers` repository
through the proposed layered spec architecture. The goal is to discover where the layering
is wrong, what fields are missing, and where the spec is ambiguous — not to produce a
finished spec.

## What obra/superpowers publishes

`obra/superpowers` (https://github.com/obra/superpowers) is a multi-skill, multi-hook
plugin for AI coding tools. Version 5.1.0 ships:

- **14 skills** in `skills/` — each a directory containing `SKILL.md` (with YAML
  frontmatter) plus optional supplementary `.md` files
- **1 hook** — `SessionStart`, defined across two provider files:
  - `hooks/hooks.json` (Claude Code format)
  - `hooks/hooks-cursor.json` (Cursor format)
  - `hooks/session-start` (the bash script both delegate to)
  - `hooks/run-hook.cmd` (cross-platform polyglot wrapper)
- **4 provider plugin manifests** — `.claude-plugin/plugin.json`,
  `.cursor-plugin/plugin.json`, `.codex-plugin/plugin.json`, `gemini-extension.json`
- `package.json` — carries version, author, license, and repository URL

The repository has a `package.json` version (`5.1.0`) as the authoritative version
label. There is no separate per-content-item versioning — all skills and hooks share the
package version.

## Items traced

### 1. `test-driven-development` skill

Source: `skills/test-driven-development/SKILL.md`

This skill has YAML frontmatter (`name`, `description`) and a large prose body.
Skills are `.md` files the publisher authors directly, so L2 publisher metadata
is carried as frontmatter augmentation — no separate sidecar file.

See: [skill-tdd.md](skill-tdd.md)

### 2. `SessionStart` hook

Source: `hooks/hooks.json`, `hooks/hooks-cursor.json`, `hooks/session-start`

The hook fires at session start, runs a bash script, and injects the
`using-superpowers` skill content as context into the agent's conversation.
It has provider-specific logic (detects `CURSOR_PLUGIN_ROOT` vs `CLAUDE_PLUGIN_ROOT`
and formats its JSON output accordingly). Hooks cannot use frontmatter because
the provider harness owns `settings.json`, so L2 metadata requires a separate
`.hook.yaml` sidecar.

See: [hook-session-start.md](hook-session-start.md)

## Output files

| File | Contents |
|------|----------|
| `README.md` | This file — overview of the trace |
| `hook-session-start.md` | Full L2/L3 trace for the SessionStart hook |
| `skill-tdd.md` | Full L2/L3 trace for the test-driven-development skill |
| `delta.md` | Comparison: where hook and skill traces diverge, and what that reveals |

## What this trace is for

Each trace document surfaces:
- What L2 publisher metadata would look like for that specific item
- What an L3 registry entry would look like, including auto-generation when L2 is absent
- Open questions the real content exposes that the spec doesn't yet answer

Placeholder values (content hashes, unspecified field names) are marked `# TBD` with
a note explaining what's missing from the spec.
