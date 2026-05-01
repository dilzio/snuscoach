# PRD: Snuscoach

> **Status:** Draft v0.2 · **Owner:** Matt · **Date:** 2026-04-30
> **Audience:** Personal tool for Matt (you build it, you use it)
> **Name:** Snuscoach (locked)

---

## 1. Context

Software engineers in corporate environments are often technically excellent but politically under-developed. They underestimate the importance of visibility, stakeholder alignment, and narrative — and as a result, their work goes uncredited, their standing stagnates, and they get out-leveled by less competent but more politically fluent peers.

This is a personal AI coach that helps a politically-naive-but-aware engineer (you) systematically build skill at corporate politics: mapping the org, managing perception, producing upward-visible communications, and preparing for high-leverage interactions.

The hypothesis: politics is a learnable skill, and most of its weight is *just doing the obvious things consistently* — writing the brag doc, prepping the 1:1, posting the visibility update — which a coached engineer will actually do, where an uncoached one won't.

## 2. Goals

1. **Build a durable model of the user's political landscape** — stakeholders, relationships, dynamics, history — that compounds over time.
2. **Produce concrete, ready-to-send artifacts** — posts, status updates, brag entries, meeting prep notes — calibrated to the user's voice and the target audience.
3. **Coach skill, not just output** — explain the *why* behind suggestions so the user gradually internalizes the playbook rather than depending on the tool forever.
4. **Be private by default** — sensitive context (perf reviews, candid stakeholder reads, manager frustrations) never leaves the user's machine in unredacted form.

## 3. Non-Goals

- Not a general productivity tool, calendar app, or task manager.
- Not a multi-user / team product. No shared workspaces, no admin console.
- Not a replacement for a human mentor or executive coach — augments, not substitutes.
- Not a covert surveillance tool. The coach acts on user-volunteered context; it does not scrape co-workers.
- Not a "how to be Machiavellian" tool. Coaching biases toward authentic, sustainable influence (credibility, alignment, reciprocity), not manipulation.

## 4. Target User

**Persona: The High-Performing IC Who Can't Read the Room**
- Senior software engineer in a mid/large corporate environment
- Strong technical reputation locally; weak narrative reach beyond immediate team
- Aware that politics matters and wants to get better; not naturally inclined
- Privacy-conscious — won't paste manager 1:1 notes into a generic SaaS chatbot
- Comfortable running local tooling (CLI, local servers, API keys)

## 5. User Stories (MVP)

1. *As Matt, I want to describe my org once and have the coach remember it,* so I don't re-explain who's who every time.
2. *As Matt, after a 1:1 with my manager, I want to dump notes and get back: what to follow up on, what to surface to my skip, what political signals I missed.*
3. *As Matt, before a skip-level or staff meeting, I want a prep brief* — talking points, who to align with beforehand, what to avoid.
4. *As Matt, when I close a meaningful piece of work, I want a draft visibility post* (Slack, internal wiki, email) calibrated to the audience.
5. *As Matt, I want a weekly nudge* to update my brag doc and surface recent wins upward.
6. *As Matt, when I describe a tense interaction, I want the coach to challenge my read* — not just validate me.

## 6. Key Features

### 6.1 Stakeholder Graph
- Per-person profiles: role, reporting line, relationship to user, communication style, what they reward, recent interactions, current sentiment.
- Lightweight org chart (manager, skip, peers, cross-functional partners, influencers).
- Evolves over time as user adds observations.

### 6.2 Visibility Drafting
- Generate posts/updates from user's recent work: Slack channel update, internal wiki post, weekly email to manager, monthly skip update, brag-doc entry.
- Audience-calibrated tone (peer-broadcast vs. upward vs. exec).
- Maintains a running **brag doc / wins ledger** — every win gets logged, recallable at perf-review time.

### 6.3 Meeting Coaching
- **Pre-meeting:** agenda framing, talking points, who to pre-align with, what to listen for.
- **Post-meeting:** debrief intake → extracts follow-ups, political signals, credit-and-thanks list, items to escalate.
- Persistent context for recurring meetings (1:1s, staff, skip-level).

### 6.4 Coaching Conversations
- User describes a situation; coach analyzes through political/influence frameworks (Cialdini, Crucial Conversations, Radical Candor, "managing up" canon).
- Pushes back when user's read is naive, victim-mode, or strategically weak.
- Surfaces patterns across sessions ("third time this quarter you've avoided a hard conversation with X — worth examining?").

### 6.5 Context Ingestion
- **Manual interview-style intake** (MVP): structured Q&A to seed org graph and personal context.
- **System-initiated update prompts** (MVP): coach asks Matt for updates rather than scraping external systems — "anything new from your 1:1 this week?", "any standout PRs to log?", "what came out of the staff meeting?". This is the integration strategy: Matt is the integration.
- **Journaling / scheduled check-ins** (MVP): daily or weekly prompts ("how did standup go?", "any signals from skip this week?").
- **Document upload** (Phase 2): paste/upload org charts, perf reviews, 1:1 notes, performance plans.
- **No external integrations in scope.** Calendar, Slack, GitHub, Jira, email connectors are explicitly out for now. May revisit if user-prompted updates prove too high-friction in practice.

### 6.6 Proactivity
- Reactive chat + scheduled nudges: daily journaling prompt, weekly brag review, pre-meeting reminders driven by user-entered cadence.
- Coach-initiated update prompts (see §6.5) keep the political graph and wins ledger fresh without requiring Matt to remember to log things.

