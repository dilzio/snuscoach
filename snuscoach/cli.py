import argparse
import os
import shlex
import subprocess
import sys
import tempfile
import textwrap
from datetime import date, datetime

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

from snuscoach import coach, db, logger


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _iterate_with_followups(initial_user_msg: str) -> tuple[list[dict], str]:
    """Run an initial coach turn, then prompt for inline follow-ups.

    Streams the first response, then loops on `you> ` prompts. Empty input
    or EOF ends the conversation. Returns (full message history, last
    assistant text).
    """
    messages: list[dict] = [{"role": "user", "content": initial_user_msg}]
    reply = coach.conversation(messages)
    messages.append({"role": "assistant", "content": reply})
    while True:
        try:
            print()
            followup = input("you> (empty to finish) ").strip()
        except EOFError:
            print()
            break
        if not followup:
            break
        messages.append({"role": "user", "content": followup})
        print("coach> ", end="", flush=True)
        reply = coach.conversation(messages)
        messages.append({"role": "assistant", "content": reply})
    return messages, reply


def _input_multiline(label: str, initial: str = "") -> str:
    """Open $EDITOR on a temp file for editable multiline input."""
    editor = os.environ.get("EDITOR") or os.environ.get("VISUAL") or "vi"
    header = (
        f"# {label}\n"
        "# Lines starting with '#' are ignored. Save and quit when done.\n"
        "# Leave the file empty (or quit without saving content) to skip.\n\n"
    )
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".md", delete=False, encoding="utf-8"
    ) as f:
        f.write(header)
        if initial:
            f.write(initial)
            if not initial.endswith("\n"):
                f.write("\n")
        path = f.name
    try:
        print(f"Opening {editor} for: {label}")
        subprocess.run(f"{editor} {shlex.quote(path)}", shell=True, check=True)
        with open(path, encoding="utf-8") as f:
            content = f.read()
    finally:
        os.unlink(path)
    body = "\n".join(
        ln for ln in content.splitlines() if not ln.lstrip().startswith("#")
    )
    return body.strip()


def _parse_date(raw: str) -> str:
    try:
        return datetime.strptime(raw, "%Y-%m-%d").date().isoformat()
    except ValueError:
        sys.exit(f"Invalid date '{raw}'. Expected YYYY-MM-DD.")


# ---------------------------------------------------------------------------
# Init / stakeholders / wins / posts (unchanged from prior versions)
# ---------------------------------------------------------------------------


def cmd_init(_args):
    db.init_db()
    print(f"Initialized database at {db.db_path()}")


def cmd_stakeholder_add(args):
    print("Add stakeholder. Press Enter to skip optional fields.\n")
    name = (getattr(args, "name", None) or "").strip() or input("Name: ").strip()
    if not name:
        sys.exit("Name is required.")
    if db.get_stakeholder(name):
        sys.exit(f"Stakeholder '{name}' already exists.")
    print(f"Name: {name}")
    role = input("Role/title: ").strip() or None
    relationship = (
        input("Relationship (manager/skip/peer/cross-functional/other): ").strip()
        or None
    )
    communication_style = (
        input("Communication style (e.g. terse, data-driven, social): ").strip()
        or None
    )
    what_they_reward = input("What do they reward / care about?: ").strip() or None
    notes = _input_multiline("Notes")
    sid = db.add_stakeholder(
        {
            "name": name,
            "role": role,
            "relationship": relationship,
            "communication_style": communication_style,
            "what_they_reward": what_they_reward,
            "notes": notes or None,
        }
    )
    print(f"\nAdded stakeholder #{sid}: {name}")


def cmd_stakeholder_list(_args):
    rows = db.list_stakeholders()
    if not rows:
        print("No stakeholders yet. Run: snuscoach stakeholder add")
        return
    for r in rows:
        rel = r["relationship"] or "?"
        role = r["role"] or "?"
        print(f"  {r['name']} — {rel}, {role}")


def cmd_stakeholder_show(args):
    s = db.get_stakeholder(args.name)
    if not s:
        sys.exit(f"No stakeholder named '{args.name}'.")
    print(f"# {s['name']}")
    for label, key in [
        ("Role", "role"),
        ("Relationship", "relationship"),
        ("Communication style", "communication_style"),
        ("What they reward", "what_they_reward"),
        ("Notes", "notes"),
    ]:
        if s[key]:
            print(f"{label}: {s[key]}")


