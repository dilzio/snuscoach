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

**Layout:** List view is full-width (single column, no chat panel). Detail view is two-column: left data panel (~40%) + right session panel (~60%).

**Screen A — List view (default, no meeting selected):**

```
┌────────┬──────────────────────────────────────────────────────────────────┐
│  nav   │  Meetings                                       [+ New Meeting]  │
│        │                                                                  │
│        │  WEEKLY 1:1                                                      │
│        │  ┌──────────────────┬────────────┬──────────────┬───────────────┐│
│        │  │ Meeting          │ Date       │ Attendees    │ Prep  Debrief ││
│        │  ├──────────────────┼────────────┼──────────────┼───────────────┤│
│        │  │ 1:1 with Alice   │ 2026-05-13 │ Alice, Bob   │ ●[→]   ○[→]  ││
│        │  │ 1:1 with Alice   │ 2026-05-06 │ Alice        │ ○[→]   ●[→]  ││
│        │  └──────────────────┴────────────┴──────────────┴───────────────┘│
│        │                                                                  │
│        │  ONE-OFFS                                                        │
│        │  ┌──────────────────┬────────────┬──────────────┬───────────────┐│
│        │  │ Meeting          │ Date       │ Attendees    │ Prep  Debrief ││
│        │  ├──────────────────┼────────────┼──────────────┼───────────────┤│
│        │  │ Q2 Planning      │ 2026-05-10 │ Team         │ ○[→]   ○[→]  ││
│        │  └──────────────────┴────────────┴──────────────┴───────────────┘│
└────────┴──────────────────────────────────────────────────────────────────┘
```

● = session content exists · ○ = not yet generated · [→] opens that session directly

**Screen B — Detail view (meeting selected):**

```
┌────────┬──────────────────────┬──────────────────────────────┐
│  nav   │  ← Back              │  [Prep session ●][Debrief]   │
│        │                      ├──────────────────────────────┤
│        │  ── Meeting Setup ── │  Pre-meeting notes           │
│        │  Title [1:1 w/ Alice]│  [                         ] │
│        │  Date  [2026-05-13 ] │  [                         ] │
│        │  Att.  [Alice, Bob  ]│  [                (3 rows)] │
│        │  Series[Weekly 1:1 ▼]│                [Save notes ↑]│
│        │           [Save ↑]   │  ────────────────────────── │
│        │                      │  [Generate Prep Brief]       │
│        │  ── Prep ──────────  │  [Save as Prep Brief ↓]     │
│        │  [Open Prep Session→]│  ────────────────────────── │
│        │  ╔══════════════════╗│  Coach: Top 3 outcomes…      │
│        │  ║focus on Q3 goals ║│                              │
│        │  ╚══════════════════╝│  You: What if she pushes…   │
│        │  AI · read-only [✎] │  Coach: Good question…       │
│        │                      │                              │
│        │  ── Debrief ───────  │                              │
│        │  [Open Debrief Sess→]│                              │
│        │  ╔══════════════════╗│                              │
│        │  ║(not yet generated║│  [______________________]    │
│        │  ╚══════════════════╝│  [Send]                      │
│        │  AI · read-only [✎] │                              │
└────────┴──────────────────────┴──────────────────────────────┘
```

**List view (full-width, default):**
- Full-width table; no chat panel in this mode
- Meetings grouped by series (alphabetical), then one-offs; each group has a bold section header and its own table
- Columns: Meeting name, Date, Attendees, Prep, Debrief
- Prep and Debrief columns each show a filled dot (●, content exists) or empty dot (○, not yet generated), plus a [→] link that opens the detail view with that session tab active
- Clicking a meeting name row opens the detail view (Screen B); ← Back returns to the list
- [+ New Meeting] opens a dialog — title (required), date, attendees, optional series

**Detail view (left, when meeting selected):**

Three named sections; no ambiguity about what the user owns vs. what the AI produces.

*Meeting Setup* — user-owned fields: Title, Date, Attendees, Series. Single [Save meeting] button. Nothing prep- or debrief-related lives here.

*Prep* — shows the AI-generated Prep Brief as styled read-only markdown. Placeholder "Use the Prep session →" if not yet generated. [Open Prep Session →] button switches the right panel to the Prep tab. [Edit ✎] link converts the display to an editable textarea for intentional manual overrides.

