import asyncio
import re
from datetime import date

from nicegui import ui

from snuscoach import coach, db
from snuscoach.web.components.chat import ChatPanel
from snuscoach.web.components.nav import create_nav

VALID_TIERS = (
    "manager", "skip", "peer", "cross-functional",
    "influencer", "direct-report", "other",
)

_TIER_OPTIONS = {t: t for t in VALID_TIERS}


def _extract_last_note_date(notes: str | None) -> str:
    if not notes:
        return "—"
    m = re.search(r"\[(\d{4}-\d{2}-\d{2})\]", notes)
    return m.group(1) if m else "—"


def _parse_notes(notes: str | None) -> list[dict]:
    """Split notes into [{date, text}] dicts. Newest first (prepended)."""
    if not notes:
        return []
    parts = re.split(r"\[(\d{4}-\d{2}-\d{2})\]", notes)
    entries = []
    i = 1
    while i + 1 < len(parts):
        text = parts[i + 1].strip()
        if text:
            entries.append({"date": parts[i], "text": text})
        i += 2
    pre = parts[0].strip()
    if pre:
        entries.append({"date": None, "text": pre})
    return entries


def _build_stakeholder_seed(s) -> str:
    lines = [f"Let's discuss {s['name']}."]
    for label, key in [
        ("Role", "role"),
        ("Tier", "relationship"),
        ("Communication style", "communication_style"),
        ("What they reward", "what_they_reward"),
        ("Notes", "notes"),
    ]:
        if s[key]:
            lines.append(f"{label}: {s[key]}")
    lines.append("\nWhat should I be thinking about in my relationship with them?")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Delete confirmation
# ---------------------------------------------------------------------------

def _confirm_delete(stakeholder_id: int, name: str, main_container: list) -> None:
    with ui.dialog() as dlg, ui.card():
        ui.label(f'Delete "{name}"?').classes("text-body2")
        ui.label("This cannot be undone.").classes("text-caption text-grey")
        with ui.row().classes("justify-end gap-2 q-mt-sm"):
            ui.button("Cancel", on_click=dlg.close).props("flat dense")
            ui.button(
                "Delete",
                on_click=lambda: (dlg.close(), _do_delete(stakeholder_id, main_container)),
            ).props("color=negative dense")
    dlg.open()


def _do_delete(stakeholder_id: int, main_container: list) -> None:
    db.delete_stakeholder(stakeholder_id)
    main_container[0].style("overflow-y: auto")
    main_container[0].clear()
    with main_container[0]:
        _render_list(main_container)
    ui.notify("Stakeholder deleted.")


# ---------------------------------------------------------------------------
# Notes section (append-only dated log)
# ---------------------------------------------------------------------------

def _render_notes_section(stakeholder_name: str, notes_container: list) -> None:
    notes_container[0].clear()
    with notes_container[0]:
        add_form: list = [None]

        with ui.row().classes("w-full items-center justify-between q-mb-xs"):
            ui.label("Notes").classes("text-overline text-bold")
            ui.button(
                "+ Add",
                on_click=lambda: add_form[0].set_visibility(True),
            ).props("flat dense size=sm")

        with ui.column().classes("w-full q-mb-sm") as af:
            af.set_visibility(False)
            add_form[0] = af
            new_note = ui.input(placeholder="New observation...").classes("w-full").props("outlined dense")

            def _save_note(_name=stakeholder_name):
                text = new_note.value.strip()
                if not text:
                    ui.notify("Note text is required.", type="warning")
                    return
                today = date.today().isoformat()
                s = db.get_stakeholder(_name)
                existing = s["notes"] or ""
                updated = f"[{today}] {text}\n{existing}".strip()
                db.update_stakeholder(_name, notes=updated)
                # notify before re-render: clear() destroys this button's parent element
                ui.notify("Note added.")
                _render_notes_section(_name, notes_container)

            with ui.row().classes("gap-2 q-mt-xs"):
                ui.button("Save", on_click=_save_note).props("color=primary dense size=sm")
                ui.button("Cancel", on_click=lambda: af.set_visibility(False)).props("flat dense size=sm")

        s_row = db.get_stakeholder(stakeholder_name)
        entries = _parse_notes(s_row["notes"] if s_row else None)

        if not entries:
            ui.label("No notes yet.").classes("text-caption text-grey")
            return

        with ui.scroll_area().classes("w-full").style("max-height: 280px"):
            with ui.column().classes("w-full gap-1"):
                for i, entry in enumerate(entries):
                    with ui.element("div").classes("w-full bordered rounded q-pa-sm"):
                        if entry["date"]:
                            ui.label(entry["date"]).classes("text-caption text-grey-5")
                        ui.label(entry["text"]).classes("text-body2")
                    if i < len(entries) - 1:
                        ui.separator().classes("q-my-xs")