def cmd_win_add(_args):
    title = input("Win title (one line): ").strip()
    if not title:
        sys.exit("Title is required.")
    description = _input_multiline(
        "Description (what, who saw it, why it matters)"
    )
    wid = db.add_win(title, description or None)
    print(f"Logged win #{wid}: {title}")


def cmd_win_list(_args):
    rows = db.list_wins()
    if not rows:
        print("No wins logged yet. Run: snuscoach win add")
        return
    for r in rows:
        print(f"  [{r['created_at'][:10]}] {r['title']}")


def cmd_post_draft(_args):
    print("Draft a visibility post.\n")
    audience = (
        input("Audience (team-broadcast / manager / skip / exec / other): ").strip()
        or "team-broadcast"
    )
    work = _input_multiline(
        "What did you do? (paste freely — describe the work, context, outcome)"
    )
    if not work.strip():
        sys.exit("Empty work description.")
    user_msg = textwrap.dedent(
        f"""
        TASK: Draft a visibility post.

        Audience: {audience}
        Work:
        {work}

        Output:
        1. The draft, ready to copy-paste. Use whatever format fits the channel (markdown, plain text, email-style).
        2. A short coda: who else should see this, what to drop or shorten if I want a tighter version, and what the political move is here.
        """
    ).strip()
    _, draft_output = _iterate_with_followups(user_msg)

    print()
    answer = input("Did you publish this? Save to history? [y/N]: ").strip().lower()
    if answer not in ("y", "yes"):
        print("Not saved.")
        return

    final = _input_multiline(
        "Finalize the posted content (edit down to exactly what you posted)",
        initial=draft_output,
    )
    if not final:
        print("Empty final content; not saved.")
        return

    channel = input("Channel (e.g. Slack #engineering, email to manager, wiki): ").strip()
    while not channel:
        channel = input("Channel is required: ").strip()

    today = date.today().isoformat()
    posted_at_raw = input(f"Posted date [YYYY-MM-DD, default {today}]: ").strip() or today
    posted_at = _parse_date(posted_at_raw)

    pid = db.add_post(final, channel, audience, posted_at)
    print(f"Saved post #{pid} to history ({channel}, {posted_at}).")


def cmd_post_list(_args):
    rows = db.list_posts()
    if not rows:
        print("No posts saved yet. Run: snuscoach post draft")
        return
    for r in rows:
        audience = f" / {r['audience']}" if r["audience"] else ""
        first_line = r["content"].splitlines()[0] if r["content"] else ""
        snippet = first_line[:80] + ("…" if len(first_line) > 80 else "")
        print(f"  #{r['id']} [{r['posted_at']}] {r['channel']}{audience}: {snippet}")


# ---------------------------------------------------------------------------
# Meeting series
# ---------------------------------------------------------------------------


def _create_series_interactive(default_name: str = "") -> int:
    name_prompt = f"Series name{f' [{default_name}]' if default_name else ''}: "
    name = input(name_prompt).strip() or default_name
    if not name:
        sys.exit("Series name is required.")
    if db.get_meeting_series_by_name(name):
        sys.exit(f"Series '{name}' already exists.")
    description = input("Description (optional): ").strip() or None
    sid = db.add_meeting_series(name, description)
    print(f"Created series #{sid}: {name}")
    return sid


def _pick_or_create_series(default_name: str = "") -> int | None:
    """Prompt the user to pick an existing series, create a new one, or skip."""
    rows = db.list_meeting_series()
    if not rows:
        choice = input(
            f"No series yet. Create a series for this meeting? [Y/n]: "
        ).strip().lower()
        if choice in ("n", "no"):
            return None
        return _create_series_interactive(default_name=default_name)

    print("\nSeries:")
    suggested = None
    for i, s in enumerate(rows, start=1):
        marker = ""
        if default_name and s["name"].lower() == default_name.lower():
            suggested = i
            marker = " (suggested)"
        print(f"  [{i}] {s['name']}{marker}")
    print("  [n] new series")
    print("  [0] no series")

    default_choice = str(suggested) if suggested else "0"
    choice = (
        input(f"Pick (default {default_choice}): ").strip().lower() or default_choice
    )
    if choice in ("0", "none"):
        return None
    if choice in ("n", "new"):
        return _create_series_interactive(default_name=default_name)
    try:
        idx = int(choice)
        if 1 <= idx <= len(rows):
            return rows[idx - 1]["id"]
    except ValueError:
        pass
    sys.exit(f"Invalid choice: {choice}")


