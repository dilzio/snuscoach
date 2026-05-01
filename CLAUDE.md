# CLAUDE.md

Working rules for the Snuscoach project. Honor these on every change. Matt will extend this file over time — read it before starting work.

## Workflow

1. **Always cut a new branch from `main`** before starting feature work.
   - Update local main, then branch: `git checkout main && git pull --rebase && git checkout -b <branch>` (skip the `pull` if there's no remote yet).
   - Default naming: `feature/<short-slug>` for features, `fix/<short-slug>` for bug fixes.
   - Never commit feature work directly to `main`.

2. **Always write integration tests** alongside code changes.
   - Tests live in `tests/` and use `pytest`.
   - Goal is regression prevention — exercise the full path (CLI → DB → output, coach context assembly with seeded DB rows, etc.) rather than mocking heavily.
   - When fixing a bug, write the test that reproduces it first, then fix.
   - When changing existing code that lacks coverage, add coverage for the path you're touching.

3. **Always commit locally after writing code.**
   - Commit at logical checkpoints — one feature or fix per commit; no batching unrelated changes.
   - Tests and the code they cover land in the same commit.
   - Do not push to a remote unless explicitly asked. Local commits only.

## Project context

- Product spec: `PRD.md` — read this before suggesting architectural changes. Phasing and non-goals are already locked.
- Phase 0 spike is built (CLI + SQLite + Anthropic SDK with prompt caching). The existing baseline is untested; when you touch a path that lacks coverage, add it.
- `make` (no target) lists every CLI command.
