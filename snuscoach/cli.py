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

from snuscoach import coach, db


def _iterate_with_followups(initial_user_msg: str) -> tuple[list[dict], str]:
    """Run an initial coach turn, then prompt for inline follow-ups.

    Streams the first response, then loops on `you> ` prompts. Empty input
    or EOF ends the conversation. Returns (full message history, last
    assistant text). Use the second value when you need the iterated final
    artifact (debrief summary, finalized post draft, etc.).
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
    """Open $EDITOR on a temp file for editable multiline input.

    If `initial` is provided, the file is pre-seeded with it (handy for editing
    a draft). Lines starting with '#' are stripped as instruction comments.
    Returns the trimmed body, or empty string if the user saves nothing.
    """
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
    try:
        posted_at = datetime.strptime(posted_at_raw, "%Y-%m-%d").date().isoformat()
    except ValueError:
        sys.exit(f"Invalid date '{posted_at_raw}'. Expected YYYY-MM-DD.")

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


def cmd_prep(_args):
    print("Pre-meeting prep brief.\n")
    title = input("Meeting title (e.g. '1:1 with Sarah', 'staff'): ").strip()
    if not title:
        sys.exit("Title is required.")
    attendees = input("Attendees (comma-separated names): ").strip()
    purpose = _input_multiline("Purpose / agenda / context (paste freely)")
    user_msg = textwrap.dedent(
        f"""
        TASK: Pre-meeting prep brief.

        Meeting: {title}
        Attendees: {attendees}
        Context:
        {purpose}

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
    _iterate_with_followups(user_msg)


def cmd_debrief(_args):
    print("Post-meeting debrief.\n")
    title = input("Meeting title (e.g. '1:1 with Sarah', 'staff'): ").strip()
    if not title:
        sys.exit("Title is required.")
    attendees = input("Attendees (comma-separated): ").strip() or None

    today = date.today().isoformat()
    happened_at_raw = (
        input(f"When did it happen? [YYYY-MM-DD, default {today}]: ").strip() or today
    )
    try:
        happened_at = (
            datetime.strptime(happened_at_raw, "%Y-%m-%d").date().isoformat()
        )
    except ValueError:
        sys.exit(f"Invalid date '{happened_at_raw}'. Expected YYYY-MM-DD.")

    notes = _input_multiline(
        "Notes from the meeting (paste freely — what was said, what you felt, signals you noticed)"
    )
    if not notes:
        sys.exit("Empty notes; nothing to debrief.")

    user_msg = textwrap.dedent(
        f"""
        TASK: Post-meeting debrief.

        Meeting: {title}
        Attendees: {attendees or '(not specified)'}
        Date: {happened_at}

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
    answer = (
        input("Save this debrief to your meeting log? [Y/n]: ").strip().lower()
    )
    if answer in ("n", "no"):
        print("Not saved.")
        return

    mid = db.add_meeting(title, attendees, notes, summary, happened_at)
    print(f"Saved meeting #{mid} ({title}, {happened_at}).")


def cmd_meeting_list(_args):
    rows = db.list_meetings()
    if not rows:
        print("No meetings logged yet. Run: snuscoach debrief")
        return
    for r in rows:
        attendees = f" — {r['attendees']}" if r["attendees"] else ""
        print(f"  #{r['id']} [{r['happened_at']}] {r['title']}{attendees}")


def cmd_meeting_show(args):
    m = db.get_meeting(args.id)
    if not m:
        sys.exit(f"No meeting #{args.id}.")
    print(f"# {m['title']}")
    if m["attendees"]:
        print(f"Attendees: {m['attendees']}")
    print(f"When: {m['happened_at']}")
    print(f"Logged: {m['created_at']}")
    print()
    print("## Raw notes")
    print(m["notes"] or "(none)")
    print()
    print("## Coach debrief")
    print(m["coach_summary"] or "(none)")


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


def main():
    parser = argparse.ArgumentParser(
        prog="snuscoach",
        description="Personal AI coach for navigating corporate office politics.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init", help="Initialize the local SQLite database").set_defaults(
        func=cmd_init
    )

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

    win_parser = sub.add_parser("win", help="Manage the brag ledger / wins")
    win = win_parser.add_subparsers(dest="sub", required=True)
    win.add_parser("add", help="Log a new win").set_defaults(func=cmd_win_add)
    win.add_parser("list", help="List wins").set_defaults(func=cmd_win_list)

    post_parser = sub.add_parser("post", help="Visibility posts: draft, save, list")
    post_sub = post_parser.add_subparsers(dest="sub", required=True)
    post_sub.add_parser("draft", help="Draft a visibility post (optionally save it)").set_defaults(
        func=cmd_post_draft
    )
    post_sub.add_parser("list", help="List saved posts").set_defaults(func=cmd_post_list)

    sub.add_parser("prep", help="Pre-meeting prep brief").set_defaults(func=cmd_prep)
    sub.add_parser(
        "debrief", help="Post-meeting debrief (saves to meeting log)"
    ).set_defaults(func=cmd_debrief)

    meeting_parser = sub.add_parser("meeting", help="Browse the meeting log")
    meeting_sub = meeting_parser.add_subparsers(dest="sub", required=True)
    meeting_sub.add_parser("list", help="List logged meetings").set_defaults(
        func=cmd_meeting_list
    )
    meeting_show = meeting_sub.add_parser("show", help="Show one meeting in full")
    meeting_show.add_argument("id", type=int)
    meeting_show.set_defaults(func=cmd_meeting_show)

    sub.add_parser("chat", help="Open coaching chat").set_defaults(func=cmd_chat)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