# ---------------------------------------------------------------------------
# Detail view — left panel
# ---------------------------------------------------------------------------

def _render_detail_left(
    stakeholder_id: int,
    stakeholder_name: str,
    notes_container: list,
    main_container: list,
) -> None:
    s = db.get_stakeholder(stakeholder_name)
    if s is None:
        ui.label("Stakeholder not found.").classes("text-caption text-negative")
        return

    def _go_back():
        main_container[0].style("overflow-y: auto")
        main_container[0].clear()
        with main_container[0]:
            _render_list(main_container)

    ui.button("← Back", on_click=_go_back).props("flat dense").classes("q-mb-sm")

    # --- Profile section ---
    ui.separator().classes("q-my-xs")
    ui.label("Profile").classes("text-overline text-bold")
    ui.label(s["name"]).classes("text-subtitle1 text-bold q-mb-xs")

    role_in = ui.input(label="Role", value=s["role"] or "").classes("w-full")
    rel = s["relationship"]
    tier_in = ui.select(
        label="Tier",
        options=_TIER_OPTIONS,
        value=rel if rel in _TIER_OPTIONS else None,
    ).classes("w-full")
    comm_in = ui.textarea(
        label="Communication style",
        value=s["communication_style"] or "",
    ).props("rows=2 outlined").classes("w-full")
    reward_in = ui.textarea(
        label="What they reward",
        value=s["what_they_reward"] or "",
    ).props("rows=2 outlined").classes("w-full")

    def _save_profile():
        db.update_stakeholder(
            stakeholder_name,
            role=role_in.value or None,
            relationship=tier_in.value or None,
            communication_style=comm_in.value or None,
            what_they_reward=reward_in.value or None,
        )
        ui.notify("Profile saved.")

    ui.button("Save ↑", on_click=_save_profile).props("color=primary dense").classes("q-mt-sm")

    # --- Notes section ---
    ui.separator().classes("q-my-sm")
    notes_container[0] = ui.column().classes("w-full")
    _render_notes_section(stakeholder_name, notes_container)

    # --- Delete zone ---
    ui.separator().classes("q-my-sm")
    ui.button(
        "Delete ✕",
        on_click=lambda: _confirm_delete(stakeholder_id, stakeholder_name, main_container),
    ).props("flat dense color=negative")


# ---------------------------------------------------------------------------
# Open detail (list → two-column)
# ---------------------------------------------------------------------------

def _open_detail(stakeholder_id: int, stakeholder_name: str, main_container: list) -> None:
    main_container[0].style("overflow: hidden")
    main_container[0].clear()

    notes_container: list = [None]
    coach_fn = coach.stub_fn("CHAT") if coach.is_stubbed("CHAT") else coach.conversation

    with main_container[0]:
        with ui.row().classes("w-full gap-0").style("height: 100%; overflow: hidden"):
            with ui.column().style(
                "width: 40%; height: 100%; overflow-y: auto; flex-shrink: 0;"
                "background: #fff; border-right: 1px solid var(--sc-border)"
            ).classes("q-pa-md gap-1"):
                _render_detail_left(
                    stakeholder_id, stakeholder_name, notes_container, main_container
                )

            with ui.column().classes("flex-1 h-full gap-0 q-pa-sm").style(
                "display: flex; flex-direction: column"
            ):
                ui.label(f"Chat: {stakeholder_name}").classes(
                    "text-overline text-grey q-mb-xs"
                ).style("flex-shrink: 0")
                s = db.get_stakeholder(stakeholder_name)
                with ui.column().classes("w-full").style("flex: 1; min-height: 0"):
                    panel = ChatPanel(
                        placeholder=f"Ask about {stakeholder_name}...",
                        coach_fn=coach_fn,
                        thread_key=f"stakeholder-{stakeholder_id}",
                    )
                if s and not panel.messages:
                    seed_text = _build_stakeholder_seed(s)
                    ui.timer(
                        0,
                        lambda: asyncio.ensure_future(panel.seed(seed_text)),
                        once=True,
                    )


# ---------------------------------------------------------------------------
# New stakeholder dialog
# ---------------------------------------------------------------------------

