.PHONY: help install init chat post posts prep debrief meetings meeting-create meeting-show meeting-edit series series-add series-show series-edit stakeholders stakeholder-add stakeholder-show wins win-add backup-db test clean

SNUSCOACH := .venv/bin/snuscoach

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'
	@printf '\n\033[1mMeeting lifecycle\033[0m\n'
	@printf '  Each meeting is one row holding both prep and debrief. Recurring\n'
	@printf '  meetings (1:1s, staff) belong to a series so the coach sees thread\n'
	@printf '  continuity across them.\n\n'
	@printf '  1. (optional) make series-add — define a recurring thread once.\n'
	@printf '  2. make prep — picker shows recent meetings; pick or create new.\n'
	@printf '     For new: title, date, attendees, attach to series. Coach streams\n'
	@printf '     a brief; iterate via the you> loop; save.\n'
	@printf '  3. make debrief — same picker; for the same meeting after it happens.\n'
	@printf '     Coach has the prep in context. Iterate, save.\n'
	@printf '  4. make meeting-edit id=N — fix any field after the fact (title,\n'
	@printf '     date, series, raw inputs, coach outputs).\n\n'
	@printf '\033[1mWhy save matters\033[0m\n'
	@printf '  Saved posts and meeting summaries feed the coach context next time.\n'
	@printf '  After 5-10 saves, drafts/briefs sound like you and reference past\n'
	@printf '  meetings in the same series — that is the compounding context.\n'

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