def cmd_series_add(_args):
    _create_series_interactive()


def cmd_series_list(_args):
    rows = db.list_meeting_series()
    if not rows:
        print("No series yet. Run: snuscoach series add")
        return
    for r in rows:
        desc = f" — {r['description']}" if r["description"] else ""
        print(f"  #{r['id']} {r['name']}{desc}")


def cmd_series_show(args):
    s = db.get_meeting_series(args.id)
    if not s:
        sys.exit(f"No series #{args.id}.")
    print(f"# {s['name']}")
    if s["description"]:
        print(f"Description: {s['description']}")
    print(f"Created: {s['created_at']}")
    meetings = db.list_meetings_by_series(args.id)
    print(f"\nMeetings ({len(meetings)}):")
    if not meetings:
        print("  (none)")
        return
    for m in meetings:
        attendees = f" — {m['attendees']}" if m["attendees"] else ""
        markers = []
        if m["prep_brief"]:
            markers.append("prep")
        if m["debrief_summary"]:
            markers.append("debrief")
        marker_str = f" [{', '.join(markers)}]" if markers else ""
        print(f"  #{m['id']} [{m['date']}] {m['title']}{attendees}{marker_str}")


def cmd_series_edit(args):
    s = db.get_meeting_series(args.id)
    if not s:
        sys.exit(f"No series #{args.id}.")
    print(f"\nEditing series #{s['id']}: {s['name']}\n")
    print("Fields:")
    print("  [1] name")
    print("  [2] description")
    choice = input("Field to edit [1-2]: ").strip()
    if choice == "1":
        new = input(f"Name [{s['name']}]: ").strip()
        if new:
            db.update_meeting_series(args.id, name=new)
            print("Updated.")
    elif choice == "2":
        new = input(f"Description [{s['description'] or ''}]: ").strip()
        db.update_meeting_series(args.id, description=new or "")
        print("Updated.")
    else:
        sys.exit(f"Invalid choice: {choice}")


# ---------------------------------------------------------------------------
# Meetings
# ---------------------------------------------------------------------------


def _create_meeting_interactive() -> dict:
    title = input("Title: ").strip()
    if not title:
        sys.exit("Title is required.")
    today = date.today().isoformat()
    date_raw = input(f"Date [YYYY-MM-DD, default {today}]: ").strip() or today
    meeting_date = _parse_date(date_raw)
    attendees = input("Attendees (comma-separated): ").strip() or None
    series_id = _pick_or_create_series(default_name=title)

    mid = db.add_meeting(
        title=title,
        date=meeting_date,
        attendees=attendees,
        series_id=series_id,
    )
    print(f"Created meeting #{mid}: {title} ({meeting_date}).")
    return db.get_meeting(mid)


def _resolve_meeting(meeting_id: int | None) -> dict:
    """Return a meeting row by id, or run an interactive picker."""
    if meeting_id is not None:
        m = db.get_meeting(meeting_id)
        if not m:
            sys.exit(f"No meeting #{meeting_id}.")
        return m

    rows = db.list_meetings(limit=10)
    if not rows:
        print("No meetings yet — let's create one.\n")
        return _create_meeting_interactive()

    print("Recent meetings:")
    series_names = {s["id"]: s["name"] for s in db.list_meeting_series()}
    for i, m in enumerate(rows, start=1):
        series = series_names.get(m["series_id"], "no series")
        print(f"  [{i}] [{m['date']}] {m['title']} (series: {series})")
    print("  [n] new meeting")
    choice = input(f"Pick [1-{len(rows)}, n] (default n): ").strip().lower() or "n"

    if choice in ("n", "new"):
        return _create_meeting_interactive()
    try:
        idx = int(choice)
        if 1 <= idx <= len(rows):
            return rows[idx - 1]
    except ValueError:
        pass
    sys.exit(f"Invalid choice: {choice}")


def cmd_meeting_create(_args):
    _create_meeting_interactive()


