# UI Design: snuscoach Web Interface

> **Status:** Draft v0.1 · **Owner:** Matt · **Date:** 2026-05-08
> **Framework:** NiceGUI (Python, server-side rendering)
> **Related:** [PRD §7.1](PRD.md) · [PROGRESS §6.7](PROGRESS.md)

---

## 1. Purpose & Scope

This document governs the NiceGUI web UI for snuscoach. It covers UX principles, screen-by-screen design, shared component patterns, and the technical architecture for wiring the UI to the existing `db.py` and `coach.py` modules.

**Constraints:**
- Desktop-first, single-user, local server — no authentication required
- The existing CLI (`cli.py`) remains fully functional and is not modified
- `coach.py` is not modified in the initial build (see §7 for the future streaming upgrade)
- NiceGUI serves the UI from `localhost:8080`

---

## 2. UX Principles

**Two modes — operational and admin.**
The UI distinguishes between surfaces where the user is *working with the coach* (Home, Meetings, Stakeholders, Wins & Posts, Journal) and surfaces where the user is *managing data* (Admin). Operational surfaces embed chat; the Admin section does not.

**Chat-native.**
Every operational section includes a contextual chat panel. The AI is never more than one click away, and the chat is always pre-loaded with the relevant context for that section (selected stakeholder, selected meeting, etc.).

**Home as command centre.**
The user lands on Home and immediately sees what matters: coach-generated nudges, upcoming meetings, and wins without visibility posts. They can act from there or navigate to a specific section.

**Proactive + reactive.**
Home surfaces coach nudges automatically on load. Sections enable user-initiated action: add a win, draft a post, prep a meeting. The user controls the depth of engagement.

---

## 3. Information Architecture

```
snuscoach (left nav — persistent)
├── Home                   ← default on load
├── Meetings
├── Stakeholders
├── Wins & Posts
├── Journal
└── Admin
    ├── Profile
    └── Voice Samples
```

The left nav is always visible. Each entry maps to a top-level NiceGUI page route.

---

## 4. Screen Designs

### 4.1 Home Dashboard

**Route:** `/`

**Layout:** Two-column. Left column holds widget cards (roughly 30% width). Right column (dominant, ~70%) holds the open coaching chat.

```
┌──────────────────────────────────────────────────────────────┐
│ snuscoach                                    [Profile: Dilz] │
├────────┬─────────────────────────────────────────────────────┤
│  Home  │                                                     │
│  Meet  │  Widget cards (left)   │  Open chat (right)        │
│  Stake │  ┌─────────────────┐   │                           │
│  Wins  │  │ Nudge           │   │  Coach: What's on your    │
│  Journ │  │ ...gap analysis │   │  mind today?              │
│  Admin │  │ [Open in chat ▸]│   │                           │
│        │  └─────────────────┘   │  You: Had a tough 1:1... │
│        │  ┌─────────────────┐   │  Coach: Let's unpack      │
│        │  │ Upcoming        │   │  that...                  │
│        │  │ • 1:1 Tue       │   │                           │
│        │  │ • Staff Wed     │   │  [____________________]   │
│        │  └─────────────────┘   │  [Send]                   │
│        │  ┌─────────────────┐   │                           │
│        │  │ Wins without    │   │                           │
│        │  │ post: 3 ▸       │   │                           │
│        │  └─────────────────┘   │                           │
└────────┴───────────────────────────────────────────────────-─┘
```

**Widget cards (left column, stacked):**

- **Nudge card** — On page load, runs the gap analysis (`prompts.nudge_analysis_prompt` in `report` mode) and renders the output. Has an [Open in chat] button that seeds the chat panel with the nudge content so the user can drill in interactively.
- **Upcoming meetings card** — Lists the next 3 meetings ordered by date from `db.list_meetings()`. Each row is a link that navigates to the Meetings section with that meeting pre-selected.
- **Wins gap card** — Shows the count of wins with no corresponding visibility post. Clicking navigates to Wins & Posts.

**Chat panel (right column):**
- Open coaching conversation — equivalent to `make chat`
- Messages persist within the browser session; cleared on page reload
- Input box pinned to bottom; [Send] button (also triggered by Enter)
- Coach responses rendered as markdown inside chat bubbles
- Spinner shown while the AI call is in-flight; replaced by the response on completion
- Maps to `coach.conversation()` (Opus)

