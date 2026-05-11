import asyncio
from typing import Callable

from nicegui import ui

from snuscoach import db


class ChatPanel:
    """Reusable chat widget. Pass coach_fn to wire AI responses.

    thread_key: stable string key (e.g. "home-nudge-2026-05-08"). When set,
    prior messages are loaded from DB on init and new messages are persisted.
    Defaults to None (in-memory only).
    """

    def __init__(
        self,
        placeholder: str = "What's on your mind?",
        coach_fn: Callable | None = None,
        thread_key: str | None = None,
    ) -> None:
        self.placeholder = placeholder
        self.coach_fn = coach_fn
        self.thread_id: int | None = None
        self.messages: list[dict] = []

        if thread_key is not None:
            try:
                self.thread_id = db.get_or_create_thread(thread_key)
                rows = db.list_chat_messages(self.thread_id)
                self.messages = [{"role": r["role"], "content": r["content"]} for r in rows]
            except Exception:
                pass  # DB unavailable — degrade to in-memory mode

        # Drop any trailing user messages that have no assistant reply
        # (left over from a previous session where the LLM call failed).
        while self.messages and self.messages[-1]["role"] == "user":
            self.messages.pop()

        # Drop the last exchange if the assistant reply is an error string that
        # old code incorrectly persisted as a real reply.
        _ERROR_MARKERS = ("Coach unavailable", "Coach not connected")
        if (
            len(self.messages) >= 2
            and self.messages[-1]["role"] == "assistant"
            and any(m in self.messages[-1]["content"] for m in _ERROR_MARKERS)
        ):
            self.messages.pop()
            if self.messages and self.messages[-1]["role"] == "user":
                self.messages.pop()

        self._build()

    def _render_message(self, role: str, content: str) -> None:
        """Render a completed message into chat_column (no spinner)."""
        with self.chat_column:
            if role == "user":
                ui.chat_message(content, name="You", sent=True)
            else:
                with ui.chat_message(name="Coach", sent=False):
                    ui.markdown(content).classes("text-body2")

    def _build(self) -> None:
        with ui.column().classes("w-full h-full gap-0"):
            self.scroll = ui.scroll_area().classes("flex-1 w-full")
            with self.scroll:
                self.chat_column = ui.column().classes("w-full gap-2 q-pa-md")
                for msg in self.messages:
                    self._render_message(msg["role"], msg["content"])

            with ui.row().classes("w-full items-center q-pa-sm gap-2"):
                self.input = ui.input(placeholder=self.placeholder).classes(
                    "flex-1"
                ).props("outlined dense")
                ui.button("Send", on_click=self._on_send).props("dense")

        self.input.on("keydown.enter", self._on_send)
        if self.messages:
            self.scroll.scroll_to(percent=1.0)

    async def _on_send(self) -> None:
        text = self.input.value.strip()
        if not text:
            return
        self.input.value = ""
        self.messages.append({"role": "user", "content": text})
        self._render_message("user", text)
        await self._get_reply()
        self.scroll.scroll_to(percent=1.0)

    async def _get_reply(self) -> None:
        with self.chat_column:
            with ui.chat_message(name="Coach", sent=False):
                response_slot = ui.column().classes("w-full")
                with response_slot:
                    spinner = ui.spinner("dots", size="sm")

        error: str | None = None
        reply: str | None = None
        if self.coach_fn:
            try:
                loop = asyncio.get_event_loop()
                reply = await loop.run_in_executor(None, self.coach_fn, list(self.messages))
            except (Exception, SystemExit):
                error = "Coach unavailable — check ANTHROPIC_API_KEY"
        else:
            error = "Coach not connected."

        spinner.delete()
        if reply is not None:
            if self.thread_id is not None:
                try:
                    db.add_chat_message(self.thread_id, "user", self.messages[-1]["content"])
                    db.add_chat_message(self.thread_id, "assistant", reply)
                except Exception:
                    pass
            self.messages.append({"role": "assistant", "content": reply})
        with response_slot:
            if error is not None:
                ui.label(error).classes("text-body2 text-grey")
            else:
                ui.markdown(reply)

        self.scroll.scroll_to(percent=1.0)

    async def seed(self, text: str) -> None:
        """Pre-load a user message and trigger a coach reply.

        If the thread already has messages (restored from DB or previously seeded),
        just scroll to the bottom — don't resend.
        """
        if self.messages:
            self.scroll.scroll_to(percent=1.0)
            return
        self.input.value = text
        await self._on_send()
