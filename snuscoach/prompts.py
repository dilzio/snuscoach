VALID_TIERS = ("manager", "skip", "peer", "cross-functional", "influencer", "direct-report", "other")

_SYSTEM_TEMPLATE = """\
You are Snuscoach, a personal AI coach for navigating corporate office politics.
You coach {name} — {role_line}. {name} knows politics matters and wants to get better at it; they are not naturally inclined to play it.
{profile_block}
Your purpose is to BUILD {name}'S SKILL, not just to produce outputs. Every artifact you draft and every situation you analyze should make them incrementally better at this. Explain the *why* behind your suggestions; reference established frameworks when they apply (Cialdini's six principles of influence, Crucial Conversations, Radical Candor, the "managing up" canon).

CORE BEHAVIORS

1. Challenge, don't validate. If {name}'s read of a situation is naive, victim-mode, or strategically weak, say so directly. They explicitly do NOT want a sycophant. Push back when you disagree — that is the value you provide.
2. Push toward action. A session that doesn't end with a concrete next step (a post to publish, a person to talk to, a question to ask, a behavior to try) is worse than nothing. Always close with a "next move."
3. Stay grounded. You only know what's been shared with you. When you need information about the org, the work, or a stakeholder you don't have on file, ASK — don't fabricate.
4. Authentic influence, not manipulation. Coaching biases toward credibility, alignment, reciprocity, and clear communication. If {name} asks for a tactic that's zero-sum or damages a colleague, name the tradeoff and offer a higher-integrity alternative.

OUTPUT STYLE

- Senior engineer audience. Skip 101 explanations.
- Be terse. Long answers only when the analysis genuinely requires depth.
- When drafting artifacts (posts, emails, prep notes): produce a clean draft ready to copy-paste, then a short coda — "why I wrote it this way" — so {name} internalizes the moves rather than just shipping the output.
- When drafting on {name}'s behalf, study the VOICE PROFILE samples below and match their register, sentence length, and vocabulary. If no samples are on file, use their post history as a proxy. Never write corporate-speak or LLM-sounding prose.

CONTEXT YOU HAVE

The sections below give you {name}'s current political landscape. They may be sparse in early sessions — when something matters and isn't there, ASK rather than guess.
"""


def system_prompt(profile: dict) -> str:
    name = (profile.get("name") or "").strip() or "the coached user"
    role_line = profile.get("role") or "a software professional"

    profile_lines = []
    if profile.get("org_context"):
        profile_lines.append(f"Org context: {profile['org_context']}")
    if profile.get("political_strengths"):
        profile_lines.append(f"Political strengths: {profile['political_strengths']}")
    if profile.get("political_weaknesses"):
        profile_lines.append(f"Political weaknesses: {profile['political_weaknesses']}")
    if profile.get("coaching_goals"):
        profile_lines.append(f"Coaching goals: {profile['coaching_goals']}")
    if profile.get("communication_style"):
        profile_lines.append(f"Communication style: {profile['communication_style']}")

    if profile_lines:
        profile_block = (
            "\n[PROFILE\nName: " + name + "\n" + "\n".join(profile_lines) + "\n]\n"
        )
    else:
        profile_block = "\n"

    return _SYSTEM_TEMPLATE.format(
        name=name, role_line=role_line, profile_block=profile_block
    )


def context_block(
    stakeholders: list,
    wins: list,
    posts: list,
    meetings: list,
    meeting_series: list,
    voice_samples: list | None = None,
) -> str:
    parts = [_render_stakeholders_block(stakeholders)]

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

    parts.append(_render_voice_block(voice_samples or []))

    parts.append(_render_meetings_block(meetings, meeting_series))

    return "\n".join(parts)


def _render_voice_block(voice_samples: list) -> str:
    parts = [
        "\n# VOICE PROFILE (real writing samples — match this register when drafting)"
    ]
    if not voice_samples:
        parts.append("(none recorded yet — add samples with: snuscoach voice add)")
        return "\n".join(parts)
    for s in voice_samples[:10]:
        header = f"\n## Sample #{s['id']}"
        if s["description"]:
            header += f" — {s['description']}"
        header += f" [{s['created_at'][:10]}]"
        parts.append(header)
        parts.append(s["content"])
    return "\n".join(parts)


def _render_meetings_block(meetings: list, meeting_series: list) -> str:
    """Render meetings grouped by series, with one-offs at the end."""
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


def _render_stakeholders_block(stakeholders: list) -> str:
    parts = ["# STAKEHOLDERS"]
    if not stakeholders:
        parts.append("(none recorded yet)")
        return "\n".join(parts)

    by_tier: dict[str, list] = {t: [] for t in VALID_TIERS}
    ungrouped: list = []
    for s in stakeholders:
        rel = (s["relationship"] or "").strip().lower()
        if rel in by_tier:
            by_tier[rel].append(s)
        else:
            ungrouped.append(s)

    for tier in VALID_TIERS:
        members = by_tier[tier]
        if not members:
            continue
        parts.append(f"\n## {tier.title()}")
        for s in members:
            parts.append(_render_one_stakeholder(s, show_rel=False))

    if ungrouped:
        parts.append("\n## Unclassified")
        for s in ungrouped:
            parts.append(_render_one_stakeholder(s, show_rel=True))

    return "\n".join(parts)


def _render_one_stakeholder(s: dict, show_rel: bool) -> str:
    header = f"\n### {s['name']}"
    if show_rel and s["relationship"]:
        header += f" ({s['relationship']})"
    lines = [header]
    for label, key in [
        ("Role", "role"),
        ("Communication style", "communication_style"),
        ("What they reward", "what_they_reward"),
        ("Notes", "notes"),
    ]:
        if s[key]:
            lines.append(f"{label}: {s[key]}")
    return "\n".join(lines)


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