---

### 4.2 Meetings Section

**Route:** `/meetings`

**Layout:** Two-column. Left data panel (~40%) + right chat panel (~60%).

```
┌────────┬──────────────────────┬──────────────────────────────┐
│  nav   │  Meetings list       │  Contextual chat             │
│        │                      │                              │
│        │  SERIES              │  [Prep this meeting]         │
│        │  ┌────────────────┐  │  [Debrief this meeting]      │
│        │  │ 1:1 w/ Alice   │  │  ──────────────────────      │
│        │  │ next: Tue      │  │                              │
│        │  │ [prep✓][deb✗] │  │  Chat pre-seeded with        │
│        │  └────────────────┘  │  selected meeting context    │
│        │  ┌────────────────┐  │                              │
│        │  │ Staff meeting  │  │                              │
│        │  └────────────────┘  │                              │
│        │  ONE-OFFS             │  [______________________]    │
│        │  ┌────────────────┐  │  [Send]                      │
│        │  │ Q2 planning    │  │                              │
│        │  └────────────────┘  │                              │
│        │  [+ New Meeting]      │                              │
└────────┴──────────────────────┴──────────────────────────────┘
```

**Data panel (left):**
- Meetings grouped by series, then one-offs (mirrors context block rendering in `prompts.py`)
- Each meeting card shows: title, date, attendees summary, status badges (prep: ✓/✗, debrief: ✓/✗)
- Clicking a meeting card loads its detail view inline (replaces the list, with a ← back link)
- Detail view: all 8 editable fields (title, series, attendees, date, prep context, prep brief, debrief notes, debrief summary); inline editing with a [Save] button per field or a single [Save all] button
- [+ New Meeting] opens a dialog with title, date, attendees, and optional series fields

**Chat panel (right):**
- When no meeting is selected: generic coaching chat with full context
- When a meeting is selected: chat is pre-seeded with that meeting's title, date, attendees, and any existing prep context / debrief notes
- [Prep this meeting] button above chat: injects a prep prompt and triggers the first AI turn
- [Debrief this meeting] button: injects a debrief prompt and triggers the first AI turn
- Maps to `coach.conversation()` (Opus)
- After a prep or debrief session, a [Save brief / Save summary] button lets the user persist the coach's output back to the meeting record

---

### 4.3 Stakeholders Section

**Route:** `/stakeholders`

**Layout:** Two-column. Left data panel (~40%) + right chat panel (~60%).

```
┌────────┬──────────────────────┬──────────────────────────────┐
│  nav   │  Stakeholders        │  Contextual chat             │
│        │                      │                              │
│        │  MANAGER             │  [Selected: Alice — Manager] │
│        │  • Alice (VP Eng)    │                              │
│        │  SKIP                │  Chat pre-seeded with        │
│        │  • Bob (CTO)         │  Alice's full profile        │
│        │  PEER                │                              │
│        │  • Carol             │  You: How should I frame     │
│        │  • Dave              │  the X project to her?       │
│        │                      │  Coach: Given she rewards... │
│        │  [+ Add Stakeholder] │                              │
│        │                      │  [______________________]    │
│        │                      │  [Send]                      │
└────────┴──────────────────────┴──────────────────────────────┘
```

**Data panel (left):**
- Stakeholders listed and grouped by `VALID_TIERS` (manager → skip → peer → cross-functional → influencer → direct-report → other)
- Each entry shows name and role; clicking loads the detail view inline
- Detail view: all stakeholder fields (role, relationship, communication style, what they reward, notes); inline editing; [Save] button
- Notes rendered as a dated log (newest entry at top); [Add Note] button appends a new dated observation
- [+ Add Stakeholder] button opens a dialog with all intake fields

**Chat panel (right):**
- When no stakeholder selected: generic coaching chat
- When a stakeholder is selected: chat pre-seeded with that person's full profile block (role, tier, comm style, what they reward, notes history)
- Maps to `coach.conversation()` (Opus)

---

### 4.4 Wins & Posts Section

**Route:** `/wins-posts`

