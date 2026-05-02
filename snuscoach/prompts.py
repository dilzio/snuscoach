SYSTEM = """You are Snuscoach, a personal AI coach for navigating corporate office politics.
You coach Matt — a senior software engineer who is technically strong but politically under-developed and aware of it. Matt knows politics matters and wants to get better at it; he is not naturally inclined to play it.

Your purpose is to BUILD MATT'S SKILL, not just to produce outputs. Every artifact you draft and every situation you analyze should make him incrementally better at this. Explain the *why* behind your suggestions; reference established frameworks when they apply (Cialdini's six principles of influence, Crucial Conversations, Radical Candor, the "managing up" canon).

CORE BEHAVIORS

1. Challenge, don't validate. If Matt's read of a situation is naive, victim-mode, or strategically weak, say so directly. He explicitly does NOT want a sycophant. Push back when you disagree — that is the value you provide.
2. Push toward action. A session that doesn't end with a concrete next step (a post to publish, a person to talk to, a question to ask, a behavior to try) is worse than nothing. Always close with a "next move."
3. Stay grounded. You only know what's been shared with you. When you need information about the org, the work, or a stakeholder you don't have on file, ASK — don't fabricate.
4. Authentic influence, not manipulation. Coaching biases toward credibility, alignment, reciprocity, and clear communication. If Matt asks for a tactic that's zero-sum or damages a colleague, name the tradeoff and offer a higher-integrity alternative.

OUTPUT STYLE

- Senior engineer audience. Skip 101 explanations.
- Be terse. Long answers only when the analysis genuinely requires depth.
- When drafting artifacts (posts, emails, prep notes): produce a clean draft ready to copy-paste, then a short coda — "why I wrote it this way" — so Matt internalizes the moves rather than just shipping the output.
- Use Matt's voice cues from the wins ledger and notes when drafting on his behalf. He is direct, low-fluff, and avoids corporate-speak. Don't make him sound like an LLM.

CONTEXT YOU HAVE

The sections below give you Matt's current political landscape. They may be sparse in early sessions — when something matters and isn't there, ASK rather than guess.
"""


def context_block(
    stakeholders: list,
    wins: list,
    posts: list,
    meetings: list,
    meeting_series: list,
) -> str:
    parts = ["# STAKEHOLDERS"]
    if stakeholders:
        for s in stakeholders:
            rel = s["relationship"] or "unknown relationship"
            parts.append(f"\n## {s['name']} ({rel})")
            for label, key in [
                ("Role", "role"),
                ("Communication style", "communication_style"),
                ("What they reward", "what_they_reward"),
                ("Notes", "notes"),
            ]:
                if s[key]:
                    parts.append(f"{label}: {s[key]}")
    else:
        parts.append("(none recorded yet)")

    parts.append("\n# WINS LEDGER (most recent first)")
    if wins:
        for w in wins[:30]:
            line = f"- [{w['created_at'][:10]}] {w['title']}"
            if w["description"]:
                line += f" — {w['description']}"
            parts.append(line)
    else:
        parts.append("(none recorded yet)")

    parts.append(
        "\n# POST HISTORY (most recent first — use these for voice and to avoid repeating yourself)"
    )
    if posts:
        for p in posts[:15]:
            audience = f" / {p['audience']}" if p["audience"] else ""
            parts.append(
                f"\n## {p['posted_at']} — {p['channel']}{audience}"
            )
            parts.append(p["content"])
    else:
        parts.append("(none recorded yet)")

    parts.append(_render_meetings_block(meetings, meeting_series))

    return "\n".join(parts)


def _render_meetings_block(meetings: list, meeting_series: list) -> str:
    """Render meetings grouped by series, with one-offs at the end.

    Each meeting shows its prep brief and debrief summary together so the
    coach sees the full lifecycle and the thread continuity within a series.
    """
    parts = [
        "\n# MEETINGS (grouped by series — use thread continuity to spot patterns)"
    ]
    if not meetings and not meeting_series:
        parts.append("(none recorded yet)")
        return "\n".join(parts)

    series_by_id = {s["id"]: s for s in meeting_series}
    by_series: dict = {}
    one_offs: list = []
    for m in meetings:
        sid = m["series_id"]
        if sid is None:
            one_offs.append(m)
        else:
            by_series.setdefault(sid, []).append(m)

    # Order series sections by most recent meeting in each series
    def _series_recency(sid: int) -> str:
        rows = by_series.get(sid, [])
        return rows[0]["date"] if rows else ""

    for sid in sorted(by_series.keys(), key=_series_recency, reverse=True):
        series = series_by_id.get(sid)
        if not series:
            continue
        desc = f" — {series['description']}" if series["description"] else ""
        parts.append(f"\n## SERIES: {series['name']}{desc}")
        for m in by_series[sid][:15]:
            parts.append(_render_meeting_entry(m))

    if one_offs:
        parts.append("\n## ONE-OFF MEETINGS")
        for m in one_offs[:15]:
            parts.append(_render_meeting_entry(m))

    return "\n".join(parts)


def _render_meeting_entry(m) -> str:
    attendees = f" — {m['attendees']}" if m["attendees"] else ""
    out = [f"\n### {m['date']} — {m['title']}{attendees}"]
    if m["prep_brief"]:
        out.append(f"Prep: {m['prep_brief']}")
    elif m["prep_context"]:
        out.append(f"Prep (raw context only): {m['prep_context']}")
    if m["debrief_summary"]:
        out.append(f"Debrief: {m['debrief_summary']}")
    elif m["debrief_notes"]:
        out.append(f"Debrief (raw notes only): {m['debrief_notes']}")
    if len(out) == 1:
        out.append("(no prep or debrief yet)")
    return "\n".join(out)
