# DRAFT

# Trace: SessionStart Hook — obra/superpowers

## Source

The `SessionStart` hook in obra/superpowers is defined across three files.

### hooks/hooks.json (Claude Code format)

```json
{
  "hooks": {
    "SessionStart": [
      {
        "matcher": "startup|clear|compact",
        "hooks": [
          {
            "type": "command",
            "command": "\"${CLAUDE_PLUGIN_ROOT}/hooks/run-hook.cmd\" session-start",
            "async": false
          }
        ]
      }
    ]
  }
}
```

Notable:
- Uses `SessionStart` (PascalCase) — Claude Code's native event name
- The matcher `"startup|clear|compact"` is a pipe-delimited regex, not a JSON array.
  In HIF canonical terms this is a `{"pattern": "startup|clear|compact"}` matcher.
- The command uses `${CLAUDE_PLUGIN_ROOT}` — a Claude Code-specific env variable
  injected at install time to point at the plugin root directory.
- `"async": false` — the hook runs synchronously (Claude Code default, so this is
  explicit but redundant).

### hooks/hooks-cursor.json (Cursor format)

```json
{
  "version": 1,
  "hooks": {
    "sessionStart": [
      {
        "command": "./hooks/run-hook.cmd session-start"
      }
    ]
  }
}
```

Notable:
- Cursor uses `sessionStart` (camelCase) for the same event.
- Cursor format does not have an inline `matcher` field at the hook level.
- Cursor format does not have an `async` field.
- The command is a relative path, not using an env variable.
  Cursor resolves it relative to the plugin root directory.
- The Cursor format does not have a nested `hooks` array — it's a flat command
  object directly under the event key.

### hooks/session-start (the bash script)

The script (`hooks/session-start`, an extensionless bash script):

1. Reads `${PLUGIN_ROOT}/skills/using-superpowers/SKILL.md`
2. JSON-escapes it using bash parameter substitution
3. Checks for a legacy `~/.config/superpowers/skills` directory and builds a warning
4. Outputs one of three JSON shapes depending on which platform env var is set:
   - `CURSOR_PLUGIN_ROOT` → `{"additional_context": "..."}` (Cursor/snake_case)
   - `CLAUDE_PLUGIN_ROOT` (without `COPILOT_CLI`) → `{"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": "..."}}` (Claude Code nested format)
   - Fallback → `{"additionalContext": "..."}` (SDK standard / Copilot CLI)
5. Exits 0 (success) in all paths

The script invocation is wrapped by `hooks/run-hook.cmd`, a bash/batch polyglot
that makes the extensionless script work on Windows (cmd.exe runs the batch
portion, which locates Git for Windows bash and delegates) and Unix (direct exec).

**What the hook actually does:** On every session start, Claude Code and Cursor
get the full content of the `using-superpowers` skill injected into the agent's
context. This bootstraps the agent's knowledge of what skills are available
without the user having to invoke anything manually.

---

## L2 Publisher Metadata

The L2 spec calls for a `.hook.yaml` sidecar file because the provider harness owns
`settings.json` — metadata cannot live inline.

There is one hook in this package. The sidecar would live alongside the hook
definition files: `hooks/session-start.hook.yaml`.

```yaml
# hooks/session-start.hook.yaml
# L2 publisher metadata sidecar for the SessionStart hook
# spec-version: TBD — the L2 spec does not yet define a version field name

name: session-start
content_type: hook
# TBD: Should content_type use canonical L1 type names? The L1 HIF spec doesn't
# define a content_type vocabulary. Candidate: "hook" or "hooks/0.1".

version: "5.1.0"
# Sourced from package.json — there is no per-hook version in this repo.
# TBD: Should L2 allow inheriting version from a package manifest?
# Or does each item always carry its own version?

description: >
  Injects the using-superpowers skill into the agent context on every session
  start, so the agent knows what skills are available without manual invocation.

license: MIT
# Sourced from package.json / .claude-plugin/plugin.json

author:
  name: Jesse Vincent
  email: jesse@fsck.com
# Sourced from .claude-plugin/plugin.json

homepage: https://github.com/obra/superpowers
# TBD: Is "homepage" the right field name, or "repository"? Both appear in plugin.json.

# Canonical event this hook binds to (using HIF event registry name)
event: session_start
# TBD: Does L2 require the publisher to declare the event? Or is this inferred
# from the hook's provider files by the registry at L3?

# The hook script that implements the behavior
entry: ./session-start
# TBD: L2 hasn't defined an "entry" or "script" field. What do we call the
# primary implementation artifact for a hook?

# Cross-platform wrapper required by this hook
# TBD: Does L2 have a concept of "auxiliary files" that the registry should
# include in the content hash? run-hook.cmd is not optional — without it,
# the hook silently no-ops on Windows.
auxiliary_files:
  - ./run-hook.cmd

# Runtime requirements
runtime:
  shell: bash
  # The script uses: set -euo pipefail, bash parameter substitution, printf
  # No external commands beyond cat and printf.
  # TBD: What vocabulary does L2 use for runtime requirements?
  # "shell: bash" is not defined anywhere in the current spec.

# Canonical capabilities used (from HIF capability registry)
capabilities:
  # The hook uses structured output (JSON on stdout with additionalContext)
  - structured_output
  # The hook provides context injection
  # TBD: "context_injection" doesn't appear in the HIF capability registry
  # as seen in capabilities.md. The closest is "structured_output".
  # This trace reveals a missing capability name.

# Provider support
# TBD: Should L2 have an explicit provider compatibility field?
# This hook is written to support claude-code, cursor, and copilot-cli.
# The gemini-extension.json doesn't reference hooks at all.
providers:
  - claude-code
  - cursor
  - copilot-cli
# The hook deliberately does NOT support Gemini (no hooks.json equivalent
# in gemini-extension.json).

# Blocking behavior
blocking: false
# The hook exits 0 and injects context — it never prevents the session
# from starting.
```

