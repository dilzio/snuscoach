.PHONY: help install init chat post posts prep debrief meetings meeting-create meeting-show meeting-edit series series-add series-show series-edit stakeholders stakeholder-add stakeholder-show wins win-add backup-db test clean

SNUSCOACH := .venv/bin/snuscoach

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'
	@printf '\n\033[1mMental model\033[0m\n'
	@printf '  A MEETING is one row that holds both the prep brief (before) and the\n'
	@printf '  debrief summary (after) — same identity across the whole lifecycle.\n'
	@printf '  Recurring meetings (1:1s, staff, skip-levels) belong to a SERIES so\n'
	@printf '  the coach sees thread continuity across each occurrence. One-off\n'
	@printf '  meetings (a coffee, an interview) can skip the series entirely.\n'
	@printf '\n\033[1mTypical weekly flow\033[0m\n'
	@printf '  \033[36mmake series-add\033[0m  (one-time, per recurring thread)\n'
	@printf '    Name it like "1:1 with Sarah" or "Weekly staff". Description optional.\n'
	@printf '\n'
	@printf '  \033[36mmake prep\033[0m  (before each meeting)\n'
	@printf '    1. Picker shows the 10 most recent meetings + a [n]ew option.\n'
	@printf '       Pick a number to re-engage with an existing meeting, or n for new.\n'
	@printf '    2. NEW meeting flow: prompts for title, date, attendees, then series\n'
	@printf '       (matching series is suggested; pick a number, [n]ew, or [0] none).\n'
	@printf '    3. Editor opens for purpose/agenda/context — paste freely.\n'
	@printf '    4. Coach streams a brief. Iterate via the \033[36myou>\033[0m loop\n'
	@printf '       (answer clarifying questions, push back, refine). Empty input ends.\n'
	@printf '    5. \033[36mSave this prep brief? [Y/n]\033[0m — default Y.\n'
	@printf '    The LAST iterated reply is what gets persisted, not the rough first draft.\n'
	@printf '\n'
	@printf '  \033[36mmake debrief\033[0m  (after each meeting)\n'
	@printf '    Same picker. Pick the same meeting you prepped — the coach sees the\n'
	@printf '    prep in its context, so the debrief can compare planned vs actual.\n'
	@printf '    Editor opens for raw notes (what was said, what you felt, signals).\n'
	@printf '    Coach streams structured debrief: follow-ups, political signals,\n'
	@printf '    credit/thanks, items to escalate, what you missed, 48h next move.\n'
	@printf '    Iterate, save.\n'
	@printf '\n\033[1mWhen a meeting already has a prep or debrief\033[0m\n'
	@printf '  Re-running prep/debrief on a meeting that already has one prompts:\n'
	@printf '    \033[36m(e)dit existing / (r)edo from scratch / (c)ancel [r]\033[0m\n'
	@printf '  • \033[36me\033[0m → opens $$EDITOR seeded with the current content for\n'
	@printf '    inline cleanup. No coach call.\n'
	@printf '  • \033[36mr\033[0m → reruns the coach from scratch and replaces the saved version.\n'
	@printf '  • \033[36mc\033[0m → bail out, nothing changes.\n'
	@printf '\n\033[1mFix-ups after the fact\033[0m\n'
	@printf '  \033[36mmake meeting-edit id=N\033[0m opens a field menu:\n'
	@printf '    [1] title  [2] attendees  [3] date  [4] series\n'
	@printf '    [5] prep context (raw)    [6] prep brief (coach output)\n'
	@printf '    [7] debrief notes (raw)   [8] debrief summary (coach output)\n'
	@printf '  Long fields open $$EDITOR with current content; metadata uses prompts.\n'
	@printf '\n\033[1mBrowsing meetings\033[0m\n'
	@printf '  \033[36mmake meetings\033[0m              all meetings, newest first, with [prep]/[debrief] markers\n'
	@printf '  \033[36mmake meeting-show id=N\033[0m     full lifecycle of one meeting\n'
	@printf '  \033[36mmake series\033[0m                all series\n'
	@printf '  \033[36mmake series-show id=N\033[0m      one series and every meeting in it (chronological)\n'
	@printf '\n\033[1mThe coach\033[0m\n'
	@printf '  Snuscoach is a thin CLI wrapper around Claude. Every command (prep,\n'
	@printf '  debrief, post, chat) talks to the SAME coach with the SAME system\n'
	@printf '  prompt — your full political graph (stakeholders, wins, posts,\n'
	@printf '  meetings, series) is loaded into context on every turn, prompt-cached\n'
	@printf '  so it does not get re-billed.\n'
	@printf '  Coach behavior is tuned to PUSH BACK, not validate. If your read of a\n'
	@printf '  situation is naive or self-serving, expect the coach to say so — that\n'
	@printf '  is the value, not a bug.\n'
	@printf '  Multi-turn commands (prep, debrief, post, chat) drop into a \033[36myou>\033[0m loop\n'
	@printf '  after the first response. Type to keep iterating; Enter to finish.\n'
	@printf '\n\033[1mStakeholders — the political graph\033[0m\n'
	@printf '  One row per person you care about politically.\n'
	@printf '  \033[36mmake stakeholder-add name=NAME\033[0m  interview-style intake: role,\n'
	@printf '    relationship, communication style, what they reward, notes.\n'
	@printf '  \033[36mmake stakeholders\033[0m              list everyone on file.\n'
	@printf '  \033[36mmake stakeholder-show name=NAME\033[0m  see one full profile.\n'
	@printf '  Why it matters: when you prep a 1:1 with Sarah, the coach reads\n'
	@printf '  Sarah profile from context and tailors the brief to her style and\n'
	@printf '  what she rewards. Every coach command sees every stakeholder.\n'
	@printf '\n\033[1mWins — the brag ledger\033[0m\n'
	@printf '  Recent accomplishments worth remembering, captured as they happen.\n'
	@printf '  \033[36mmake win-add\033[0m         title + free-form description in $$EDITOR\n'
	@printf '                       (what, who saw it, why it matters).\n'
	@printf '  \033[36mmake wins\033[0m            browse the ledger.\n'
	@printf '  Why it matters: source material for visibility posts, ammunition for\n'
	@printf '  performance reviews, and signal the coach uses when shaping upward\n'
	@printf '  comms. Log wins as they happen — the brag doc you write at promotion\n'
	@printf '  time is almost always too late.\n'
	@printf '\n\033[1mPosts — visibility drafting + history\033[0m\n'
	@printf '  \033[36mmake post\033[0m  picks audience (team-broadcast / manager / skip / exec),\n'
	@printf '    opens $$EDITOR for the work description, coach drafts, iterate via\n'
	@printf '    \033[36myou>\033[0m loop. On exit: \033[36mDid you publish this? Save to history? [y/N]\033[0m.\n'
	@printf '    Yes → $$EDITOR opens seeded with the LAST iterated draft so you can\n'
	@printf '    trim to exactly what you posted, then prompts for channel and date.\n'
	@printf '  \033[36mmake posts\033[0m  browse the history.\n'
	@printf '  Why it matters: saved posts feed the coach as voice training and\n'
	@printf '  repetition-avoidance ("you posted about this last week to the same\n'
	@printf '  channel — do not repeat the framing"). Drafts get more like you.\n'
	@printf '\n\033[1mChat — open-ended coaching\033[0m\n'
	@printf '  \033[36mmake chat\033[0m  interactive \033[36myou>\033[0m / \033[36mcoach>\033[0m loop with the full context\n'
	@printf '  loaded but no persistence. Type "exit" or Ctrl-D to quit.\n'
	@printf '  Useful for: gut-check before sending a message, processing a situation\n'
	@printf '  that does not warrant a full meeting log, exploring a pattern across\n'
	@printf '  meetings, asking "what would you do here?"\n'
	@printf '\n\033[1mLogging\033[0m\n'
	@printf '  Every Claude API call (prompt + response + usage + latency) is\n'
	@printf '  appended to a JSONL log file. One file per CLI invocation, grouped\n'
	@printf '  by day:\n'
	@printf '    \033[36m~/.snuscoach/logs/YYYY-MM-DD/HHMMSS.jsonl\033[0m\n'
	@printf '  Multi-turn flows (prep, debrief, post, chat) write multiple lines\n'
	@printf '  to the same file — one per coach turn.\n'
	@printf '  Configure via .env:\n'
	@printf '    \033[36mSNUSCOACH_LOG=true\033[0m              default true; "false"/"0"/"off" disables\n'
	@printf '    \033[36mSNUSCOACH_LOG_DIR=...\033[0m           default ~/.snuscoach/logs\n'
	@printf '  Logs contain everything sent to the API (stakeholder profiles,\n'
	@printf '  meeting notes, candid reads). They are local-only and gitignored;\n'
	@printf '  treat them as private. Inspect with: \033[36mtail -n 1 LOGFILE | jq .\033[0m\n'
	@printf '\n\033[1mHow everything compounds\033[0m\n'
	@printf '  Each command writes to ONE store; every command READS all of them.\n'
	@printf '  • Add a stakeholder → every prep/debrief/post/chat sees their profile.\n'
	@printf '  • Log a win → posts and prep briefs can pull from it; coach uses it\n'
	@printf '    for perf-review framing.\n'
	@printf '  • Save a post → next draft sounds more like you and avoids repeating.\n'
	@printf '  • Save a debrief → next prep for that series sees the thread,\n'
	@printf '    grouped together so continuity is explicit.\n'
	@printf '  After a few weeks of consistent use, the coach starts referencing\n'
	@printf '  past meetings, prior posts, and stakeholder dynamics by name —\n'
	@printf '  because the context window is doing the work. That is the design:\n'
	@printf '  small inputs over time, compounding into a coach that knows your org.\n'

