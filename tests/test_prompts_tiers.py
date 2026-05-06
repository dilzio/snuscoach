"""Tests for tier-grouped stakeholder rendering in prompts.context_block.

No DB needed — calls context_block() directly with in-memory dicts.
"""
from snuscoach import prompts


def _s(name, rel, **kwargs):
    return {
        "name": name,
        "relationship": rel,
        "role": kwargs.get("role"),
        "communication_style": None,
        "what_they_reward": None,
        "notes": None,
    }


def _ctx(stakeholders):
    return prompts.context_block(stakeholders, [], [], [], [], [])


def test_tier_sections_present():
    out = _ctx([_s("Alice", "manager"), _s("Bob", "peer")])
    assert "## Manager" in out
    assert "## Peer" in out


def test_tier_order_manager_before_peer():
    out = _ctx([_s("Bob", "peer"), _s("Alice", "manager")])
    assert out.index("## Manager") < out.index("## Peer")


def test_skip_before_peer_before_influencer():
    out = _ctx([_s("C", "influencer"), _s("B", "peer"), _s("A", "skip")])
    assert out.index("## Skip") < out.index("## Peer") < out.index("## Influencer")


def test_relationship_not_in_per_stakeholder_header():
    out = _ctx([_s("Alice", "manager")])
    assert "Alice (manager)" not in out
    assert "### Alice" in out


def test_none_relationship_goes_to_unclassified():
    out = _ctx([_s("Alice", None)])
    assert "## Unclassified" in out
    assert "Alice" in out


def test_noncanonical_relationship_goes_to_unclassified():
    out = _ctx([_s("Alice", "director")])
    assert "## Unclassified" in out
    assert "Alice (director)" in out


def test_canonical_other_tier_gets_own_section():
    out = _ctx([_s("Alice", "other")])
    assert "## Other" in out
    assert "## Unclassified" not in out


def test_empty_stakeholders_list():
    out = _ctx([])
    assert "(none recorded yet)" in out


def test_stakeholder_fields_rendered():
    s = _s("Alice", "manager", role="VP Eng")
    s["communication_style"] = "terse"
    s["what_they_reward"] = "metrics"
    s["notes"] = "key ally"
    out = _ctx([s])
    assert "Role: VP Eng" in out
    assert "Communication style: terse" in out
    assert "What they reward: metrics" in out
    assert "Notes: key ally" in out


def test_multiple_stakeholders_same_tier():
    out = _ctx([_s("Alice", "peer"), _s("Bob", "peer")])
    assert out.count("## Peer") == 1
    assert "### Alice" in out
    assert "### Bob" in out