**What the publisher would actually write.** Jesse Vincent would realistically
provide `name`, `version`, `description`, `license`, `author`, and `homepage`
from what's already in `package.json` / `.claude-plugin/plugin.json`. The
`event`, `entry`, `capabilities`, and `providers` fields are the new things
L2 asks of the publisher. That's non-trivial annotation on top of metadata
that already exists in the plugin manifests.

**The overlap problem.** The four plugin manifests (`.claude-plugin/plugin.json`,
`.cursor-plugin/plugin.json`, `.codex-plugin/plugin.json`, `gemini-extension.json`)
already carry `name`, `version`, `author`, `license`, and `repository`. L2 would
be asking the publisher to duplicate this into a fifth file. The spec needs to
say whether L2 can source from these existing manifests rather than requiring
a new sidecar.

---

## L3 Registry Entry

The registry auto-generates metadata when L2 is absent (Debian overlay pattern).
Here is what the registry entry would look like both with and without L2 provided.

### With L2 provided (publisher supplied sidecar)

```yaml
# L3 registry index entry for obra/superpowers SessionStart hook

id: obra/superpowers/session-start
# TBD: What is the L3 ID scheme? "org/repo/item-name"? Or something else?

content_type: hook

# Content hash computed by the registry over the canonical bytes
# TBD: What bytes are hashed for a hook?
# For a skill (single .md file), the content is clear.
# For a hook, the "content" could be:
#   (a) hooks.json + hooks-cursor.json (provider files)
#   (b) the session-start script itself
#   (c) all files in hooks/ including run-hook.cmd
#   (d) a canonical HIF JSON derived from decoding the provider files
# Option (d) is the most principled (hash over canonical representation)
# but requires the registry to run a full HIF decode before hashing.
# Options (a)-(c) are simpler but hash provider-specific bytes.
# The choice here determines whether two providers that ship identical
# behavior but different provider files get the same content hash.
content_hash:
  algorithm: sha256  # TBD: hash algorithm not yet defined in L3 spec
  value: "TBD"       # placeholder — not computed

# Source
source_repo: https://github.com/obra/superpowers
source_path: hooks/
# TBD: source_path for a hook is a directory, not a single file.
# For skills, it's a single file path. This asymmetry needs spec language.

discovered_at: "TBD"  # ISO 8601 timestamp set by registry at first index

# Publisher metadata — from L2 sidecar (publisher-provided)
publisher_metadata_source: publisher  # "publisher" | "registry" (auto-generated)
name: session-start
version: "5.1.0"
description: >
  Injects the using-superpowers skill into the agent context on every session
  start, so the agent knows what skills are available without manual invocation.
license: MIT
author:
  name: Jesse Vincent
  email: jesse@fsck.com
homepage: https://github.com/obra/superpowers
event: session_start
entry: ./session-start
blocking: false
capabilities:
  - structured_output

# Registry-added fields (not from publisher)
package_name: superpowers
# TBD: Where does the "package name" come from? package.json? .claude-plugin/plugin.json?
# obra/superpowers uses "superpowers" consistently, but the spec doesn't define
# how registries surface this.

verified_at: "TBD"   # Last time registry re-verified the content hash
```

### Without L2 provided (registry auto-generation, Debian overlay pattern)

When the publisher provides no sidecar, the registry infers what it can from
the existing files. This is what obra/superpowers looks like today — there
are no `.hook.yaml` sidecars.

