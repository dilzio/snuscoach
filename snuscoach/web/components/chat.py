from nicegui import ui


class ChatPanel:
    """Reusable chat widget. Wired to coach functions in later passes."""

    def __init__(self, placeholder: str = "What's on your mind?") -> None:
        self.messages: list[dict] = []
        self.placeholder = placeholder
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
        with self.chat_column:
            ui.chat_message(text, name="You", sent=True)
            ui.chat_message("(Coach responses will appear here once wired up.)", name="Coach")
        self.scroll.scroll_to(percent=1.0)