install:  ## Create venv and install snuscoach (run once)
	python3 -m venv .venv
	.venv/bin/pip install --upgrade pip --quiet
	.venv/bin/pip install -e . --quiet
	@echo "Installed. Set ANTHROPIC_API_KEY in .env, then run: make init"

init:  ## Initialize / migrate the local SQLite database
	$(SNUSCOACH) init

chat:  ## Open coaching chat
	$(SNUSCOACH) chat

post:  ## Draft a visibility post (offers to save on publish)
	$(SNUSCOACH) post draft

posts:  ## List saved posts
	$(SNUSCOACH) post list

prep:  ## Pre-meeting prep (alias for: meeting prep)
	$(SNUSCOACH) meeting prep

debrief:  ## Post-meeting debrief (alias for: meeting debrief)
	$(SNUSCOACH) meeting debrief

meetings:  ## List recent meetings
	$(SNUSCOACH) meeting list

meeting-create:  ## Create a new meeting (interactive)
	$(SNUSCOACH) meeting create

meeting-show:  ## Show one meeting in full (required: id=N)
	@if [ -z "$(id)" ]; then echo "Usage: make meeting-show id=N"; exit 1; fi
	$(SNUSCOACH) meeting show $(id)

meeting-edit:  ## Edit a meeting field (required: id=N)
	@if [ -z "$(id)" ]; then echo "Usage: make meeting-edit id=N"; exit 1; fi
	$(SNUSCOACH) meeting edit $(id)

