# agent-content-interchange-format

A set of independent, layered specifications for describing, distributing, and rendering AI agent content — skills, hooks, rules, commands, sub-agents, and MCP configs — across the AI coding tool ecosystem.

## Why this exists

Today, AI agent content is published in provider-native formats. A "hook" for Claude Code, a "hook" for Cursor, and a "hook" for Codex are three different files even when they invoke the same underlying behavior. There is no provider-neutral way to:

1. **Describe** what an agent content item *is* (its capabilities, dependencies, runtime needs)
2. **Distribute** it through a registry that doesn't care which provider it targets
3. **Render** it back into one or more provider-native shells

This project pulls those three concerns apart into independent specs that can be adopted incrementally.

## The four layers

```
┌─────────────────────────────────────────────────────────────┐
│  L4  Render-back                                            │
│      Canonical item  →  provider-native files               │
│      (e.g., one canonical hook → hooks.json + hooks-cursor) │
└─────────────────────────────────────────────────────────────┘
                            ▲
┌─────────────────────────────────────────────────────────────┐
│  L3  Registry Consumption Spec                              │
│      How a registry indexes, hashes, and serves content     │
│      Includes auto-generation when publisher metadata is    │
│      absent (Debian-overlay pattern).                       │
└─────────────────────────────────────────────────────────────┘
                            ▲
┌─────────────────────────────────────────────────────────────┐
│  L2  Publisher Metadata Spec                                │
│      Author-side: what publishers declare per content item  │
│      (version label, dependencies, runtime, etc.).          │
│      Sidecar required for hooks/mcp; frontmatter elsewhere. │
└─────────────────────────────────────────────────────────────┘
                            ▲
┌─────────────────────────────────────────────────────────────┐
│  L1  Canonical Interchange Formats (per content type)       │
│      Provider-neutral data model for each content type.     │
│      One spec per type, each independent and versioned.     │
│      hooks-interchange (HIF) is the exemplar.               │
└─────────────────────────────────────────────────────────────┘
```

Each layer is independently adoptable. A publisher can adopt L2 without L1. A registry can adopt L3 without forcing publishers to adopt L2 (it auto-generates the metadata). Render-back (L4) is a tooling concern that consumes L1.

## Layer details

### L1 — Canonical Interchange Formats

One spec per content type. Each is a standalone document that defines:

- The canonical capability vocabulary for that content type
- How provider-native fields map to canonical keys
- A conversion enum: `translated | embedded | dropped | preserved | not-portable`
- Reference test vectors and (ideally) reference implementations

**Status:**

| Content type | Canonical format | Spec status |
|---|---|---|
| Hooks | HIF v0.1.0 → hooks-interchange | Externalized exemplar |
| Skills | Implemented in syllago | Not yet externalized |
| MCP configs | Implemented in syllago | Not yet externalized |
| Commands | Implemented in syllago | Not yet externalized |
| Sub-agents | Implemented in syllago | Not yet externalized |
| Rules | Implemented in syllago | Not yet externalized |

The canonical formats already exist as code in syllago (`cli/internal/capmon/recognize_*.go` + `docs/spec/canonical-keys.yaml` + `docs/provider-formats/*.yaml`). What this project does is *externalize* them into independent, versioned specs that other tools can implement without depending on syllago.

### L2 — Publisher Metadata Spec

Defines what a publisher declares about each content item: version label, dependencies, runtime requirements, license, content type, capabilities.

**Carrier rules:**

- **Forced sidecar** — hooks, MCP configs. The provider harness owns the top-level schema (`settings.json`, `mcp.json`), so metadata cannot live inline.
- **Frontmatter-capable** — skills, rules, agents, commands. Metadata lives in the existing file's YAML frontmatter; no new files required.

The publisher does as little as possible. Where frontmatter is available, that is the carrier. Sidecars exist only where the format forces them.

### L3 — Registry Consumption Spec

Defines how a registry:

1. Indexes content from publisher repos
2. Computes `content_hash` over canonical bytes (the identity primitive)
3. Auto-generates publisher metadata when absent (Debian overlay pattern)
4. Serves content to install tools (conforming clients per MOAT)

The registry never modifies the publisher's files. Auto-generated metadata is overlay metadata held by the registry, not pushed back upstream.

### L4 — Render-back

Given a canonical item (L1), deterministically emit one or more provider-native files. A single canonical hook produces both `hooks.json` (Claude format) and `hooks-cursor.json` (Cursor format) from the same source.

Render-back is what makes the canonical formats useful: publishers author once, registries serve once, tools install for any provider.

## Relationship to other projects

- **MOAT** — Signs and attests content bytes. Composes underneath this project: registries that implement L3 can use MOAT to attest their indexes; conforming clients verify those attestations at install. MOAT does not care about content type or capability — it operates on bytes.
- **syllago** — Personal package manager and conversion engine that already implements all six canonical formats internally. This project externalizes those formats into independent specs so other tools can adopt them without depending on syllago.

## Working method

This is an exercise, not a deliverable yet. We use `obra/superpowers` (cloned to `~/.local/src/superpowers/`) as real-world test data — it ships skills, hooks, and four provider plugins (Claude, Cursor, Codex, Gemini), so every layer has a concrete case to validate against.

Each artifact is written incrementally, with redirection between steps. The point is to discover where the layering is wrong, not to produce a finished spec on the first pass.

## Layout

```
specs/
  hooks-interchange/      # L1 — Hook Interchange Format
  skill-interchange/      # L1 — Skill canonical format (stub, follow HIF template)
  ...                     # one per content type
publisher-spec/           # L2
registry-spec/            # L3
render-back/              # L4
examples/
  obra/                   # End-to-end trace of obra/superpowers through all layers
```