```yaml
# Auto-generated L3 entry — no publisher L2 sidecar present

id: obra/superpowers/session-start
content_type: hook

content_hash:
  algorithm: sha256  # TBD
  value: "TBD"       # placeholder

source_repo: https://github.com/obra/superpowers
source_path: hooks/
discovered_at: "TBD"
publisher_metadata_source: registry  # registry auto-generated this

# Fields the registry CAN infer without L2:
name: session-start
# Inferred from: hooks/ directory name convention? Or from hooks.json key "SessionStart"?
# TBD: The spec needs to say how a registry derives the item name for a hook
# when no L2 sidecar exists.

version: "5.1.0"
# Inferred from: package.json .version field.
# TBD: Is the registry allowed to look in package.json for the version?
# What if package.json doesn't exist?

license: MIT
# Inferred from: .claude-plugin/plugin.json .license field.
# TBD: Which file takes precedence if multiple manifests declare different licenses?

author:
  name: Jesse Vincent
  email: jesse@fsck.com
# Inferred from: .claude-plugin/plugin.json .author field.

description: "Core skills library for Claude Code: TDD, debugging, collaboration patterns, and proven techniques"
# Inferred from: .claude-plugin/plugin.json .description field.
# NOTE: This is the *package* description, not a hook-specific description.
# The registry has no way to generate a hook-specific description without L2.

event: session_start
# Inferred by: decoding hooks.json and translating "SessionStart" → canonical name
# using the HIF Event Registry. This requires the registry to run a full decode.

# Fields the registry CANNOT infer without L2:
# - entry: which file is the primary implementation script?
#   The registry can see hooks.json → command → run-hook.cmd → session-start
#   but that requires chain-following across files.
# - blocking: false (could be inferred from hook definition, but fragile)
# - capabilities: cannot be inferred without running the script or static analysis
# - providers: could be inferred from which provider files exist, but fragile

verified_at: "TBD"
```

---

## Questions raised

### Q1: What bytes does the registry hash for a hook?

A skill is a single `.md` file — the content hash is straightforward. A hook
is a collection of files: provider config files (`hooks.json`, `hooks-cursor.json`),
the implementation script (`session-start`), and the wrapper (`run-hook.cmd`).

Option A: Hash provider config files only. Misses script changes.
Option B: Hash all files in `hooks/`. Includes `run-hook.cmd` even if unchanged.
Option C: Hash the canonical HIF JSON (decode → serialize → hash). Content-addressable
by behavior rather than bytes, but requires decode at index time.
Option D: Hash only the entry script. Ignores the provider routing layer.

This is unresolved in the current spec. For MOAT's content hash, the directory
hash algorithm covers all files in a directory — that would be option B. But the
spec doesn't say whether the hook "directory" is `hooks/` (all files) or just
the subset referenced by the hook definition.

### Q2: How does the registry identify item boundaries for hooks?

A plugin with multiple hooks needs separate registry entries per hook — otherwise
registry consumers can't install individual items. But the registry currently
scans repositories, not individual hook definitions. How does it know to create
`obra/superpowers/session-start` vs. `obra/superpowers` (one entry for the whole
plugin)?

obra/superpowers has only one hook, so this doesn't bite here. But the spec
needs item-granularity rules before it can handle a repo with five hooks.

### Q3: The sidecar overlaps heavily with existing plugin manifests.

`.claude-plugin/plugin.json` already carries `name`, `version`, `author`, `license`,
`repository`, `description`, `keywords`. The L2 sidecar would duplicate most of
this. The spec should define a merge order: if a plugin manifest exists, the
registry can source those fields from it without requiring a sidecar. The sidecar
then only adds hook-specific fields (`event`, `entry`, `capabilities`, `blocking`).

This would change the publisher's burden from "write a whole new sidecar" to
"write a minimal sidecar with the fields the plugin manifest doesn't cover."

### Q4: The matcher in hooks.json is not standard HIF syntax.

The Claude Code `hooks.json` uses `"matcher": "startup|clear|compact"` — a
pipe-delimited regex string. In HIF canonical form this is
`{"pattern": "startup|clear|compact"}`. But the HIF spec says pattern matchers
use RE2 and match against "provider-native tool names." The `SessionStart` event
matcher in Claude Code doesn't match tool names at all — it matches session
lifecycle events (startup, clear, compact are sub-types of SessionStart in
Claude Code). The HIF spec doesn't have a concept of "event sub-type matchers."
This is a gap: the HIF event model assumes a single event fires once, but Claude
Code's `SessionStart` is more like an event category.

### Q5: run-hook.cmd is a dependency of session-start but isn't declared anywhere.

The `session-start` script is invoked by Claude Code as:
`"${CLAUDE_PLUGIN_ROOT}/hooks/run-hook.cmd" session-start`

So the actual executable is `run-hook.cmd`, which delegates to `session-start`.
From an L2/L3 perspective, `run-hook.cmd` is a required auxiliary file — if it's
missing or tampered with, the hook silently no-ops (on Windows, where no bash
is found) or breaks. The spec has no field for auxiliary files. The content hash
must cover `run-hook.cmd` or integrity verification is incomplete.

### Q6: The hook has provider-specific output format detection at runtime.

The session-start script emits different JSON shapes depending on which env var
is set (`CURSOR_PLUGIN_ROOT` vs `CLAUDE_PLUGIN_ROOT`). This is provider detection
at runtime inside the script — not captured by any L1/L2/L3 field. From the
registry's perspective, this is a single hook that supports multiple providers.
But the registry can't verify this without running the script. L2 needs a way
to declare multi-provider support explicitly so the registry doesn't have to
execute content to discover it.
