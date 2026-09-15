"""Tests for the conversation outline the navigation rail is built from."""

from typing import Any

from imbue.chat.outline import MAX_OPENING_LENGTH
from imbue.chat.outline import build_outline
from imbue.chat.outline import opening_of


def _user(event_id: str, content: str, **extra: Any) -> dict[str, Any]:
    return {"type": "user_message", "event_id": event_id, "role": "user", "content": content, **extra}


def _says(event_id: str, text: str) -> dict[str, Any]:
    return {"type": "assistant_message", "event_id": event_id, "text": text, "tool_calls": []}


def _works(event_id: str) -> dict[str, Any]:
    return {
        "type": "assistant_message",
        "event_id": event_id,
        "text": "",
        "tool_calls": [{"tool_call_id": f"{event_id}-c", "tool_name": "Bash", "input_chars": 4}],
    }


def _result(event_id: str) -> dict[str, Any]:
    return {"type": "tool_result", "event_id": event_id, "tool_call_id": "c", "output_chars": 3, "is_error": False}


def test_a_conversation_alternates_user_and_agent_entries() -> None:
    outline = build_outline(
        [
            _user("u1", "First question"),
            _says("a1", "First answer"),
            _user("u2", "Second question"),
            _says("a2", "Second answer"),
        ]
    )
    assert [(e.role, e.text) for e in outline] == [
        ("user", "First question"),
        ("agent", "First answer"),
        ("user", "Second question"),
        ("agent", "Second answer"),
    ]


def test_a_whole_agent_reply_is_one_entry_not_one_per_message() -> None:
    """An agent reply is many messages; an entry each would bury the user's own."""
    outline = build_outline(
        [
            _user("u1", "Do the thing"),
            _says("a1", "On it."),
            _works("a2"),
            _result("r2"),
            _says("a3", "Halfway through."),
            _works("a4"),
            _says("a5", "Done."),
            _user("u2", "Thanks"),
        ]
    )
    assert [(e.role, e.text) for e in outline] == [
        ("user", "Do the thing"),
        ("agent", "On it."),
        ("user", "Thanks"),
    ]


def test_the_agent_entry_points_at_the_first_words_of_the_reply() -> None:
    """Clicking the entry should land on the sentence the rail is showing."""
    outline = build_outline([_user("u1", "Go"), _works("a1"), _result("r1"), _says("a2", "Here is what I found.")])
    agent_entry = outline[1]
    assert agent_entry.event_id == "a2"
    assert agent_entry.index == 3
    assert agent_entry.text == "Here is what I found."


def test_a_reply_that_only_ran_tools_gets_no_entry() -> None:
    """A blank rail row would label nothing and navigate nowhere."""
    outline = build_outline([_user("u1", "Go"), _works("a1"), _result("r1")])
    assert [e.role for e in outline] == ["user"]


def test_indexes_are_global_positions_so_an_unloaded_entry_can_be_jumped_to() -> None:
    events = [_user("u1", "One"), _says("a1", "Two"), _result("r1"), _user("u2", "Three")]
    assert [e.index for e in build_outline(events)] == [0, 1, 3]


def test_hidden_and_chip_messages_are_not_conversation_turns() -> None:
    """A framework injection or a stop-hook chip is not something to navigate to."""
    outline = build_outline(
        [
            _user("h1", "/welcome", display="hidden"),
            _user("u1", "Real question"),
            _says("a1", "Real answer"),
            _user("c1", "Stop hook feedback", display="chip"),
            _user("s1", "skill body", display="skill_expansion"),
        ]
    )
    assert [(e.role, e.text) for e in outline] == [("user", "Real question"), ("agent", "Real answer")]


def test_a_chip_does_not_split_one_reply_into_two() -> None:
    """Work resumed after a stop-hook nudge is still the same reply."""
    outline = build_outline(
        [
            _user("u1", "Go"),
            _says("a1", "Starting."),
            _user("c1", "Stop hook feedback", display="chip"),
            _says("a2", "Continuing."),
        ]
    )
    assert [(e.role, e.text) for e in outline] == [("user", "Go"), ("agent", "Starting.")]


def test_an_empty_conversation_has_an_empty_outline() -> None:
    assert build_outline([]) == []


def test_a_short_message_is_shown_whole() -> None:
    assert opening_of("C1+C2 sounds good") == "C1+C2 sounds good"


def test_a_long_message_is_clipped_with_an_ellipsis() -> None:
    clipped = opening_of("word " * 200)
    assert len(clipped) <= MAX_OPENING_LENGTH
    assert clipped.endswith("…")


def test_the_opening_is_collapsed_to_one_line() -> None:
    """The rail's two lines should hold the first WORDS, not the blank lines."""
    assert opening_of("First line.\n\n\nSecond line.") == "First line. Second line."


def test_a_leading_heading_marker_is_dropped() -> None:
    """A reply opening with a heading would otherwise spend a line on the hashes."""
    assert opening_of("## What changed\n\nThe rename came out of the merge.") == (
        "What changed The rename came out of the merge."
    )


def test_a_leading_bullet_marker_is_dropped() -> None:
    assert opening_of("- First point here") == "First point here"


def test_a_message_that_is_only_whitespace_is_not_an_entry() -> None:
    outline = build_outline([_user("u1", "   \n  "), _says("a1", "  ")])
    assert outline == []
