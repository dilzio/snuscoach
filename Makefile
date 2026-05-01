.PHONY: help install init chat post posts prep debrief meetings meeting-show stakeholders stakeholder-add stakeholder-show wins win-add test clean

SNUSCOACH := .venv/bin/snuscoach

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'
	@printf '\n\033[1mPost lifecycle (make post)\033[0m\n'
	@printf '  1. Pick audience, paste the work — coach streams a draft.\n'
	@printf '  2. Prompt: "Did you publish this? Save to history? [y/N]"\n'
	@printf '  3. If y: $$EDITOR opens pre-loaded with the draft — trim to exactly\n'
	@printf '     what you posted, save, quit.\n'
	@printf '  4. Prompt: channel (e.g. Slack #engineering, email to Sarah, wiki).\n'
	@printf '  5. Prompt: posted date (default today).\n'
	@printf '  6. Saved. Future prep/post/chat sees this in the coach context —\n'
	@printf '     it learns your voice and avoids repeating itself.\n'
	@printf '\n\033[1mWhy save matters\033[0m\n'
	@printf '  Post history is the highest-signal voice training data the coach\n'
	@printf '  has. After 5-10 finalized posts, drafts start sounding like you\n'
	@printf '  instead of like an LLM.\n'

install:  ## Create venv and install snuscoach (run once)
	python3 -m venv .venv
	.venv/bin/pip install --upgrade pip --quiet
	.venv/bin/pip install -e . --quiet
	@echo "Installed. Set ANTHROPIC_API_KEY in .env, then run: make init"

init:  ## Initialize the local SQLite database
	$(SNUSCOACH) init

chat:  ## Open coaching chat
	$(SNUSCOACH) chat

post:  ## Draft a visibility post (offers to save on publish)
	$(SNUSCOACH) post draft

posts:  ## List saved posts
	$(SNUSCOACH) post list

prep:  ## Pre-meeting prep brief
	$(SNUSCOACH) prep

debrief:  ## Post-meeting debrief (saves to meeting log)
	$(SNUSCOACH) debrief

meetings:  ## List logged meetings
	$(SNUSCOACH) meeting list

meeting-show:  ## Show one meeting in full (required: id=N)
	@if [ -z "$(id)" ]; then echo "Usage: make meeting-show id=N"; exit 1; fi
	$(SNUSCOACH) meeting show $(id)

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

test:  ## Run the integration test suite
	.venv/bin/pytest

clean:  ## Remove venv and build artifacts
	rm -rf .venv build dist *.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

.DEFAULT_GOAL := help