def cmd_meeting_prep(args):
    meeting = _resolve_meeting(getattr(args, "id", None))

    if meeting["prep_brief"]:
        choice = (
            input(
                "Prep already exists. (e)dit existing / (r)edo from scratch / (c)ancel [r]: "
            ).strip().lower()
            or "r"
        )
        if choice.startswith("c"):
            return
        if choice.startswith("e"):
            new_brief = _input_multiline(
                "Prep brief", initial=meeting["prep_brief"]
            )
            if not new_brief:
                print("Empty brief; not saved.")
                return
            db.update_meeting(meeting["id"], prep_brief=new_brief)
            print(f"Updated prep brief on meeting #{meeting['id']}.")
            return

    if meeting["prep_context"]:
        print(f"Existing context will be reused for meeting #{meeting['id']}.")
        context = meeting["prep_context"]
    else:
        context = _input_multiline("Purpose / agenda / context (paste freely)")

    user_msg = textwrap.dedent(
        f"""
        TASK: Pre-meeting prep brief.

        Meeting: {meeting['title']}
        Attendees: {meeting['attendees'] or '(not specified)'}
        Meeting date: {meeting['date']}
        Context:
        {context}

        Produce:
        1. Top 3 outcomes I should aim for, ranked.
        2. Talking points in priority order.
        3. Who to align with beforehand (if anyone) and why.
        4. Risks / things to avoid.
        5. Listen-fors — political signals I should be alert to in the meeting.
        6. Coda: what's the actual political move here, and what makes it land?

        If you need information you don't have (about a stakeholder, the work, the org dynamics), ASK rather than guess.
        """
    ).strip()
    _, brief = _iterate_with_followups(user_msg)

    print()
    answer = input("Save this prep brief? [Y/n]: ").strip().lower()
    if answer in ("n", "no"):
        print("Not saved.")
        return

    db.update_meeting(
        meeting["id"], prep_context=context or None, prep_brief=brief
    )
    print(f"Saved prep on meeting #{meeting['id']} ({meeting['title']}, {meeting['date']}).")


def cmd_meeting_debrief(args):
    meeting = _resolve_meeting(getattr(args, "id", None))

    if meeting["debrief_summary"]:
        choice = (
            input(
                "Debrief already exists. (e)dit existing / (r)edo from scratch / (c)ancel [r]: "
            ).strip().lower()
            or "r"
        )
        if choice.startswith("c"):
            return
        if choice.startswith("e"):
            new_summary = _input_multiline(
                "Debrief summary", initial=meeting["debrief_summary"]
            )
            if not new_summary:
                print("Empty summary; not saved.")
                return
            db.update_meeting(meeting["id"], debrief_summary=new_summary)
            print(f"Updated debrief on meeting #{meeting['id']}.")
            return

    notes = _input_multiline(
        "Notes from the meeting (paste freely — what was said, what you felt, signals you noticed)"
    )
    if not notes:
        sys.exit("Empty notes; nothing to debrief.")

    user_msg = textwrap.dedent(
        f"""
        TASK: Post-meeting debrief.

        Meeting: {meeting['title']}
        Attendees: {meeting['attendees'] or '(not specified)'}
        Date: {meeting['date']}

        Raw notes:
        {notes}

        Produce, in this order:
        1. Concrete follow-ups I should commit to (with rough timing).
        2. Political signals — what was actually being negotiated, who's aligned with whom, what's unsaid.
        3. Credit & thanks list — who deserves a public or private acknowledgment, and from whom.
        4. Items to escalate — anything my manager or skip should know, framed for them.
        5. What I missed — likely interpretations of the meeting I haven't considered.
        6. Coda: the single highest-leverage thing for me to do in the next 48 hours, and why.

        Push back if my read of the meeting is naive or self-serving — don't validate by default.
        """
    ).strip()
    _, summary = _iterate_with_followups(user_msg)

    print()
    answer = input("Save this debrief? [Y/n]: ").strip().lower()
    if answer in ("n", "no"):
        print("Not saved.")
        return

    db.update_meeting(
        meeting["id"], debrief_notes=notes, debrief_summary=summary
    )
    print(f"Saved debrief on meeting #{meeting['id']} ({meeting['title']}, {meeting['date']}).")


