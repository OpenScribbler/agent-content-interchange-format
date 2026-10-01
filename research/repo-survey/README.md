# Repo Survey — How AI Agent Content is Structured Today

**Survey date:** 2026-05-12
**Repos analyzed:** 111 (round 1, by category) + 105 (round 2, by discovery axis)
**Purpose:** Empirical grounding for ACIF's carrier model (Decisions #10/#15), pack model (Decision #18), hashing algorithm (Decision #19), and content discovery rules.

**Scope note:** ACIF is provider-agnostic content interchange for the six content types (hook, skill, rule, command, agent, mcp_config). Vendor-specific plugin and marketplace distribution systems are explicitly out of scope and are not analyzed in this survey.

## Files

### Round 1 — high-star sample by content category

| File | Purpose |
|---|---|
| [`findings.md`](./findings.md) | Main analysis — cross-category patterns, ACIF implications, spec-text recommendations |
| [`repos.csv`](./repos.csv) | Flat per-repo structured data (111 rows) |
| [`raw/cat1-skills.md`](./raw/cat1-skills.md) | Cat 1: Skills (18) |
| [`raw/cat2-claude-code.md`](./raw/cat2-claude-code.md) | Cat 2: Commands, agents, subagents (18) |
| [`raw/cat3-cursor.md`](./raw/cat3-cursor.md) | Cat 3: Cursor rules ecosystem (19) |
| [`raw/cat4-mcp.md`](./raw/cat4-mcp.md) | Cat 4: MCP servers and config (20) |
| [`raw/cat5-other-tools.md`](./raw/cat5-other-tools.md) | Cat 5: Other AI coding tools — Cline / Roo / Aider / Continue / Goose / Copilot / Codex (18) |
| [`raw/cat6-broader.md`](./raw/cat6-broader.md) | Cat 6: Broader agentic + prompt collections (16) |

### Round 2 — community signal and registries, beyond GitHub stars

Round 1 ranked by stars only. Round 2 covers Reddit/HN, notable individuals (Pocock, Karpathy-styled, Yegge, Willison, Tan, Steinberger, Schmid), long-tail active repos including non-shell hook libraries and vendor skills, registry-level data (npm/PyPI/crates.io/MCP Registry/HuggingFace/SkillsMP), and named-citation discourse.

| File | Purpose |
|---|---|
| [`round2-findings.md`](./round2-findings.md) | Round 2 synthesis — 10 new findings (numbered #9–#18), spec-text additions R2-1 through R2-8 |
| [`round2-repos.csv`](./round2-repos.csv) | Flat per-repo structured data (105 rows) |
| [`raw/round2/agent-a-reddit-hn.md`](./raw/round2/agent-a-reddit-hn.md) | Reddit / HN signal (25 entries) |
| [`raw/round2/agent-b-notable-individuals.md`](./raw/round2/agent-b-notable-individuals.md) | Notable individuals (12 entries) |
| [`raw/round2/agent-c-longtail-active.md`](./raw/round2/agent-c-longtail-active.md) | Long-tail active including non-shell hooks and vendor skills (37 entries) |
| [`raw/round2/agent-d-registries-non-github.md`](./raw/round2/agent-d-registries-non-github.md) | npm / PyPI / crates.io / MCP Registry / HuggingFace / SkillsMP (28 entries) |
| [`raw/round2/agent-e-discourse-citations.md`](./raw/round2/agent-e-discourse-citations.md) | Blog / X / podcast citations (20 entries) |

## TL;DR

**Round 1 (stars-based, by content category):**
- **5 dominant shapes of "content unit"**: dir-with-SKILL.md, single-md-with-frontmatter, single-dotfile, single-file-aggregations (CSV/JSON/README), code-as-content
- **AGENTS.md is a real provider-neutral cross-tool marker** worth acknowledging in ACIF (as a marker / render target, not a carrier)
- **~⅓ of high-star repos have NO manifest at all** — Decision #18's inferred-pack model is essential
- **Multi-file content is implicit by directory** in 100% of skill repos — OQ-8 should resolve to implicit-bundle semantics
- **Per-item versioning is rare**; absent or pack-level is the norm — Decisions #16/#17 are uncontroversial
- **Cross-platform mirror dirs** (publishers maintaining `.claude/` + `.cursor/` + `.codex/` + `.opencode/` by hand) are the strongest "ACIF should exist" signal — frame as "publish once, render to N tools"
- **MCP `server.json` already solves install metadata** (upstream protocol-level, not vendor plugin) — ACIF's `mcp_config` should be runtime-wiring only

**Round 2 (community signal and registries):**
- **MCP registry's `packages[]` / `remotes[]` structural split** is the normative answer for `mcp_config` carrier shape (R2-1)
- **Six-shape hook taxonomy** (enforcement / quality / memory / observability / compression / session continuity) — these are usage patterns; ACIF's flat hook content type is sufficient
- **Download counts diverge 10–100× from star counts** — `@modelcontextprotocol/sdk` ships 36M/week npm + 67M/week PyPI; registry data is the real adoption signal
- **Hook libraries are now multi-language** (TS / Ruby / Go / Rust / Python daemon / PowerShell) — hook body must be opaque to ACIF (R2-2)
- **Practitioner-invented auxiliary types**: `skill-rules.json`, `CONTEXT.md`, `.beads/beads.jsonl`, `~/.agents` symlinks — the first one suggests reserving an `extensions.activation` namespace on hooks
- **Big Four practitioner consensus**: obra/superpowers, garrytan/gstack, EveryInc/compound-engineering-plugin, mattpocock/skills — load-bearing repos that converged across independent discovery axes
- **karpathy-skills exists** (forrestchang/andrej-karpathy-skills, 126.7k stars, created 1 day after Karpathy's X post) and is the canonical demo of CLAUDE.md + skill + Cursor `.mdc` *dual-delivery*

See [`findings.md`](./findings.md) for round 1 analysis and [`round2-findings.md`](./round2-findings.md) for round 2 synthesis.

## Methodology

**Round 1.** Six general-purpose subagents ran in parallel, each surveying one content-type category via `gh` CLI. Seed repos provided; agents expanded via `gh search`. Stars are point-in-time snapshots from the GitHub API on 2026-05-12.

**Round 2.** Five sonnet subagents ran in parallel, each surveying one *discovery axis* (Reddit/HN, notable individuals, long-tail active, registries / non-GitHub, discourse citations) — deliberately orthogonal to round 1's category structure to avoid duplication. Round 1's covered repos passed to each agent as an exclusion list. Suspicious star counts verified via direct `gh repo view` calls. Reddit and Twitter/X direct fetches were blocked; agents compensated via HN Algolia API and search-engine snippets, so discourse signal is shallower than GitHub signal.

No repos were modified or cloned in either round.
