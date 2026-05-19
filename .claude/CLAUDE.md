# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

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
   - Write Playwright tests for all **web UI** features (in `tests/ui/`); CLI-only paths use pytest directly

3. **Always commit locally after writing code.**
   - Commit at logical checkpoints — one feature or fix per commit; no batching unrelated changes.
   - Tests and the code they cover land in the same commit.
   - Do not push to a remote unless explicitly asked. Local commits only.

4. **Always refer to PROGRESS.md when recommending/selecting the next feature to build**
   - Always update PROGRESS.md on the feature branch when the work is completed

## Project context

- Product spec: `docs/PRD.md` — read this before suggesting architectural changes. Phasing and non-goals are already locked.
- UI spec: `docs/UI_DESIGN.md` — read this before suggesting architectural changes. Phasing and non-goals are already locked.
- Progress File: `docs/PROGRESS.md` — read this before planning features.
- Phase 0 spike is built (CLI + SQLite + Anthropic SDK with prompt caching). The existing baseline is untested; when you touch a path that lacks coverage, add it.
- `make` (no target) lists every CLI command.

## Commands

```bash
make install        # create venv and install snuscoach + dev deps
make init           # initialize / migrate the SQLite DB
make ui             # launch NiceGUI web app at localhost:8080
make test           # run pytest suite excluding Playwright UI tests (-m "not ui")
make test-ui        # run Playwright browser tests (requires live server)
make                # list all CLI commands
```

Run a single CLI test:
```bash
pytest tests/test_post.py::TestPostDraft::test_post_draft_saves_last_iterated_draft
```

Run a single UI test module or specific test:
```bash
make test-ui module=test_meetings
make test-ui module=test_meetings test=test_meeting_list_shows_rows
```

Requires `ANTHROPIC_API_KEY` in `.env` (see `.env.example`). Optional overrides: `SNUSCOACH_DB`, `SNUSCOACH_PROFILE`, `SNUSCOACH_LOG_DIR`.

**LLM stub flags** — set in `.env` to skip real API calls during development:
```
SNUSCOACH_STUB_CHAT=1
SNUSCOACH_STUB_POST_DRAFT=1
SNUSCOACH_STUB_MEETING_PREP=1
SNUSCOACH_STUB_MEETING_DEBRIEF=1
SNUSCOACH_STUB_JOURNAL=1
SNUSCOACH_STUB_REFLECT=1
SNUSCOACH_STUB_NUDGE_INTERACTIVE=1
SNUSCOACH_STUB_NUDGE_REPORT=1
```
`conftest.py` autouse fixtures clear these flags so tests opt in explicitly; `.env` values never bleed into the test suite.

## Architecture

**CLI modules (`snuscoach/`):**
- `cli.py` — argparse routing and all command handlers; entry point is `main()`
- `coach.py` — Anthropic SDK integration; exports `conversation()` (Opus) and `draft()` (Sonnet)
- `db.py` — SQLite CRUD for all entities; `init_db()` is idempotent with migration support
- `prompts.py` — builds system prompt (per-profile) and the cache-controlled context block (stakeholders, wins, posts, meetings, voice samples)
- `logger.py` — appends one JSONL record per LLM call to `~/.snuscoach/logs/YYYY-MM-DD/HHMMSS.jsonl`

**Web layer (`snuscoach/web/`):**
- `web/main.py` — NiceGUI entry point; registers static files, imports all page routes, applies theme; runs on port 8080 (override via `SNUSCOACH_PORT`)
- `web/theme.py` — Quasar colour tokens + CSS custom properties applied globally via `shared=True`
- `web/pages/` — one module per section: `home`, `meetings`, `stakeholders`, `wins_posts`, `journal`, `admin`; each registers `@ui.page` routes
- `web/components/chat.py` — reusable `ChatPanel` component wired to `coach.conversation()`; shared across pages
- `web/components/nav.py` — left navigation sidebar

**Model routing:**
- `coach.conversation()` → Opus with adaptive thinking — used for coaching sessions (meeting prep, debrief, chat)
- `coach.draft()` → Sonnet — used for post drafting (faster, no thinking)
- Call sites in `cli.py` pass the right function via `_iterate_with_followups(coach_fn=coach.draft)`

**Prompt caching:**
- `system_prompt()` is ephemeral (changes per profile); `context_block()` is cache-controlled (stable across turns)
- The cache-controlled block avoids re-sending the full stakeholder/meeting graph on every follow-up

**Testing patterns:**
- `tests/test_cli.py` — subprocess tests against the installed binary; exercises argparse dispatch end-to-end
- `tests/test_*.py` — call CLI functions directly; mock `input()`, `_input_multiline()`, and `coach.draft/conversation()`; use a real temp SQLite DB (never mock the DB)
- `tests/conftest.py` autouse fixtures: isolate DB (`SNUSCOACH_DB`), logger state, `SNUSCOACH_PROFILE`, and all `SNUSCOACH_STUB_*` flags
- `tests/ui/` — Playwright tests; `tests/ui/conftest.py` spins up a **real NiceGUI server subprocess** on port 18080 with a fake API key (LLM calls fail fast); uses session-scoped `ui_server` fixture; `PYTEST_CURRENT_TEST` is stripped from the subprocess env to prevent NiceGUI entering its own screen-test mode
