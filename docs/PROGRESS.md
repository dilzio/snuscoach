# Implementation Progress

Tracks build state against the PRD. Update this when features land or scope shifts.

Last updated: 2026-05-10 · Current branch: `feature/meetings-ui`

---

## Current Phase

**Phase 0 is complete.** We are mid-Phase 1, but building CLI-first rather than jumping straight to the web UI — the CLI proves the data model and coaching flows before we add a frontend layer.

---

## Phase 0 — Spike ✅ COMPLETE

Goal: prove the loop end-to-end (CLI → DB → coach → output).

| Item | Status |
|---|---|
| Local SQLite + Claude API | ✅ |
| CLI entry point (`snuscoach`) | ✅ |
| Stakeholder intake (one person) | ✅ |
| Meeting prep brief | ✅ |
| Visibility post draft | ✅ |
| Loop validation (§10) | ✅ ingest stakeholder → meeting note → post-meeting follow-up + visibility draft in one session |

---

## Phase 1 — MVP (IN PROGRESS)

PRD goal: web chat UI + stakeholder graph + brag ledger + visibility drafting + pre/post-meeting flows + scheduled nudges + journaling + coach-initiated update prompts.

### Form factor
| Item | Status | Notes |
|---|---|---|
| Web chat UI | ❌ | Building CLI-first; web layer is next major milestone |
| Local backend serving UI | ❌ | |

### §6.1 Stakeholder Graph
| Item | Status |
|---|---|
| Per-person profiles (role, relationship, comm style, what they reward, notes) | ✅ |
| Add / list / show (CLI) | ✅ |
| Evolves over time (editable notes) | ✅ `stakeholder edit` command |
| Formal org-chart structure (manager/skip/peer/influencer tiers) | ✅ VALID_TIERS enforced at input; context block and list grouped by tier |
| Recent interactions / current sentiment tracking | ✅ `stakeholder note` prepends dated entries to notes |

### §6.2 Visibility Drafting
| Item | Status |
|---|---|
| Draft posts from recent work | ✅ |
| Audience-calibrated tone (team / manager / skip / exec) | ✅ |
| Brag doc / wins ledger | ✅ add + list |
| Save published posts to history | ✅ |
| Avoid repeating prior posts (coach sees history) | ✅ post history in context |

### §6.3 Meeting Coaching
| Item | Status |
|---|---|
| Pre-meeting prep brief | ✅ |
| Post-meeting debrief | ✅ |
| Persistent context for recurring meetings (series) | ✅ meeting_series table, coach sees thread |
| One-off meetings (no series) | ✅ |
| Multi-turn follow-up loop in prep/debrief | ✅ |

### §6.4 Coaching Conversations
| Item | Status |
|---|---|
| Open chat with full context loaded | ✅ `make chat` |
| Framework-grounded analysis (Cialdini, Crucial Conversations, etc.) | ✅ in system prompt |
| Pushes back on naive reads | ✅ in system prompt |
| Cross-session pattern surfacing — passive (coach calls out patterns in all flows) | ✅ explicit directive in system prompt; series meeting counts surface recurrence |
| Cross-session pattern surfacing — active (`make reflect [since=DATE]`) | ✅ structured brief: avoidances, stalled relationships, visibility gaps, working well |
| Reflections persisted + fed back into context (latest reflection in context block) | ✅ `reflections` table; latest reflection injected cache-controlled |

### §6.5 Context Ingestion
| Item | Status |
|---|---|
| Manual interview-style intake — user profile | ✅ `profile create` |
| Manual interview-style intake — stakeholder | ✅ `stakeholder add` |
| System-initiated update prompts | ✅ `nudge` command — gap analysis + coach-initiated check-in (interactive: Opus multi-turn; report: Sonnet numbered list) |
| Journaling / scheduled check-ins | ✅ `journal` command — coach-prompted daily check-in; `make schedule-install` manages crontab |
| Document upload | ❌ Phase 2 |
| No external integrations | ✅ design honored |

### §6.6 Proactivity
| Item | Status |
|---|---|
| Reactive coaching chat | ✅ |
| Scheduled nudges (daily journaling, weekly brag review) | ✅ `make schedule-install [time=HH:MM]` installs cron; `schedule-show` / `schedule-remove` manage it |
| Coach-initiated update prompts | ✅ `make nudge` — gap analysis drives targeted questions; mode configurable via `SNUSCOACH_NUDGE_MODE` |

### §6.7 Web UI (NiceGUI)

Design doc: [`docs/UI_DESIGN.md`](UI_DESIGN.md)

