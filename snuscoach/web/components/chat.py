import asyncio
from typing import Callable

from nicegui import ui


class ChatPanel:
    """Reusable chat widget. Pass coach_fn to wire AI responses."""

    def __init__(
        self,
        placeholder: str = "What's on your mind?",
        coach_fn: Callable | None = None,
    ) -> None:
        self.messages: list[dict] = []
        self.placeholder = placeholder
        self.coach_fn = coach_fn
        self._build()

    def _build(self) -> None:
        with ui.column().classes("w-full h-full gap-0"):
            self.scroll = ui.scroll_area().classes("flex-1 w-full")
            with self.scroll:
                self.chat_column = ui.column().classes("w-full gap-2 q-pa-md")

            with ui.row().classes("w-full items-center q-pa-sm gap-2"):
                self.input = ui.input(placeholder=self.placeholder).classes(
                    "flex-1"
                ).props("outlined dense")
                ui.button("Send", on_click=self._on_send).props("dense")

        self.input.on("keydown.enter", self._on_send)

    async def _on_send(self) -> None:
        text = self.input.value.strip()
        if not text:
            return
        self.input.value = ""
        self.messages.append({"role": "user", "content": text})

        with self.chat_column:
            ui.chat_message(text, name="You", sent=True)

        await self._get_reply()
        self.scroll.scroll_to(percent=1.0)

    async def _get_reply(self) -> None:
        with self.chat_column:
            with ui.chat_message(name="Coach", sent=False) as coach_bubble:
                response_slot = ui.column().classes("w-full")
                with response_slot:
                    spinner = ui.spinner("dots", size="sm")

        if self.coach_fn:
            try:
                loop = asyncio.get_event_loop()
                reply = await loop.run_in_executor(None, self.coach_fn, list(self.messages))
            except Exception:
                reply = "(Coach unavailable — check ANTHROPIC_API_KEY)"
        else:
            reply = "(Coach not connected.)"

        spinner.delete()
        self.messages.append({"role": "assistant", "content": reply})
        with response_slot:
            ui.markdown(reply)

        self.scroll.scroll_to(percent=1.0)

    async def seed(self, text: str) -> None:
        """Pre-load a user message and trigger a coach reply."""
        self.input.value = text
        await self._on_send()
