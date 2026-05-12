

![Snuscoach](snuscoach_logo.png)

# Snuscoach

Being technically excellent isn't enough. In most corporate environments, visibility, relationships, and narrative matter just as much as output — and engineers who aren't playing that game are often outpaced by people who are. The problem isn't that politics is unknowable; it's that nobody teaches it, there's no obvious place to practice, and the feedback loops are slow and opaque.

Snuscoach is a personal AI coach that treats politics as a learnable skill. It helps you build a durable model of your political landscape, produce concrete artifacts (posts, prep notes, brag entries) calibrated to your voice and audience, and gradually internalize the playbook so you rely on the tool less over time. All context stays on your machine in a local SQLite database; only task-scoped slices reach the Claude API.

## Status

| Phase | Scope | State |
|-------|-------|-------|
| Phase 0 — Spike | CLI + SQLite + Claude API end-to-end loop | Complete |
| Phase 1 — MVP | Full CLI feature set + NiceGUI web UI | In progress (CLI complete; web UI partial) |
| Phase 2 — Ingestion | Document upload, artifact parsing | Not started |
| Phase 3 — Smarter Coaching | Cross-session patterns, voice refinement | Not started |

See [`docs/PROGRESS.md`](docs/PROGRESS.md) for the full feature checklist.

## Quick Start

```bash
make install        # create venv and install deps
make init           # create/migrate ~/.snuscoach/snuscoach.db
make profile-create # one-time interview: role, org context, coaching goals
make chat           # open coaching session
```