| Item | Status | Notes |
|---|---|---|
| Foundation: NiceGUI install, module layout, left nav, page routing, `make ui` | ✅ | `feature/ui-foundation`; Playwright test suite in `tests/ui/` |
| Home dashboard: open chat + nudge card + upcoming meetings card + wins-gap card | ✅ | `feature/home-dashboard`; ChatPanel wired to Opus; Playwright tests in `tests/ui/test_home_dashboard.py` |
| Meetings section: meeting list + series + detail view + prep/debrief chat | ✅ | `feature/meetings-ui`; Playwright tests in `tests/ui/test_meetings.py` |
| Stakeholders section: list by tier + detail view + add/edit + contextual chat | ❌ | |
| Wins & Posts section: wins ledger + post history + AI drafting chat + save post | ❌ | |
| Journal section: entry history + daily check-in chat | ❌ | |
| Admin section: profile list/edit + voice samples | ❌ | |
| Integration tests for web pages (NiceGUI test client) | ❌ | |

---

## Built Beyond PRD Scope

These weren't explicitly called out in the PRD but fell out naturally or were requested:

| Feature | Rationale |
|---|---|
| LLM call logging (JSONL per session) | §9 calls for an audit log of every outbound payload |
| Meeting series (recurring threads) | §6.3 "persistent context for recurring meetings" implied it |
| Voice profile capture (writing samples) | §7.4 + §9 voice-mismatch risk |
| Multi-user profile support | Requested; `user_profiles` table, `SNUSCOACH_PROFILE` env var |

---

## Technical Architecture vs PRD §7

| PRD requirement | Status | Notes                                                                     |
|---|--|---------------------------------------------------------------------------|
| Web app form factor (§7.1) | ⚠️ | In progress — NiceGUI local server; see [UI_DESIGN.md](UI_DESIGN.md)     |
| Local SQLite (§7.2) | ✅ | `~/.snuscoach/snuscoach.db`                                               |
| Task-scoped context slicing (§7.2) | ⚠️ | Full graph sent on every turn; scoping not yet implemented                |
| Claude Opus for coaching (§7.3) | ✅ | All calls use `claude-opus-4-7`                                           |
| Claude Sonnet for routine drafting (§7.3) | ✅| routine draft uses  "claude-sonnet-4-6"                            |
| Prompt caching (§7.3) | ✅ | Context block cache-controlled                                            |
| Pluggable provider interface (§7.3) | ❌ | Hardcoded Anthropic client                                                |
| Structured long-term store (§7.4) | ✅ | stakeholders, wins, posts, meetings, series, voice samples, user profiles, reflections |
| Unstructured store / journal (§7.4) | ❌ | No journal table yet                                                      |
| Hybrid retrieval / embedding search (§7.4) | ❌ | All context loaded on every turn; no retrieval layer                      |
| Voice profile (§7.4) | ✅ | `voice_samples` table, rendered into context block                        |

---

## Phase 2 — Ingestion ❌ NOT STARTED

| Item | Status |
|---|---|
| Document upload (perf reviews, org charts, 1:1 notes) | ❌ |
| Smarter parsing of pasted artifacts into the graph | ❌ |

---

## Phase 3 — Smarter Coaching ❌ NOT STARTED

| Item | Status |
|---|---|
| Cross-session pattern detection | ❌ |
| Voice-profile refinement from user edits | ❌ |
| Smarter timing of coach-initiated prompts | ❌ |

---

## Known Gaps / Tech Debt

- **Task-scoped slicing** — §7.2 says send only the task-relevant slice (e.g. one stakeholder profile), not the full graph. Currently everything is sent on every turn. Fine at low data volume; will matter when the graph grows.
- **Sonnet routing** — routine drafting (post, win log) could use Sonnet; deep coaching (debrief, prep, chat) warrants Opus. No routing yet.
- **DB migration UX** — if a user has a pre-`user_profiles` DB and runs a coaching command, they get "Database not initialized" which is misleading. Should detect existing DB with missing table and suggest `make init`.
- **Journal** — `journal_entries` table now exists; last 7 entries injected into context block. Embedding search still not implemented — all context loaded on every turn (§7.4).
- **Nudge caching** — `nudges` table persists LLM report; web UI and CLI both write to it; web UI reads cached report if one exists for today (no repeated LLM calls). Run `make init` to add the table to existing DBs.
- **Embedding / retrieval** — currently the full graph is dumped into context on every turn. Not scalable past a few hundred meetings/stakeholders.