**Layout:** Three areas. Left column split vertically: wins ledger (top) + post history (bottom). Right column: AI drafting chat.

```
┌────────┬───────────────────┬──────────────────────────────────┐
│  nav   │  Wins ledger      │  Drafting chat                   │
│        │  ┌─────────────┐  │                                  │
│        │  │ Shipped X   │  │  Coach: What would you like to   │
│        │  │ 2026-05-01  │  │  draft? A Slack post, email to   │
│        │  ├─────────────┤  │  skip, brag doc entry?           │
│        │  │ Led Y       │  │                                  │
│        │  │ 2026-04-20  │  │  You: Draft a Slack post about   │
│        │  └─────────────┘  │  shipping X for the eng channel  │
│        │  [+ Add Win]       │  Coach: Here's a draft...       │
│        │                   │                                  │
│        │  ─────────────    │  [Save Post ▾]                   │
│        │  Post history     │                                  │
│        │  • Slack #eng ... │  [______________________] [Send] │
│        │  • Email mgr ...  │                                  │
└────────┴───────────────────┴──────────────────────────────────┘
```

**Wins ledger (left top):**
- All wins from `db.list_wins()`, sorted newest-first
- Each entry shows title, truncated description, date
- Clicking a win highlights it; selected wins are mentioned in the chat context
- [+ Add Win] button → inline form (title + description textarea); saves via `db.add_win()`

**Post history (left bottom):**
- All saved posts from `db.list_posts()`, newest-first
- Each entry shows channel, audience, date, and truncated content
- Read-only; click to expand full text in a dialog

**Drafting chat (right):**
- Maps to `coach.draft()` (Sonnet) — faster, no thinking
- Pre-loaded context: full wins ledger + post history (same as CLI post command)
- User describes what to draft; AI produces the post; iterate in chat
- [Save Post] button appears below the latest AI response; clicking opens a small dialog to record channel, audience, and optional posted_at date; saves via `db.add_post()`

---

### 4.5 Journal Section

**Route:** `/journal`

**Layout:** Two-column. Left journal history (~35%) + right journal chat (~65%).

**History panel (left):**
- All entries from `db.list_journal_entries()`, newest-first
- Each entry shows date, type badge (journal / nudge), and a one-line preview
- Clicking an entry shows the full text below the list (preview pane)

**Chat panel (right):**
- On page load: auto-generates 2–3 personalised check-in questions via `prompts.journal_opening_prompt()`; first coach message pre-populated with these questions
- Multi-turn conversation; maps to `coach.draft()` (Sonnet — same as CLI journal command)
- [Save Entry] button at top of chat: saves the full conversation as a new `journal_entries` row via `db.add_journal_entry()`

---

### 4.6 Admin Section

**Route:** `/admin`

**Layout:** Single-column, no chat. Two tabs: Profile | Voice Samples.

**Profile tab:**
- Lists all user profiles (usually one) from `db.list_user_profiles()`
- Active profile highlighted; [Set as active] button on non-active profiles sets `SNUSCOACH_PROFILE` for the session
- [+ New Profile] button → form with all intake fields (name, role, org context, political strengths/weaknesses, coaching goals, communication style)
- Click a profile → inline detail view with all fields editable; [Save] button

**Voice Samples tab:**
- Lists all samples from `db.list_voice_samples()` with description and creation date
- [+ Add Sample] button → textarea for the writing sample + description field; saves via `db.add_voice_sample()`
- [Delete] button per row (with confirmation dialog)

---

## 5. Shared Components

| Component | NiceGUI primitives | Behaviour |
|---|---|---|
| Left nav | `ui.left_drawer` + `ui.link` + `ui.separator` | Fixed width; highlights the active route |
| Page header | `ui.header` | App name left; active profile chip right |
| Chat panel | `ui.column` + `ui.chat_message` + `ui.scroll_area` + `ui.input` + `ui.button` | Reusable `ChatPanel` class; accepts initial messages and a coach function |
| Data list | `ui.list` / `ui.card` inside `ui.scroll_area` | Per-section; click handler sets selected item in page state |
| Detail view | `ui.card` with `ui.input` / `ui.textarea` per field | Inline edit; [Save] triggers db update |
| Form dialog | `ui.dialog` + form fields + [Save] / [Cancel] | Used for all add-new flows |
| Spinner | `ui.spinner` | Shown inside chat bubble slot while AI call is in-flight |
| Status badge | `ui.badge` | Used for prep/debrief status on meeting cards; journal entry type |
| Confirmation dialog | `ui.dialog` with message + [Confirm] / [Cancel] | Used before destructive actions (delete voice sample) |

