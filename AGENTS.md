# Agent Instructions

## What this repo is

ACIF is a specification set, not a library. The normative content is the 11
specs under `specs/` and the test vectors under `conformance/vectors/`; the
vectors win over prose when the two disagree. `conformance/runner/` is the
Python conformance runner. Implementations live in other repos (syllago,
acif-ts).

## Build and test

There is no build. Python 3 with PyYAML runs everything, from the repo root.

```bash
python3 -m conformance.runner selftest   # must pass before any commit
python3 -m conformance.runner --adapter "<cmd>" [--scope S] [--only ID] [--report out.json]
python3 -m conformance.runner differential --adapter-a "<cmd>" --adapter-b "<cmd>"
```

The selftest checks catalog hashes against `conformance/suite-manifest.yaml`,
checks every export (`conformance/*.yaml`) against its spec section, and runs
the runner's own regression tests.

## Changing the specs or the suite

Every normative change follows [CHANGE-PROCESS.md](CHANGE-PROCESS.md). Read
it before editing a spec table, a vector, or an export: the change class
decides whether you need a suite bump, a manifest entry, or a decision row
in `SHAPE.md`. Editing a vector or a hashed catalog without a manifest entry
fails the selftest.

## Non-Interactive Shell Commands

**ALWAYS use non-interactive flags** with file operations to avoid hanging on confirmation prompts.

Shell commands like `cp`, `mv`, and `rm` may be aliased to include `-i` (interactive) mode on some systems, causing the agent to hang indefinitely waiting for y/n input.

**Use these forms instead:**
```bash
# Force overwrite without prompting
cp -f source dest           # NOT: cp source dest
mv -f source dest           # NOT: mv source dest
rm -f file                  # NOT: rm file

# For recursive operations
rm -rf directory            # NOT: rm -r directory
cp -rf source dest          # NOT: cp -r source dest
```

**Other commands that may prompt:**
- `scp` - use `-o BatchMode=yes` for non-interactive
- `ssh` - use `-o BatchMode=yes` to fail instead of prompting
- `apt-get` - use `-y` flag
- `brew` - use `HOMEBREW_NO_AUTO_UPDATE=1` env var