def cmd_meeting_edit(args):
    m = db.get_meeting(args.id)
    if not m:
        sys.exit(f"No meeting #{args.id}.")
    print(f"\nEditing meeting #{m['id']}: {m['title']} ({m['date']})\n")
    print("Fields:")
    print("  [1] title")
    print("  [2] attendees")
    print("  [3] date")
    print("  [4] series")
    print("  [5] prep context (raw)")
    print("  [6] prep brief (coach output)")
    print("  [7] debrief notes (raw)")
    print("  [8] debrief summary (coach output)")
    choice = input("Field to edit [1-8]: ").strip()

    if choice == "1":
        new = input(f"Title [{m['title']}]: ").strip()
        if new:
            db.update_meeting(args.id, title=new)
            print("Updated.")
    elif choice == "2":
        new = input(f"Attendees [{m['attendees'] or ''}]: ").strip()
        db.update_meeting(args.id, attendees=new or None)
        print("Updated.")
    elif choice == "3":
        new_raw = input(f"Date [{m['date']}]: ").strip()
        if not new_raw:
            return
        new = _parse_date(new_raw)
        db.update_meeting(args.id, date=new)
        print("Updated.")
    elif choice == "4":
        new_series_id = _pick_or_create_series(default_name=m["title"])
        db.update_meeting(args.id, series_id=new_series_id)
        print("Updated.")
    elif choice == "5":
        new = _input_multiline("Prep context", initial=m["prep_context"] or "")
        db.update_meeting(args.id, prep_context=new or None)
        print("Updated.")
    elif choice == "6":
        new = _input_multiline("Prep brief", initial=m["prep_brief"] or "")
        db.update_meeting(args.id, prep_brief=new or None)
        print("Updated.")
    elif choice == "7":
        new = _input_multiline("Debrief notes", initial=m["debrief_notes"] or "")
        db.update_meeting(args.id, debrief_notes=new or None)
        print("Updated.")
    elif choice == "8":
        new = _input_multiline(
            "Debrief summary", initial=m["debrief_summary"] or ""
        )
        db.update_meeting(args.id, debrief_summary=new or None)
        print("Updated.")
    else:
        sys.exit(f"Invalid choice: {choice}")


def cmd_meeting_list(_args):
    rows = db.list_meetings()
    if not rows:
        print("No meetings yet. Run: snuscoach meeting create")
        return
    series_names = {s["id"]: s["name"] for s in db.list_meeting_series()}
    for r in rows:
        attendees = f" — {r['attendees']}" if r["attendees"] else ""
        series = series_names.get(r["series_id"], "no series")
        markers = []
        if r["prep_brief"]:
            markers.append("prep")
        if r["debrief_summary"]:
            markers.append("debrief")
        marker_str = f" [{', '.join(markers)}]" if markers else ""
        print(
            f"  #{r['id']} [{r['date']}] {r['title']}{attendees} (series: {series}){marker_str}"
        )


def cmd_meeting_show(args):
    m = db.get_meeting(args.id)
    if not m:
        sys.exit(f"No meeting #{args.id}.")
    print(f"# {m['title']}")
    if m["attendees"]:
        print(f"Attendees: {m['attendees']}")
    print(f"Date: {m['date']}")
    if m["series_id"]:
        s = db.get_meeting_series(m["series_id"])
        if s:
            print(f"Series: {s['name']} (#{s['id']})")
    print(f"Created: {m['created_at']} · Updated: {m['updated_at']}")
    print()
    print("## Prep context")
    print(m["prep_context"] or "(none)")
    print()
    print("## Prep brief")
    print(m["prep_brief"] or "(none)")
    print()
    print("## Debrief notes")
    print(m["debrief_notes"] or "(none)")
    print()
    print("## Debrief summary")
    print(m["debrief_summary"] or "(none)")


# ---------------------------------------------------------------------------
# Chat
# ---------------------------------------------------------------------------


def cmd_chat(_args):
    print("Open coaching chat. Type 'exit' or Ctrl-D to quit.\n")
    messages: list[dict] = []
    while True:
        try:
            user_input = input("you> ").strip()
        except EOFError:
            print()
            break
        if not user_input:
            continue
        if user_input.lower() in ("exit", "quit"):
            break
        messages.append({"role": "user", "content": user_input})
        print("coach> ", end="", flush=True)
        reply = coach.conversation(messages)
        messages.append({"role": "assistant", "content": reply})
        print()