series:  ## List all meeting series
	$(SNUSCOACH) series list

series-add:  ## Create a new meeting series
	$(SNUSCOACH) series add

series-show:  ## Show a series and its meetings (required: id=N)
	@if [ -z "$(id)" ]; then echo "Usage: make series-show id=N"; exit 1; fi
	$(SNUSCOACH) series show $(id)

series-edit:  ## Edit a series (required: id=N)
	@if [ -z "$(id)" ]; then echo "Usage: make series-edit id=N"; exit 1; fi
	$(SNUSCOACH) series edit $(id)

stakeholders:  ## List all stakeholders
	$(SNUSCOACH) stakeholder list

stakeholder-add:  ## Add a stakeholder (optional: name=NAME)
	$(SNUSCOACH) stakeholder add $(name)

stakeholder-show:  ## Show one stakeholder (required: name=NAME)
	@if [ -z "$(name)" ]; then echo "Usage: make stakeholder-show name=NAME"; exit 1; fi
	$(SNUSCOACH) stakeholder show "$(name)"

wins:  ## List logged wins
	$(SNUSCOACH) win list

win-add:  ## Log a new win
	$(SNUSCOACH) win add

backup-db:  ## Snapshot the local DB to a timestamped backup file
	@if [ ! -f "$$HOME/.snuscoach/snuscoach.db" ]; then \
		echo "No DB at ~/.snuscoach/snuscoach.db — nothing to back up."; \
		exit 0; \
	fi
	cp "$$HOME/.snuscoach/snuscoach.db" "$$HOME/.snuscoach/snuscoach.db.backup-$$(date +%Y%m%d-%H%M%S)"
	@echo "Backed up to ~/.snuscoach/snuscoach.db.backup-$$(date +%Y%m%d-%H%M%S)"

test:  ## Run the integration test suite
	.venv/bin/pytest

clean:  ## Remove venv and build artifacts
	rm -rf .venv build dist *.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

.DEFAULT_GOAL := help
