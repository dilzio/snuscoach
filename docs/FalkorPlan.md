# FalkorDB Migration Plan

## Context

The current SQLite schema is a flat relational model that cannot express org-chart traversals, meeting attendance patterns, or stakeholder relationship networks natively. FalkorDB (property graph + Cypher) lets the coach query things like "who are the common attendees across Alice's series and the staff meeting?" or "path from me to the VP via existing relationships?" — which are impossible in SQLite without Python post-processing.

**Decision:** Full replacement (no hybrid), FalkorDB via Docker, standard `falkordb` Python client (v1.6.1 — already installed in `.venv`), same public API surface so `cli.py`/`prompts.py` changes are minimal.

**Note on embedded mode:** `falkordblite` ships ARM64 binaries only and is incompatible with Intel Mac (x86_64). Use Docker.

---

## Infrastructure Changes

**Docker run command** (one-liner, no compose needed):
```
docker run -p 6379:6379 --name falkordb -d falkordb/falkordb:latest
```

**New Makefile targets:**
```makefile
db-start:   ## Start FalkorDB (Docker required)
db-stop:    ## Stop FalkorDB container
db-logs:    ## Tail FalkorDB container logs
migrate:    ## Migrate data from SQLite → FalkorDB (run once after db-start)
```

**New `.env` vars:**
```
FALKORDB_HOST=localhost
FALKORDB_PORT=6379
SNUSCOACH_GRAPH=snuscoach        # graph name (tests use a unique name per run)
```

**`pyproject.toml`:** add `falkordb>=1.6.0` to dependencies (already installed in `.venv`).

---

## Graph Schema

### Node Labels + Properties

| Label | Properties | Replaces |
|---|---|---|
| `User` | name, role, org_context, political_strengths, political_weaknesses, coaching_goals, communication_style, created_at, updated_at | `user_profiles` |
| `Stakeholder` | name, role, communication_style, what_they_reward, notes (unstructured general notes only), created_at, updated_at | `stakeholders` (notes field split out) |
| `Observation` | text, date (YYYY-MM-DD), created_at | replaces dated `[YYYY-MM-DD] ...` entries from stakeholder notes |
| `MeetingSeries` | name, description, created_at, updated_at | `meeting_series` |
| `Meeting` | title, attendees (freetext, kept for display), date, prep_context, prep_brief, debrief_notes, debrief_summary, created_at, updated_at | `meetings` |
| `Win` | title, description, created_at | `wins` |
| `Post` | content, channel, audience, posted_at, created_at | `posts` |
| `VoiceSample` | content, description, created_at | `voice_samples` |
| `Reflection` | content, since_date, created_at | `reflections` |
| `JournalEntry` | content, coach_prompt, entry_type, created_at, updated_at | `journal_entries` |

### Relationship Types

```
(User)-[:REPORTS_TO]->(Stakeholder)         # tier=manager
(User)-[:SKIP_REPORTS_TO]->(Stakeholder)    # tier=skip
(User)-[:PEERS_WITH]->(Stakeholder)         # tier=peer
(User)-[:WORKS_WITH]->(Stakeholder)         # tier=cross-functional/influencer/direct-report/other

(Stakeholder)-[:ATTENDED]->(Meeting)        # NEW — parsed best-effort from attendees field
(User)-[:ATTENDED]->(Meeting)               # always created

(Meeting)-[:IN_SERIES]->(MeetingSeries)

(User)-[:OBSERVED]->(Observation)
(Observation)-[:ABOUT]->(Stakeholder)       # replaces notes append-only field

(User)-[:LOGGED]->(Win)
(User)-[:PUBLISHED]->(Post)
(User)-[:AUTHORED]->(VoiceSample)
(User)-[:REFLECTED]->(Reflection)
(User)-[:JOURNALED]->(JournalEntry)
```

---

## New Files

### `snuscoach/graph_db.py`

Full replacement for `db.py`. Same public function signatures, same return types (plain dicts, same keys as old `sqlite3.Row` objects). Internal IDs use FalkorDB's `id(n)` integer — compatible with existing CLI argparse (`id=N` args).