Requires `ANTHROPIC_API_KEY` in `.env` (see [Configuration](#configuration)).

## Core Concepts

- **Stakeholder Graph** — per-person profiles: role, relationship tier, communication style, what they reward, dated observations, sentiment history.
- **Wins Ledger** — brag doc entries recording what you did, who saw it, and why it matters.
- **Meeting Coaching** — pre-meeting prep briefs and post-meeting debriefs with extracted follow-ups and political signals; recurring meetings belong to a persistent series thread.
- **Visibility Drafting** — audience-calibrated posts drafted from recent work descriptions, matched to your voice, with history tracked to avoid repetition.

## Typical Weekly Flow

```bash
# One-time per recurring thread
make series-add

# Before each meeting
make prep

# After each meeting
make debrief

# Log what you shipped
make win-add

# Draft a visibility post
make post

# Open coaching session
make chat

# Web UI (alternative to CLI)
make ui             # opens localhost:8080
```

## Commands

### Meeting Flow
| Command | Description |
|---------|-------------|
| `make series-add` | Create a recurring meeting thread |
| `make series` | List all series |
| `make series-show id=N` | Show a series and every meeting in it |
| `make prep` | Pre-meeting prep brief (interactive picker; iterate with coach) |
| `make debrief` | Post-meeting debrief (same picker; saves structured summary) |
| `make meetings` | List recent meetings with [prep]/[debrief] markers |
| `make meeting-show id=N` | Full lifecycle of one meeting |
| `make meeting-edit id=N` | Fix any field after the fact |

### Stakeholders
| Command | Description |
|---------|-------------|
| `make stakeholder-add name=NAME` | Interview-style intake for a new person |
| `make stakeholders` | List everyone on file, grouped by tier |
| `make stakeholder-show name=NAME` | Full profile for one person |
| `make stakeholder-note name=NAME` | Append a dated observation |

### Wins & Posts
| Command | Description |
|---------|-------------|
| `make win-add` | Log a win (title + what/who/why) |
| `make wins` | Browse the brag ledger |
| `make post` | Draft a visibility post; iterate with coach; optionally save |
| `make posts` | Browse post history |

### Chat, Journal & Nudges
| Command | Description |
|---------|-------------|
| `make chat` | Open coaching session with full context (no persistence) |
| `make journal` | Daily journal check-in (coach-prompted; saves to ledger) |
| `make journals` | List recent journal entries |
| `make nudge` | Coach detects gaps and prompts for updates |
| `make reflect` | Cross-session political pattern analysis |
| `make reflect since=YYYY-MM-DD` | Pattern analysis since a date |

### Voice Profile
| Command | Description |
|---------|-------------|
| `make voice-add` | Add a writing sample (your actual writing) |
| `make voice-list` | List voice samples |

### Scheduling & Utilities
| Command | Description |
|---------|-------------|
| `make schedule-install` | Install cron job for daily nudge (default 09:00 Mon–Fri) |
| `make schedule-show` | Show snuscoach cron entries |
| `make schedule-remove` | Remove snuscoach cron job |
| `make backup-db` | Snapshot DB to timestamped backup |
| `make purge-stubs` | Remove stub LLM responses from DB |

### Web UI
| Command | Description |
|---------|-------------|
| `make ui` | Launch NiceGUI web app at localhost:8080 |

### Development
| Command | Description |
|---------|-------------|
| `make test` | Run pytest suite |
| `make test-ui` | Run Playwright browser tests |
| `make clean` | Remove venv and build artifacts |

All `make` targets are aliases for `snuscoach <command>` — the CLI is fully usable directly.

## Architecture

**Stack:** Python ≥3.11 · SQLite · [Anthropic API](https://docs.anthropic.com/) · [NiceGUI](https://nicegui.io/)

**Model routing:**
- `claude-opus-4-7` with extended thinking — coaching sessions (prep, debrief, chat, reflect, nudge)
- `claude-sonnet-4-6` — drafting tasks (post, journal summary)

**Key modules:**

| Module | Role |
|--------|------|
| `snuscoach/cli.py` | argparse routing; all command handlers; entry point `main()` |
| `snuscoach/coach.py` | Anthropic SDK; exports `conversation()` (Opus) and `draft()` (Sonnet) |
| `snuscoach/db.py` | SQLite CRUD for all entities; `init_db()` is idempotent with migration support |
| `snuscoach/prompts.py` | Builds system prompt and cache-controlled context block |
| `snuscoach/logger.py` | Appends JSONL per LLM call to `~/.snuscoach/logs/YYYY-MM-DD/HHMMSS.jsonl` |
| `snuscoach/web/` | NiceGUI pages: home, meetings, stakeholders, wins_posts, journal, admin |

**Data residency:**
- Database: `~/.snuscoach/snuscoach.db`
- Logs: `~/.snuscoach/logs/YYYY-MM-DD/HHMMSS.jsonl`

**Prompt caching:** The context block (stakeholders, wins, posts, meetings, voice samples) is cache-controlled to avoid re-sending the full graph on every follow-up turn.

## Configuration

Copy `.env.example` to `.env` and set:

```bash
ANTHROPIC_API_KEY=sk-ant-...          # required

# Optional overrides
SNUSCOACH_DB=/path/to/custom.db       # default: ~/.snuscoach/snuscoach.db
SNUSCOACH_PROFILE=name                # select a non-default user profile
SNUSCOACH_LOG=true                    # default: true
SNUSCOACH_LOG_DIR=/path/to/logs       # default: ~/.snuscoach/logs
SNUSCOACH_PORT=8080                   # web UI port
```

## Testing

```bash
make test                             # pytest suite — 23+ test files, real SQLite, no DB mocks
make test-ui                          # Playwright browser tests
make test-ui module=meetings          # single UI module
```

Stub env vars (`SNUSCOACH_STUB_CHAT`, `SNUSCOACH_STUB_POST_DRAFT`, etc.) bypass the Claude API and return canned responses for offline development.

## Docs

- [`docs/PRD.md`](docs/PRD.md) — product spec, goals, non-goals, phasing
- [`docs/UI_DESIGN.md`](docs/UI_DESIGN.md) — NiceGUI screen designs, UX principles
- [`docs/PROGRESS.md`](docs/PROGRESS.md) — per-feature phase tracking and known gaps
