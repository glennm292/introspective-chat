"""The conversation outline: one short entry per message, for the navigation rail.

The rail needs an entry for every message in the WHOLE conversation, but the
transcript only ever holds a window of it in memory (see the scroll engine's fill
planner). A rail built from the loaded rows alone would gain and lose entries as
the user scrolls, which is exactly the opposite of a navigation aid. So the outline
is computed here, over every parsed event, and served in one small response.

It stays small because it carries only openings: events are already payload-free
(``harnesses/events``), and an entry keeps at most :data:`MAX_OPENING_LENGTH`
characters of text. A thousand-message conversation is tens of kilobytes.

What counts as an entry -- the shape the user asked for, "my turn, your turn":

- Each visible user message is one entry.
- Each RUN of assistant messages between user messages is one entry, not one per
  message. An agent reply is many assistant messages (measured on a real session:
  160 tool-only, 32 text-only, none combined), and an entry per message would bury
  the user's own messages in a list several times longer.
- An entry's text is the OPENING of that message or run -- never a summary. There
  is no model call here and nothing is generated: what the rail shows is text the
  conversation already contains.
"""

import re
from collections.abc import Sequence
from typing import Any
from typing import Final

from pydantic import Field

from imbue.chat.harnesses.events import DisplayKind
from imbue.imbue_common.frozen_model import FrozenModel
from imbue.imbue_common.pure import pure

# Enough to fill the rail's two-line clamp at any reasonable rail width, with a
# little slack for the hover title. Not a display limit -- the clamp is CSS.
MAX_OPENING_LENGTH: Final[int] = 240

# Messages that are not part of the conversation the user had: framework injections,
# collapsed system chips, a skill's expanded body, a permission verdict. They render
# as chips or not at all, and none of them is a turn to navigate to.
_SKIPPED_DISPLAY_KINDS: Final[frozenset[str]] = frozenset(
    {
        DisplayKind.HIDDEN.value,
        DisplayKind.CHIP.value,
        DisplayKind.SKILL_EXPANSION.value,
        DisplayKind.PERMISSION_RESOLUTION.value,
    }
)

_USER_ROLE: Final[str] = "user"
_AGENT_ROLE: Final[str] = "agent"


class OutlineEntry(FrozenModel):
    """One navigable message (or one run of agent messages) in the conversation."""

    event_id: str = Field(description="The event the rail scrolls to when this entry is clicked")
    index: int = Field(description="The event's global position, so an unloaded entry can be jumped to")
    role: str = Field(description="'user' or 'agent' -- which side the entry leans towards")
    text: str = Field(description="The opening of the message, clipped; never a generated summary")


@pure
def opening_of(text: str) -> str:
    """The first stretch of a message, collapsed to one line and clipped.

    Collapsed because the rail's two-line clamp should be filled with the message's
    first WORDS, not with whatever blank lines and markdown scaffolding happened to
    come first -- a reply that opens with a heading would otherwise spend one of its
    two lines on it.
    """
    collapsed = re.sub(r"\s+", " ", _strip_markdown_scaffolding(text)).strip()
    if len(collapsed) <= MAX_OPENING_LENGTH:
        return collapsed
    return collapsed[: MAX_OPENING_LENGTH - 1].rstrip() + "…"


@pure
def _strip_markdown_scaffolding(text: str) -> str:
    """Drop leading markers that carry no meaning once the text is one line."""
    without_headings = re.sub(r"^\s*#{1,6}\s*", "", text)
    without_bullets = re.sub(r"^\s*[-*+]\s+", "", without_headings)
    return without_bullets


@pure
def _visible_user_text(event: dict[str, Any]) -> str | None:
    """The user's own words, or None when this message is not a conversation turn."""
    if event.get("display") in _SKIPPED_DISPLAY_KINDS:
        return None
    content = event.get("content")
    if not isinstance(content, str) or not content.strip():
        return None
    return content


@pure
def _assistant_text(event: dict[str, Any]) -> str | None:
    """The assistant's prose, or None for a message that only made tool calls."""
    text = event.get("text")
    if not isinstance(text, str) or not text.strip():
        return None
    return text


@pure
def _agent_entry(event: dict[str, Any], index: int) -> OutlineEntry:
    """The entry standing for one run of agent messages."""
    return OutlineEntry(
        event_id=str(event.get("event_id", "")),
        index=index,
        role=_AGENT_ROLE,
        text=opening_of(_assistant_text(event) or ""),
    )


@pure
def _user_entry(event: dict[str, Any], index: int, text: str) -> OutlineEntry:
    return OutlineEntry(
        event_id=str(event.get("event_id", "")),
        index=index,
        role=_USER_ROLE,
        text=opening_of(text),
    )


def build_outline(events: Sequence[dict[str, Any]]) -> list[OutlineEntry]:
    """One entry per user message and per run of agent messages, in transcript order.

    ``events`` is the whole conversation in order; an entry's ``index`` is its
    position within it, which is what lets the rail jump to a message the
    transcript has not loaded.
    """
    entries: list[OutlineEntry] = []
    # The agent's reply spans every assistant message up to the next user message,
    # and is represented by the first one that actually says something. A run that
    # only made tool calls and never spoke yields no entry -- there is nothing to
    # label it with, and a blank rail row navigates to nothing.
    agent_run_event: dict[str, Any] | None = None
    agent_run_index = 0

    for index, event in enumerate(events):
        event_type = event.get("type")
        if event_type == "assistant_message":
            if agent_run_event is None and _assistant_text(event) is not None:
                agent_run_event = event
                agent_run_index = index
            continue
        if event_type != "user_message":
            # tool_result and special events are neither a turn nor a boundary.
            continue
        user_text = _visible_user_text(event)
        if user_text is None:
            # A chip or injection does not end the agent's reply: work resumed
            # after a stop-hook nudge is still the same reply.
            continue
        if agent_run_event is not None:
            entries.append(_agent_entry(agent_run_event, agent_run_index))
            agent_run_event = None
        entries.append(_user_entry(event, index, user_text))

    if agent_run_event is not None:
        entries.append(_agent_entry(agent_run_event, agent_run_index))
    return entries