# ---------------------------------------------------------------------------
# Argparse
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(
        prog="snuscoach",
        description="Personal AI coach for navigating corporate office politics.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init", help="Initialize the local SQLite database").set_defaults(
        func=cmd_init
    )

    # stakeholder
    sk_parser = sub.add_parser("stakeholder", help="Manage stakeholder profiles")
    sk = sk_parser.add_subparsers(dest="sub", required=True)
    sk_add = sk.add_parser("add", help="Interview-style intake of a new stakeholder")
    sk_add.add_argument("name", nargs="?", help="Stakeholder name (prompted if omitted)")
    sk_add.set_defaults(func=cmd_stakeholder_add)
    sk.add_parser("list", help="List all stakeholders").set_defaults(
        func=cmd_stakeholder_list
    )
    sk_show = sk.add_parser("show", help="Show one stakeholder profile")
    sk_show.add_argument("name")
    sk_show.set_defaults(func=cmd_stakeholder_show)

    # win
    win_parser = sub.add_parser("win", help="Manage the brag ledger / wins")
    win = win_parser.add_subparsers(dest="sub", required=True)
    win.add_parser("add", help="Log a new win").set_defaults(func=cmd_win_add)
    win.add_parser("list", help="List wins").set_defaults(func=cmd_win_list)

    # post
    post_parser = sub.add_parser("post", help="Visibility posts: draft, save, list")
    post_sub = post_parser.add_subparsers(dest="sub", required=True)
    post_sub.add_parser(
        "draft", help="Draft a visibility post (optionally save it)"
    ).set_defaults(func=cmd_post_draft)
    post_sub.add_parser("list", help="List saved posts").set_defaults(func=cmd_post_list)

    # series
    series_parser = sub.add_parser("series", help="Meeting series (recurring threads)")
    series_sub = series_parser.add_subparsers(dest="sub", required=True)
    series_sub.add_parser("add", help="Create a new meeting series").set_defaults(
        func=cmd_series_add
    )
    series_sub.add_parser("list", help="List all series").set_defaults(
        func=cmd_series_list
    )
    series_show = series_sub.add_parser(
        "show", help="Show a series and its meetings"
    )
    series_show.add_argument("id", type=int)
    series_show.set_defaults(func=cmd_series_show)
    series_edit = series_sub.add_parser("edit", help="Edit a series (name/description)")
    series_edit.add_argument("id", type=int)
    series_edit.set_defaults(func=cmd_series_edit)

    # meeting
    meeting_parser = sub.add_parser(
        "meeting", help="Meetings: create, prep, debrief, edit, list, show"
    )
    meeting_sub = meeting_parser.add_subparsers(dest="sub", required=True)
    meeting_sub.add_parser(
        "create", help="Create a new meeting"
    ).set_defaults(func=cmd_meeting_create)

    m_prep = meeting_sub.add_parser(
        "prep", help="Pre-meeting prep brief (interactive picker if no id)"
    )
    m_prep.add_argument("id", type=int, nargs="?")
    m_prep.set_defaults(func=cmd_meeting_prep)

    m_debrief = meeting_sub.add_parser(
        "debrief", help="Post-meeting debrief (interactive picker if no id)"
    )
    m_debrief.add_argument("id", type=int, nargs="?")
    m_debrief.set_defaults(func=cmd_meeting_debrief)

    m_edit = meeting_sub.add_parser("edit", help="Edit a meeting field")
    m_edit.add_argument("id", type=int)
    m_edit.set_defaults(func=cmd_meeting_edit)

    meeting_sub.add_parser("list", help="List recent meetings").set_defaults(
        func=cmd_meeting_list
    )
    m_show = meeting_sub.add_parser("show", help="Show one meeting in full")
    m_show.add_argument("id", type=int)
    m_show.set_defaults(func=cmd_meeting_show)

    # Top-level aliases (muscle-memory ergonomics)
    prep_alias = sub.add_parser("prep", help="Alias: snuscoach meeting prep")
    prep_alias.add_argument("id", type=int, nargs="?")
    prep_alias.set_defaults(func=cmd_meeting_prep)

    debrief_alias = sub.add_parser("debrief", help="Alias: snuscoach meeting debrief")
    debrief_alias.add_argument("id", type=int, nargs="?")
    debrief_alias.set_defaults(func=cmd_meeting_debrief)

    sub.add_parser("chat", help="Open coaching chat").set_defaults(func=cmd_chat)

    args = parser.parse_args()
    logger.set_command(_command_path(args))
    args.func(args)


def _command_path(args) -> str:
    parts = [getattr(args, "cmd", None) or ""]
    sub = getattr(args, "sub", None)
    if sub:
        parts.append(sub)
    return " ".join(p for p in parts if p)


if __name__ == "__main__":
    main()
