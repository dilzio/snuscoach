# CLAUDE.md

Working rules for the Snuscoach project. Honor these on every change. Matt will extend this file over time — read it before starting work.

## Agent Invariants
1. **Think Before Coding. Don't assume. Don't hide confusion. Surface tradeoffs.**
2. **Simplicity First. Minimum code that solves the problem. Nothing speculative.**
3. **Surgical Changes. Touch only what you must. Clean up only your own mess.** 
4. **Goal-Driven Execution. Define success criteria. Loop until verified.**
5. **Plan, then implement.  Always create a plan for review with the user before implementing.  Always ask probing questions and iterate witht the user**

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

4. **Always refer to PROGRESS.md when recommending/selecting the next feature to build**
   - Always update PROGRESS.md on the feature branch when the work is completed

## Project context

- Product spec: `PRD.md` — read this before suggesting architectural changes. Phasing and non-goals are already locked.
- Phase 0 spike is built (CLI + SQLite + Anthropic SDK with prompt caching). The existing baseline is untested; when you touch a path that lacks coverage, add it.
- `make` (no target) lists every CLI command.

## Commands

```bash
make install        # create venv and install snuscoach + dev deps
make test           # run full pytest suite
make init           # initialize / migrate the SQLite DB
make                # list all CLI commands
```

Run a single test:
```bash
pytest tests/test_post.py::TestPostDraft::test_post_draft_saves_last_iterated_draft
```

Requires `ANTHROPIC_API_KEY` in `.env` (see `.env.example`). Optional overrides: `SNUSCOACH_DB`, `SNUSCOACH_PROFILE`, `SNUSCOACH_LOG_DIR`.

## Architecture

**Modules:**
- `cli.py` — argparse routing and all command handlers; entry point is `main()`
- `coach.py` — Anthropic SDK integration; exports `conversation()` (Opus) and `draft()` (Sonnet)
- `db.py` — SQLite CRUD for all entities; `init_db()` is idempotent with migration support
- `prompts.py` — builds system prompt (per-profile) and the cache-controlled context block (stakeholders, wins, posts, meetings, voice samples)
- `logger.py` — appends one JSONL record per LLM call to `~/.snuscoach/logs/YYYY-MM-DD/HHMMSS.jsonl`

**Model routing:**
- `coach.conversation()` → Opus with adaptive thinking — used for coaching sessions (meeting prep, debrief, chat)
- `coach.draft()` → Sonnet — used for post drafting (faster, no thinking)
- Call sites in `cli.py` pass the right function via `_iterate_with_followups(coach_fn=coach.draft)`

**Prompt caching:**
- `system_prompt()` is ephemeral (changes per profile); `context_block()` is cache-controlled (stable across turns)
- The cache-controlled block avoids re-sending the full stakeholder/meeting graph on every follow-up

**Testing patterns:**
- `test_cli.py` — subprocess tests against the installed binary; exercises argparse dispatch end-to-end
- All other test files — call CLI functions directly; mock `input()`, `_input_multiline()`, and `coach.draft/conversation()`; use a real temp SQLite DB (never mock the DB)
- `conftest.py` autouse fixtures handle isolation: temp DB path via `SNUSCOACH_DB`, logger reset, `SNUSCOACH_PROFILE` cleared
