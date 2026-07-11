# ACIF Roadmap

This is a list of items the ACIF spec has explicitly deferred. No version assignments — items here are not committed to any future release and are not prioritized.

The purpose of this file is to make deferrals visible: when someone asks "why doesn't ACIF handle X?", the answer is either "it does" (see SHAPE.md) or "it's listed here, with the rationale."

---

## Deferred items

### Single-file aggregations

Multi-item content stored as one CSV, JSON array, or single README (e.g., `f/prompts.chat` is one CSV containing 162k stars worth of prompts; `PlexPt` is one JSON array; awesome-list READMEs are single files of curated entries).

**Why deferred:** These collections are popular content but not unitized. Treating them as ACIF items would require an "exploder" carrier that declares how to slice one file into N logical items (path/JMESPath/CSV column mapping). Authoring burden is real, and the demand signal from publishers is weak — most aggregations are curated by hand, not synced as ACIF content.

**What it would take to revisit:** A publisher with a high-traffic aggregation asks for ACIF support, or a registry needs to ingest one.

### i18n / locale variants

Some publishers ship the same skill in multiple languages (PEG ships `_meta.{en,de,zh,...}.json` in 14 locales; `f/prompts.chat` has 30+ `messages/*.json`; obra/superpowers has localized README variants).

**Why deferred:** ACIF currently has no `locale` discriminator. Adding one touches identity (does each locale variant get its own UUID? share one?), discovery (which locale does a consumer prefer?), and rendering (does the runtime know the user's locale?). All resolvable, none urgent.

**What it would take to revisit:** A publisher with serious i18n needs asks for ACIF support, or a registry wants to surface localized variants distinctly.

### Multi-size content variants

Some publishers ship `.md`, `.mini.md`, `.nano.md` for different context-window budgets (ciembor's pattern). Authors are manually solving for context economy.

**Why deferred:** Could be modeled as `variants: [{name, body_hash}]` on a single item, or as N separate items. Either way, it's a feature addition, not a correctness issue.

**What it would take to revisit:** Context-window pressure shows up as a publisher-driven concern (rather than a runtime concern that the runtime handles).

### AGENTS.md full bidirectional emit/render

Round 1 finding #2 + Round 2 finding #16: ACIF v0.1 treats AGENTS.md as an informative marker. A full bidirectional workflow — read AGENTS.md as carrier input, write AGENTS.md as a canonical output target — is more than v0.1 needs.

**Why deferred:** Marker recognition is small and uncontroversial. Bidirectional CI is a larger surface (what's the round-trip guarantee? does AGENTS.md content map cleanly to ACIF's content types?).

**What it would take to revisit:** AGENTS.md adoption keeps accelerating *and* practitioners ask for ACIF tools that round-trip cleanly.

### Memory as a content type

Some practitioners ship git-backed agent memory (e.g., `gastownhall/gastown` uses `.beads/beads.jsonl`). This is not a hook, skill, rule, command, agent, or mcp_config — it's a 7th category.

**Why deferred:** Memory-as-content is an emerging pattern with one or two visible publishers. ACIF v0.1 has six well-bounded content types; adding a seventh on weak signal would dilute the spec.

**What it would take to revisit:** Multiple independent publishers converge on a memory-as-content pattern with similar shape.

### Cross-pack versioned dependencies

A skill declaring "requires hook X v2.x" from a different pack. ACIF v0.1 has same-pack cross-references for activation (Decision #21) using item UUIDv4, but no version constraints in the reference.

**Why deferred:** Single-pack activation cross-references are sufficient for the patterns observed so far. Cross-pack dependencies are a larger design surface (version range syntax, conflict resolution, transitive dependency handling) and the demand signal is currently zero.

**What it would take to revisit:** A pack publisher asks for the ability to constrain a referenced item by version, or a registry needs to express compatibility.

### Code-as-content (Python modules, TypeScript scripts, etc.)

LangChain / CrewAI / AutoGen agents live in `.py` files imported by `__init__.py`. Genaiscript skills are TypeScript modules. Dify workflows are YAML DSL in databases.

**Why deferred:** These are not portable units in the ACIF sense — they're code that runs in a specific runtime. ACIF cannot ingest them without parsing language-specific ASTs, which is a different scope.

**What it would take to revisit:** Unlikely. ACIF's design boundary is content interchange, not code distribution.

### Curated-index aggregator READMEs

Awesome-lists (e.g., `punkpeye/awesome-mcp-servers`, `jim-schwoebel/awesome_ai_agents`) are single READMEs of curated links. They're content discovery surfaces, not content publishers.

**Why deferred:** Out of scope by design. These point *to* publishers; ACIF talks to publishers directly.

**What it would take to revisit:** Never — this is a permanent scope boundary, not a deferral.

### Body-content reference grammar (owned deferral of OQ-8)

**Owner: the roadmap — carries binding obligations.** Whether ACIF's capability layer ever parses body content — rules' `@path` imports, skills' `@sibling.md` references, commands' positional argument forms, gemini's `!{shell}`/`@{file}` injection directives — and under what structure. ACIF v0.1's answer (adopted 2026-07-11, SHAPE.md OQ-8) is never-parse: capability dispositions read canonical structured content only; heuristic body signals are advisory-tier only.

**Why deferred:** No v0.1 consumer needs body-content derivation; the advisory tier delivers the installer-join value (commands walk); and pinning a reference grammar is multi-panel work. The de facto standing rule (derivation-vs-heuristic refinement) already governs.

**Binding obligations for whoever resolves this permanently:**
- **The structured-record bar (commands walk):** "grammar pinned" legitimizes derivation only if the canonicalizer resolves body content into a structured canonical record (e.g., an `imports[]` array) a predicate reads correct-by-construction — a grammar that merely recognizes patterns leaves any scan a heuristic → advisory tier at most.
- **Grammar branch consequences:** rules' `file_imports` becomes DERIVABLE (registry-computed, whole-corpus, zero author burden — never `requires`-eligible in any branch); the deferred OP-COND-RULES-4/-5 lints become implementable (@-target classes `{in-bundle, absolute, home, url}` — the `@~/.aws/credentials` exfil / `@https://` remote-fetch threat context recorded in the rules walk); Decision #31's fence-awareness and positional-form canonicalization unlock.
- **Never-parse branch obligation:** spec-purist's preserved rules dissent (`panel/rules-requires-consensus.md` §9 — silent semantic corruption of @-importing rules; OOS-routing a works-fine-without-it-failing capability is "the theater move on the other side") **MUST be re-heard before never-parse is finalized permanently.** The v0.1 deferral deliberately does not trigger this — it defers rather than finalizes.
- In no branch does any body-carried capability become `requires`-eligible (out-of-band guardrail + three-way routing, Decision #23).

**What it would take to revisit:** A registry or installer needs the @-import join normatively (not advisorily), or the OP-COND-RULES-5 security lint is wanted as normative rather than registry-discretion.

### Latent-field promotion (owned deferral of OQ-10)

**Owner: the roadmap — carries binding obligations.** Whether `SkillMeta`'s `AllowedTools`/`DisallowedTools`/`Model`/bundled `Hooks` and `CommandMeta`'s `AllowedTools`/`Model`/`Agent`/`Effort`/`Context`/`DisableModelInvocation`/`UserInvocable` are promoted to canonical capability vocabulary. Deferred 2026-07-11 (SHAPE.md OQ-10).

**Why deferred:** Transport ≠ promotion — v0.1 carries all latent fields 1:1 as opaque passthrough (round-trip fidelity), and nothing in v0.1 consumes them as capabilities. Promotion is a vocabulary-walk-scale effort across two content types.

**Binding obligations for whoever promotes:**
- **Uniformity constraint (commands walk):** activation-adjacent fields (commands' `UserInvocable`/`DisableModelInvocation`, skills' equivalents) MUST be disposed uniformly — same representation, same `D_K` shape; six-types-co-equal forbids a user-invocability signal installers parse two ways.
- `allowed_tools` MUST use Decision #25's canonical tool vocabulary (no second tool vocabulary).
- Commands' `agent` is a latent NAME-based cross-type reference — promotion requires resolving name-vs-UUID against Decision #21's UUID pattern first (Decision #28 input).
- `effort` needs a Decision #30/#31-style enum + total mapping if promoted; `model` stays opaque (provider-ID allowlists are the Decision #8 brittle-list trap).
- Any promoted key routes per the three-way routing (Decision #23); latent-field presence never softens the orphan-key reject in the interim.
- OP-COND-SKILLS-5 remains coupled here.

**What it would take to revisit:** An installer needs tool-restriction or model-selection filtering across skills/commands (the agents walk already derives these for agents), or a registry wants cross-type invocability filtering.

### `attestation_valid_until` informative mirror (OQ-9 roadmap valve)

An OPTIONAL, informative `registry_section` field mirroring the external attestation's validity horizon, for offline/air-gapped consumers that cannot fetch the attestation manifest at decision time. Deferred 2026-07-11 by the OQ-9 mini-review (Decision #34 adopted orthogonal freshness axes with zero new fields).

**Why deferred:** Reducing heterogeneous external validity representations (cert `notAfter`, transparency-log inclusion time, policy TTLs) to one instant requires the registry to understand the external system's semantics — the which-timestamp ambiguity Decision #13's agnosticism exists to avoid. And a consumer making attestation-based decisions must verify the attestation anyway, which yields validity under the system's own rules for free.

**Binding obligations if it lands:** OPTIONAL and informative only, carrying an explicit "may be stale; MUST NOT be a staleness input" disclaimer (parallel to `publisher_metadata`); spec-purist's absence semantics govern (absent = drops out of any consumer computation — never "expired," never a freshness extension); Decision #34's no-blending rule is unaffected. Revisit alongside the content-revocation feed (Decision #33 roadmap) — a revocation signal addresses the freeze-surface concern more directly than any expiry heuristic.

**What it would take to revisit:** Offline/air-gapped consumers with attestation-based policies materialize as a real deployment class.