## 7. Architecture & Technical Approach

### 7.1 Form Factor
Web app. Single-user. Conversational primary surface, with structured side panels for stakeholder graph and brag ledger. Local backend serves the UI; no hosted multi-tenant infrastructure.

### 7.2 Data Residency — Local-First
- All raw context (notes, profiles, journal, brag entries) stored locally in a SQLite database.
- LLM calls send only the **task-scoped slice** needed for the current turn (e.g., one stakeholder profile + the user's question, not the whole graph). This is for token efficiency and blast-radius control, not name redaction.
- No name-tokenization / redaction layer — relying on Claude API privacy terms for content sent over the wire.
- API keys user-supplied; no managed cloud component.

### 7.3 Model
- Claude API (Opus for deep coaching/analysis, Sonnet for routine drafting) — user already operates in this ecosystem.
- Prompt caching for the long-lived persona/coaching system prompt and stable context blocks (org graph snapshot, user voice profile).
- Pluggable provider interface so model choice is not load-bearing.

### 7.4 Memory Model
- **Long-term store:** structured (stakeholders, relationships, wins ledger, meeting log) + unstructured (journal entries, raw notes).
- **Retrieval:** hybrid — structured filters for "give me everything about $person" + embedding search over unstructured journal/notes.
- **Voice profile:** small captured sample of user's writing style, used in drafting prompts so output sounds like the user, not like an LLM.

### 7.5 Phasing

| Phase | Scope | Goal |
|---|---|---|
| **0 — Spike** | Local SQLite + Claude API + CLI chat. Manual intake of one stakeholder, one drafted post, one meeting prep. | Prove the loop end-to-end. |
| **1 — MVP** | Web chat UI. Stakeholder graph, brag ledger, visibility drafting, pre/post-meeting flows, scheduled nudges, journaling, coach-initiated update prompts. | Daily-driver tool for Matt. |
| **2 — Ingestion** | Document upload (perf reviews, org charts, 1:1 notes); smarter parsing of pasted artifacts into the graph. | Reduce manual transcription cost. |
| **3 — Smarter coaching** | Cross-session pattern detection (recurring blind spots, stalled stakeholder relationships), voice-profile refinement, smarter timing of coach-initiated prompts. | Coach gets sharper as data accumulates. |

## 8. Success Metrics

Personal-tool metrics — measured by you, on you:

- **Behavioral (leading):**
  - Brag entries logged per week (target: ≥3)
  - Visibility posts published per month (target: ≥2)
  - Pre-meeting prep completed for 1:1s and skip-levels (target: 100% of skip-level, ≥75% of 1:1)
  - Weekly journaling streak

- **Outcome (lagging):**
  - Self-rated confidence in navigating political situations (quarterly 1–10)
  - Manager/skip-level perception signals (perf review language, scope expansion, stretch assignments)
  - Promotion / level progression vs. baseline trajectory

- **Skill-transfer (the real test):**
  - Frequency of user pre-empting the coach's suggestions ("I already drafted this, just sanity-check tone")
  - Decreasing reliance on the tool for situations the user previously struggled with

## 9. Risks & Open Questions

**Risks**
- *Coaching becomes sycophantic* — tool tells user what they want to hear, calcifies blind spots. **Mitigation:** explicit "challenge mode" in system prompt; periodic devil's-advocate passes.
- *Voice mismatch* — drafted posts sound like an LLM, user won't ship them. **Mitigation:** voice profile from sample writings, user-edit-loop captured to refine.
- *Privacy slip* — sensitive content leaks via API call. **Mitigation:** task-scoped slicing (never send full graph); audit log of every outbound payload; rely on Claude API privacy terms for content in flight. Accept this trade-off explicitly: no name tokenization.
- *Becomes a journaling toy* — user inputs lots, never acts. **Mitigation:** every session ends with a concrete "next action" or it doesn't count.
- *Shifts ethical line* — slides from "be visible" to "manipulate." **Mitigation:** explicit values in system prompt; coach refuses zero-sum tactics that damage others.

**Resolved decisions** (previously open questions, now locked)
- **Form factor:** web app (not desktop/Tauri). Faster to iterate; backend stays local.
- **Single-user only.** No future mentor-share mode in scope.
- **No name redaction.** Trust Claude API privacy terms; rely on task-scoped slicing for blast-radius control.
- **No direct external integrations.** Coach prompts Matt for updates; Matt is the integration.
- **Name:** Snuscoach.

## 10. Verification / How to Validate

- **Loop validation (Phase 0):** can the tool, in one session, ingest a stakeholder, accept a meeting note, and produce a usable post-meeting follow-up + visibility draft? If yes, loop works.
- **Daily-driver validation (Phase 1):** Matt uses it every working day for 30 days. Brag entries, posts, meeting prep all flow through the tool.
- **Skill-transfer validation (Phase 1+2):** quarterly self-assessment — situations user navigated well *without* tool prompting, attributable to internalized framework.
- **Outcome validation (Phase 2+):** perf review cycle. Did manager/skip's written feedback shift toward language matching the visibility narrative the tool helped construct?

## 11. Critical Files (when build starts)

Project root: `/Users/matt/Projects/snuscoach/` (currently empty)

Likely structure (TBD at implementation planning time):
- `app/` — web chat UI
- `core/` — stakeholder graph, brag ledger, journal, meeting log
- `coach/` — prompt construction, framework library, voice profile, coach-initiated update prompts
- `data/` — local SQLite + file store