**Connection helpers:**
```python
def _client() -> FalkorDB:   # reads FALKORDB_HOST/PORT from env
def _graph() -> Graph:       # reads SNUSCOACH_GRAPH from env; calls _client()
def _now() -> str:           # ISO timestamp, same as db.py
```

**Initialization:**
```python
def init_db() -> None:       # creates indexes (kept as init_db for CLI compat)
```
Creates indexes:
```cypher
CREATE INDEX FOR (n:Stakeholder) ON (n.name)
CREATE INDEX FOR (n:User) ON (n.name)
CREATE INDEX FOR (n:Meeting) ON (n.date)
CREATE INDEX FOR (n:Win) ON (n.created_at)
CREATE INDEX FOR (n:JournalEntry) ON (n.created_at)
CREATE INDEX FOR (n:Observation) ON (n.date)
```

**Key design — returning dicts:** Each entity type has a `_to_dict(node)` helper that converts a FalkorDB Node object to a plain dict with the exact same keys callers expect. IDs come from `id(n)` queried inline.

**Stakeholder functions:**
- `add_stakeholder(profile: dict) -> int` — CREATE node + relationship edge to default User
- `list_stakeholders() -> list[dict]` — MATCH all Stakeholder nodes, ordered by name
- `get_stakeholder(name: str) -> dict | None`
- `update_stakeholder(name: str, **fields) -> None`
- `add_observation(stakeholder_name: str, text: str, obs_date: str) -> int` — NEW; creates Observation node linked to Stakeholder + User
- `list_observations(stakeholder_name: str) -> list[dict]` — returns observations newest-first

**Stakeholder dict keys:** `{id, name, role, relationship, communication_style, what_they_reward, notes, created_at, updated_at}` — `relationship` is derived from the relationship type on the edge to User.

**All other entity CRUD functions:** direct translation of `db.py` functions into Cypher with identical signatures.

**New graph-native queries (not in db.py):**
```python
def get_org_neighbors(profile_id: int) -> dict:
    # Returns {manager, skip, peers, cross_functional} — used in context_block
def get_meeting_attendees(meeting_id: int) -> list[dict]:
    # MATCH (s:Stakeholder)-[:ATTENDED]->(m:Meeting) WHERE id(m) = $id
```

---

### `snuscoach/migrate.py`

One-shot migration from SQLite to FalkorDB. Entry point: `python -m snuscoach.migrate` (also wired to `make migrate`).

**Steps:**
1. Connect to both SQLite (via existing `sqlite_db.py`) and FalkorDB (via new `graph_db.py`)
2. Migrate in dependency order: User profiles → Stakeholders → Wins → Posts → MeetingSeries → Meetings → VoiceSamples → Reflections → JournalEntries
3. Stakeholder notes: parse `[YYYY-MM-DD] text` lines → Observation nodes; remaining text → keep as `notes` property
4. Meetings: attendees freetext → split on comma, strip, match against Stakeholder names (case-insensitive) → create `ATTENDED` edges for matches
5. Print progress per entity type, print summary of unmatched attendees

---

## Modified Files

### `snuscoach/db.py` → renamed `snuscoach/sqlite_db.py`

Kept intact for use by `migrate.py`. After migration is verified, can be deleted.

### `snuscoach/coach.py`

Two-line change: `from snuscoach import db` → `from snuscoach import graph_db as db`. The function signatures and return types match, so nothing else changes.

### `snuscoach/cli.py`

- Import: `from snuscoach import graph_db as db`
- `cmd_stakeholder_note()`: call `db.add_observation(name, obs, date)` instead of prepending to notes string
- `cmd_stakeholder_show()`: query `db.list_observations(name)` and display below the stakeholder properties; notes property still displayed if present
- `cmd_stakeholder_edit()`: field [5] "Notes" edits the `notes` property (general unstructured notes); field [6] NEW "Add observation" calls `add_observation`; remove the raw multiline editor for notes since dated observations are separate
- `_compute_nudge_gaps()`: replace regex date parsing with `db.list_observations(s["name"])` and check max date

### `snuscoach/prompts.py`