*Debrief* — same structure: read-only Debrief Summary with placeholder, [Open Debrief Session →] button, [Edit ✎] link.

**Session panel (right):**

Two tabs — Prep session and Debrief session. The [Open Prep Session →] / [Open Debrief Session →] buttons on the left activate the corresponding tab. Each tab has an independent chat thread (`meeting-{id}-prep` / `meeting-{id}-debrief`).

*Prep tab:*
- "Pre-meeting notes" textarea (the user's agenda / context going *into* the meeting) + [Save notes ↑]
- [Generate Prep Brief] — injects the prep prompt and fires the first AI turn
- [Save as Prep Brief ↓] — persists the last assistant reply to `prep_brief`; prompts confirmation if overwriting existing content; left panel Prep Brief display refreshes
- Full chat history for this meeting's prep session; chat input pinned at bottom

*Debrief tab:*
- "Meeting notes" textarea (raw notes on what happened) + [Save notes ↑]
- [Generate Debrief Summary] — injects the debrief prompt
- [Save as Debrief Summary ↓] — persists to `debrief_summary`; confirmation if overwriting; left panel refreshes
- Full chat history for this meeting's debrief session

*No meeting selected:* generic coaching chat with no tabs.

Maps to `coach.conversation()` (Opus) for all session chat.

---

### 4.3 Stakeholders Section

**Route:** `/stakeholders`

**Layout:** List view is full-width (single column, no chat panel). Detail view is two-column: left data panel (~40%) + right chat panel (~60%).

**Screen A — List view (default, no stakeholder selected):**

```
┌────────┬──────────────────────────────────────────────────────────────┐
│  nav   │  Stakeholders                            [+ New Stakeholder] │
│        │                                                               │
│        │  MANAGER                                                      │
│        │  ┌──────────────────┬──────────────────┬────────────────┐   │
│        │  │ Name             │ Role             │ Last Note      │   │
│        │  ├──────────────────┼──────────────────┼────────────────┤   │
│        │  │ Alice            │ VP Engineering   │ 2026-05-01     │   │
│        │  └──────────────────┴──────────────────┴────────────────┘   │
│        │                                                               │
│        │  SKIP                                                         │
│        │  ┌──────────────────┬──────────────────┬────────────────┐   │
│        │  │ Name             │ Role             │ Last Note      │   │
│        │  ├──────────────────┼──────────────────┼────────────────┤   │
│        │  │ Bob              │ CTO              │ 2026-04-28     │   │
│        │  └──────────────────┴──────────────────┴────────────────┘   │
│        │                                                               │
│        │  PEER                                                         │
│        │  ┌──────────────────┬──────────────────┬────────────────┐   │
│        │  │ Name             │ Role             │ Last Note      │   │
│        │  ├──────────────────┼──────────────────┼────────────────┤   │
│        │  │ Carol            │ Staff Engineer   │ —              │   │
│        │  │ Dave             │ Engineering Mgr  │ 2026-05-10     │   │
│        │  └──────────────────┴──────────────────┴────────────────┘   │
└────────┴──────────────────────────────────────────────────────────────┘
```

**List view behaviour:**
- Full-width scrollable page; no chat panel in this mode.
- Stakeholders grouped by tier in `VALID_TIERS` order: manager → skip → peer → cross-functional → influencer → direct-report → other. Only non-empty tiers rendered.
- Each tier is a bold section header followed by a table.
- Columns: Name, Role, Last Note date. "Last Note date" = the most recent `[YYYY-MM-DD]` prefix extracted from the notes field; `—` if no notes exist.
- Clicking any row opens the detail view (Screen B). ← Back returns to the list.
- [+ New Stakeholder] opens a dialog — name (required), role, tier (select from VALID_TIERS), communication style, what they reward, optional initial note.

**Screen B — Detail view (stakeholder selected):**

```
┌────────┬──────────────────────────┬──────────────────────────────┐
│  nav   │  ← Back                  │  [Chat: Alice]               │
│        │                          ├──────────────────────────────┤
│        │  ── Profile ───────────  │                              │
│        │  Name  Alice             │  Coach: Alice rewards        │
│        │  Role  [VP Engineering ] │  delivering visible wins.    │
│        │  Tier  [manager       ▼]│  What's on your mind?        │
│        │  Comm  [Direct, data-  ] │                              │
│        │        [driven feedback] │  You: How do I frame the     │
│        │  Rwrd  [Outcomes and   ] │  X project to her?           │
│        │        [visibility     ] │                              │
│        │                 [Save ↑] │  Coach: Given Alice's        │
│        │                          │  focus on outcomes...        │
│        │  ── Notes ─────────────  │                              │
│        │                   [+ Add]│  [______________________]    │
│        │  ┌────────────────────┐  │  [Send]                      │
│        │  │ 2026-05-01         │  │                              │
│        │  │ Seemed stressed    │  │                              │
│        │  │ about Q3 goals     │  │                              │
│        │  ├────────────────────┤  │                              │
│        │  │ 2026-04-15         │  │                              │
│        │  │ Strong reaction to │  │                              │
│        │  │ headcount request  │  │                              │
│        │  └────────────────────┘  │                              │
│        │                          │                              │
│        │           [Delete ✕]     │                              │
└────────┴──────────────────────────┴──────────────────────────────┘
```

**Detail view — left panel:**

*Profile section* — user-editable fields:
- **Name**: displayed as read-only text (it is the unique key; renaming not supported).
- **Role**: text input.
- **Tier**: select dropdown from `VALID_TIERS` values.
- **Communication style**: textarea (multi-line).
- **What they reward**: textarea (multi-line).
- Single [Save ↑] button below all fields calls `db.update_stakeholder()`.

*Notes section* — append-only dated log:
- Displays each dated observation as a card (date label + text below), newest entry first, in a scrollable area.
- Notes are parsed from the `notes` field by splitting on `[YYYY-MM-DD]` prefixes.
- [+ Add] button opens an inline single-line input field + [Save] that prepends `[TODAY] {observation}` to the notes field via `db.update_stakeholder(name, notes=...)`.
- The log is read-only; no editing of individual entries.

*Delete zone* — at the bottom of the left panel:
- [Delete ✕] button. Opens a confirmation dialog: `"Delete {name}? This cannot be undone."` with [Cancel] / [Delete] buttons.
- On confirm: calls `db.delete_stakeholder(id)` (new function required in db.py) and returns to the list view.

**Detail view — right panel (chat):**
- Chat header shows the selected stakeholder's name as a label.
- Thread persists across sessions using thread key `stakeholder-{id}`.
- On first open (no prior messages): chat pre-seeded with the stakeholder's full profile block (role, tier, comm style, what they reward, full notes history); coach responds with a contextual opening message.
- Subsequent opens: loads and displays the existing saved thread history.
- Maps to `coach.conversation()` (Opus).

**CRUD Workflow:**

| Operation | Trigger | Function |
|---|---|---|
| Create | [+ New Stakeholder] → dialog → [Create] | `db.add_stakeholder()` |
| Read (list) | Page load | `db.list_stakeholders()` |
| Read (detail) | Click row | `db.get_stakeholder(name)` |
| Update (profile) | Edit fields → [Save ↑] | `db.update_stakeholder(name, **fields)` |
| Update (note) | [+ Add] → input → [Save] | `db.update_stakeholder(name, notes=prepended)` |
| Delete | [Delete ✕] → confirm | `db.delete_stakeholder(id)` *(new)* |

**Chat Workflow:**
- Pre-loaded context: stakeholder's full profile block, identical to what the CLI coaching session sees.
- Thread key `stakeholder-{id}` means chat history persists across page loads and sessions.
- On first open with no history: auto-seeds an opener so the chat is live on arrival, not blank.
- When no stakeholder is selected: generic coaching chat with no stakeholder context and no thread persistence.
- Maps to `coach.conversation()` (Opus).

---

### 4.4 Wins & Posts Section

**Route:** `/wins-posts`

**Layout:** List view is full-width (single column, no chat panel). Detail view is two-column: left edit panel (~40%) + right chat panel (~60%). Mirrors the Meetings section UX.

**Screen A — List view (default):**

```
┌────────┬────────────────────────────────────────────────────────────────┐
│  nav   │  Wins                                           [+ Add Win]    │
│        │  ┌──────────────────┬──────────────────────┬────────┬────────┐ │
│        │  │ Title            │ Description           │ Date   │ Posted │ │
│        │  ├──────────────────┼──────────────────────┼────────┼────────┤ │
│        │  │ Shipped X        │ Delivered key...      │ May 1  │ ✓ [↗] │ │
│        │  │ Led Y            │ —                     │ Apr 20 │   [↗] │ │
│        │  └──────────────────┴──────────────────────┴────────┴────────┘ │
│        │                                                                  │
│        │  Posts                                          [+ New Post]    │
│        │  ┌──────────────┬────────────┬──────────────┬──────────────┐   │
│        │  │ Channel      │ Date       │ Audience      │ Win          │   │
│        │  ├──────────────┼────────────┼──────────────┼──────────────┤   │
│        │  │ slack-eng    │ 2026-05-01 │ eng team      │ Shipped X    │   │
│        │  │ email-skip   │ 2026-04-25 │ —             │ —            │   │
│        │  └──────────────┴────────────┴──────────────┴──────────────┘   │
└────────┴────────────────────────────────────────────────────────────────┘
```

**Wins table (top):**
- Columns: Title | Description (truncated ~60 chars, `—` if none) | Date | Posted
- "Posted" column: green ✓ indicator if at least one post has `win_id = this win.id`; a [↗ New Post] button always present opens the Save Post dialog pre-linked to this win
- Clicking a row (Title / Description / Date cell) → opens Win detail view (Screen B)
- [+ Add Win] button → dialog (title required, description optional); saves via `db.add_win()`

**Posts table (bottom):**
- Columns: Channel | Posted at | Audience (`—` if none) | Win (linked win title, or `—`)
- Clicking a row opens the post expand/edit dialog (full content rendered as `ui.markdown`, with inline [Edit] mode backed by `db.update_post()`)
- [+ New Post] button → opens Save Post dialog with no pre-linked win

---

**Screen B — Win detail view:**

```
┌────────┬──────────────────────────┬──────────────────────────────┐
│  nav   │  ← Back                  │  Chat: Shipped X             │
│        │                          ├──────────────────────────────┤
│        │  ── Win Details ───────  │                              │
│        │  Title  [Shipped X     ] │  You: Help me write a        │
│        │  Description:            │  stronger description...     │
│        │  [                    ]  │                              │
│        │  [                    ]  │  Coach: Here's a tighter     │
│        │  [          (4 rows)  ]  │  version: …                  │
│        │                 [Save ↑] │                              │
│        │                          │  [Adopt AI draft ↓]          │
│        │  Created: 2026-05-01     │                              │
│        │                          │  [________________________]  │
│        │  ── Linked posts ──────  │  [Send]                      │
│        │  • 2026-05-01 slack-eng  │                              │
│        │  [+ New Post for Win]    │                              │
└────────┴──────────────────────────┴──────────────────────────────┘
```

**Detail view — left panel:**
- ← Back returns to list view
- **Win Details**: Title (text input), Description (textarea, ~4 rows), [Save Win] button → `db.update_win(win_id, title, description)`
- Created at shown as read-only label
- **Linked posts**: lists posts where `win_id = this win.id` (channel + date per row); clicking a row opens the post expand/edit dialog
- [+ New Post for Win] → Save Post dialog pre-linked to this win

**Detail view — right panel (chat):**
- Label: "Chat: {win title}"
- Thread key: `win-{id}` — persistent across sessions
- Maps to `coach.draft()` (Sonnet)
- **No auto-LLM call on open** — chat loads prior thread history and waits; coach is only invoked when the user sends their first message
- **[Adopt AI draft ↓]** button fixed in right panel header: reads the last assistant reply and writes it into the Description textarea on the left (does not auto-save; user must click [Save Win])

**CRUD Workflow:**

| Operation | Trigger | Function |
|---|---|---|
| Create win | [+ Add Win] → dialog | `db.add_win()` |
| Read wins (list) | Page load | `db.list_wins()` |
| Read win (detail) | Click row | pass win dict from list |
| Update win | [Save Win] in detail | `db.update_win(win_id, title, description)` |
| Create post | [↗ New Post] or [+ New Post for Win] | `db.add_post(win_id=...)` |
| Read posts (list) | Page load | `db.list_posts()` |
| Update post | [Edit] in expand dialog | `db.update_post()` |

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