def _open_new_stakeholder_dialog(main_container: list) -> None:
    with ui.dialog() as dlg, ui.card().classes("w-96"):
        ui.label("New Stakeholder").classes("text-subtitle1 text-bold q-mb-sm")
        name_in = ui.input(label="Name *").classes("w-full")
        role_in = ui.input(label="Role").classes("w-full")
        tier_in = ui.select(label="Tier", options=_TIER_OPTIONS, value=None).classes("w-full")
        comm_in = ui.textarea(label="Communication style").props("rows=2 outlined").classes("w-full")
        reward_in = ui.textarea(label="What they reward").props("rows=2 outlined").classes("w-full")
        note_in = ui.input(label="Initial note (optional)").classes("w-full")

        def _create():
            name = name_in.value.strip()
            if not name:
                ui.notify("Name is required.", type="warning")
                return
            notes_val = None
            if note_in.value.strip():
                today = date.today().isoformat()
                notes_val = f"[{today}] {note_in.value.strip()}"
            db.add_stakeholder({
                "name": name,
                "role": role_in.value or None,
                "relationship": tier_in.value or None,
                "communication_style": comm_in.value or None,
                "what_they_reward": reward_in.value or None,
                "notes": notes_val,
            })
            dlg.close()

            def _refresh():
                main_container[0].style("overflow-y: auto")
                main_container[0].clear()
                with main_container[0]:
                    _render_list(main_container)

            ui.timer(0, _refresh, once=True)

        with ui.row().classes("w-full justify-end gap-2 q-mt-sm"):
            ui.button("Cancel", on_click=dlg.close).props("flat dense")
            ui.button("Create", on_click=_create).props("color=primary dense")

    dlg.open()


# ---------------------------------------------------------------------------
# List view (full-width table grouped by tier)
# ---------------------------------------------------------------------------

def _render_group_table(stakeholders: list, main_container: list) -> None:
    if not stakeholders:
        return

    with ui.element("table").classes("w-full").style(
        "border-collapse: collapse; table-layout: fixed;"
        "border: 1px solid var(--sc-border); border-radius: 6px; overflow: hidden"
    ):
        with ui.element("thead"):
            with ui.element("tr").style(
                "border-bottom: 1px solid var(--sc-border);"
                "background: var(--sc-border-light)"
            ):
                for label, width in [
                    ("Name", "35%"),
                    ("Role", "40%"),
                    ("Last Note", "25%"),
                ]:
                    with ui.element("th").classes(
                        "sc-label text-left q-pa-xs"
                    ).style(f"width: {width}"):
                        ui.label(label)

        with ui.element("tbody"):
            for s in stakeholders:
                sid = s["id"]
                sname = s["name"]
                last_note = _extract_last_note_date(s["notes"])

                with ui.element("tr").classes("cursor-pointer").style(
                    "border-bottom: 1px solid var(--sc-border-light)"
                ):
                    with ui.element("td").classes("q-pa-xs").on(
                        "click",
                        lambda _sid=sid, _sname=sname: _open_detail(_sid, _sname, main_container),
                    ):
                        ui.label(sname).classes("text-body2 text-bold cursor-pointer")
                    with ui.element("td").classes("q-pa-xs").on(
                        "click",
                        lambda _sid=sid, _sname=sname: _open_detail(_sid, _sname, main_container),
                    ):
                        ui.label(s["role"] or "—").classes("text-caption")
                    with ui.element("td").classes("q-pa-xs").on(
                        "click",
                        lambda _sid=sid, _sname=sname: _open_detail(_sid, _sname, main_container),
                    ):
                        ui.label(last_note).classes("text-caption text-grey")


def _render_list(main_container: list) -> None:
    stakeholders = db.list_stakeholders()

    # Group by tier; unclassified / unknown tier → "other"
    tier_buckets: dict = {t: [] for t in VALID_TIERS}
    for s in stakeholders:
        rel = s["relationship"]
        bucket = tier_buckets.get(rel)
        if bucket is not None:
            bucket.append(s)
        else:
            tier_buckets["other"].append(s)

    with ui.row().classes("w-full items-center justify-between q-pb-sm").style("flex-shrink: 0"):
        with ui.row().classes("items-center gap-2"):
            ui.icon("person", size="sm").style("color: var(--sc-accent-nudge)")
            ui.label("Stakeholders").classes("text-h6")
        ui.button(
            "+ New Stakeholder",
            on_click=lambda: _open_new_stakeholder_dialog(main_container),
        ).props("flat dense")

    if not stakeholders:
        ui.label("No stakeholders yet.").classes("text-caption text-grey q-mt-sm")
        return

    with ui.scroll_area().classes("w-full").style("flex: 1"):
        for tier in VALID_TIERS:
            group = tier_buckets[tier]
            if not group:
                continue
            ui.label(tier.upper()).classes("text-overline text-bold q-mt-md q-mb-xs")
            _render_group_table(group, main_container)


# ---------------------------------------------------------------------------
# Page entry point
# ---------------------------------------------------------------------------

@ui.page("/stakeholders")
def stakeholders_page() -> None:
    create_nav("/stakeholders")

    with ui.column().classes("w-full q-pa-md").style(
        "height: calc(100vh - 56px); overflow-y: auto; display: flex; flex-direction: column;"
        "background: var(--sc-content-bg)"
    ) as outer:
        main_container: list = [outer]
        _render_list(main_container)