- `context_block()`: add `observations: dict[str, list]` parameter (keyed by stakeholder name, value = list of Observation dicts from `list_observations`)
- `_render_one_stakeholder()`: replace `Notes: {s['notes']}` with rendered observations + general notes
- `_render_stakeholders_block()`: pass observations through
- No signature changes to public functions that would break callers

### `tests/conftest.py`

Replace `temp_db_path` fixture with `temp_graph` fixture:
```python
@pytest.fixture(autouse=True)
def temp_graph(monkeypatch):
    graph_name = f"snuscoach_test_{uuid.uuid4().hex[:8]}"
    monkeypatch.setenv("SNUSCOACH_GRAPH", graph_name)
    graph_db.init_db()
    yield graph_name
    # teardown: delete graph
    try:
        graph_db._graph().delete()
    except Exception:
        pass
```

Tests that previously used `temp_db` now use `temp_graph`. The `temp_db_path` fixture is removed. All tests that used `db.connect()` directly for seeding old-schema data will need to be rewritten using `graph_db` functions.

**Migration test** (`test_db.py::test_migration_from_old_schema`): removed — replaced with a `test_migrate.py` that seeds SQLite via `sqlite_db`, runs `migrate.main()`, and verifies FalkorDB contains the correct nodes/edges.

---

## Implementation Order

1. Docker infra + Makefile targets + `.env.example` + `pyproject.toml`
2. `snuscoach/graph_db.py` — full CRUD layer
3. `snuscoach/migrate.py` — migration script
4. Rename `db.py` → `sqlite_db.py`, update imports in `migrate.py`
5. Update `coach.py` (2 lines)
6. Update `cli.py` — import + stakeholder note/show/edit + `_compute_nudge_gaps`
7. Update `prompts.py` — `context_block` observations rendering
8. Update `tests/conftest.py` — FalkorDB graph fixture
9. Update all test files — replace db calls, update stakeholder-notes assertions
10. Commit

---

## Verification

```bash
# Start FalkorDB
make db-start

# Init graph schema (creates indexes)
make init

# Run full test suite (requires running FalkorDB)
make test

# If migrating existing data:
make migrate   # reads from ~/.snuscoach/snuscoach.db, writes to FalkorDB

# Smoke test: add a stakeholder, verify graph
snuscoach stakeholder add
snuscoach stakeholders        # should show stakeholder
snuscoach stakeholder note    # enter an observation
snuscoach stakeholder show    # should show observation with date

# Verify graph queries work
snuscoach chat    # coach should load full context from FalkorDB
```

---

## Critical Files

| File | Status | Notes |
|---|---|---|
| `snuscoach/graph_db.py` | NEW | Core data layer |
| `snuscoach/migrate.py` | NEW | One-shot migration |
| `snuscoach/db.py` | RENAME → `sqlite_db.py` | Kept for migration only |
| `snuscoach/coach.py` | MINOR | Import change only |
| `snuscoach/cli.py` | MODERATE | Import + stakeholder note/show/edit + gap detection |
| `snuscoach/prompts.py` | MODERATE | `context_block` observations |
| `tests/conftest.py` | REWRITE | FalkorDB graph fixture |
| `tests/test_db.py` | REWRITE | All db tests → graph_db |
| `tests/test_journal.py` | MINOR | Fixture rename only |
| `tests/test_nudge.py` | MODERATE | Fixture + observation-based gap detection |
| `tests/test_reflect.py` | MINOR | Fixture rename only |
| `tests/test_migrate.py` | NEW | Migration correctness |
| `pyproject.toml` | MINOR | Add falkordb dep |
| `Makefile` | MINOR | Add db-start/stop/logs/migrate |
| `.env.example` | MINOR | Add FALKORDB_HOST/PORT/GRAPH |

## Prerequisites for Implementation

- Docker must be running on the target machine
- `falkordb>=1.6.0` Python package (already in `.venv` as of 2026-05-07)
- **Do not use `falkordblite`** — it ships ARM64 binaries and is incompatible with Intel Mac (x86_64)
- Run `make db-start` before `make test` or `make migrate`