---

## 6. Technical Architecture

### 6.1 Module Layout

```
snuscoach/
  web/
    __init__.py
    main.py                  # ui.run() entry point; imports all page modules
    components/
      __init__.py
      nav.py                 # create_nav() — renders left drawer + header
      chat.py                # ChatPanel class — reusable chat widget
    pages/
      __init__.py
      home.py                # @ui.page('/')
      meetings.py            # @ui.page('/meetings')
      stakeholders.py        # @ui.page('/stakeholders')
      wins_posts.py          # @ui.page('/wins-posts')
      journal.py             # @ui.page('/journal')
      admin.py               # @ui.page('/admin')
```

### 6.2 Data Access

All pages import `snuscoach.db` directly. No service layer. Example:

```python
from snuscoach import db

stakeholders = db.list_stakeholders()
profile = db.get_default_profile()
```

Profile resolution follows the same logic as the CLI: read `SNUSCOACH_PROFILE` env var, fall back to the first profile in `user_profiles`.

### 6.3 AI Calls

`coach.conversation()` and `coach.draft()` are blocking (they stream to stdout). In NiceGUI, blocking calls must run off the event loop to avoid freezing the UI:

```python
import asyncio
from snuscoach import coach

async def send_message(messages):
    loop = asyncio.get_event_loop()
    reply = await loop.run_in_executor(None, coach.conversation, messages)
    return reply
```

While the executor is running, the UI shows a `ui.spinner` inside the chat panel. When the coroutine resolves, the spinner is replaced with the response rendered as a `ui.chat_message` with `ui.markdown` content.

Context assembly uses `prompts.system_prompt()` and `prompts.context_block()` directly — identical to how `coach._system_blocks()` works internally.

### 6.4 Entry Point

`snuscoach/web/main.py` imports all page modules (triggering `@ui.page` registrations) and calls:

```python
ui.run(
    title='snuscoach',
    port=int(os.getenv('SNUSCOACH_PORT', '8080')),
    show=True,           # open browser on launch
    reload=False,        # production mode
    storage_secret='snuscoach-local',
)
```

New Makefile target:
```makefile
ui: ## launch the web UI at localhost:8080
	.venv/bin/python -m snuscoach.web.main
```

New dependency in `pyproject.toml`:
```toml
"nicegui>=2.0",
```

### 6.5 Session State

NiceGUI `app.storage.user` provides per-browser-tab persistent storage (survives page navigation within a session, cleared on browser close). Used for:
- Active selected stakeholder ID
- Active selected meeting ID
- Chat message history per page

`app.storage.user` is a dict; each page uses a namespaced key (e.g. `'meetings.selected_id'`).

---

## 7. Future: Streaming AI Responses

Currently `coach._stream()` prints tokens to stdout. Once the core UI is stable, streaming can be enabled by adding an optional `on_token` callback:

```python
# coach.py — proposed future change
def conversation(messages: list[dict], on_token=None) -> str:
    return _stream(messages, OPUS_MODEL, on_token=on_token)

def _stream(messages, model, on_token=None) -> str:
    ...
    for text in stream:
        if on_token:
            on_token(text)   # UI callback: update label in-place
        else:
            print(text, end="", flush=True)  # CLI path unchanged
```

The web `ChatPanel` would pass a callback that calls `ui.run_javascript` or updates a reactive `ui.label` for each token. This is a single surgical change to `coach.py` with no CLI impact.

**Do not implement this until the spinner-then-render path is working end-to-end.**

---

## 8. Non-Goals (this phase)

- Mobile / responsive layout
- Authentication or access control
- Real-time multi-tab sync (each tab has independent session state)
- Dark / light theme toggle (NiceGUI default dark theme is used as-is)
- In-browser notifications or OS push notifications
