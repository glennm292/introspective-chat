"""The agent overview: how many calls the conversation made, and how long they took.

Computed over EVERY event, like the outline (:mod:`imbue.chat.outline`), so the
figures describe the whole conversation rather than whatever slice the transcript
currently holds. Events are payload-free, so one pass over all of them is cheap.

Both durations are gaps between recorded timestamps, which is the only timing the
transcript actually contains:

- A **tool call** lasts from the assistant message that issued it to its result.
- An **LLM call** lasts from the previous event to the assistant message it
  produced -- the model was working during exactly that gap.

That makes them wall-clock, not billed time: a gap also covers anything else that
happened in it (a queued request, a hook, the user's own delay before a tool was
allowed to run). They are honest as "how long this conversation spent here", which
is the question the overview answers, and should not be read as vendor metering.

Tokens belong to model calls alone. A tool call consumes none: its output becomes
input to whichever model call reads it next, and is counted there. So the token
figures are totals over the conversation's model calls, and tool kinds report none
rather than a zero that would read as "this tool is free".
"""

import re
from collections.abc import Sequence
from datetime import datetime
from typing import Any
from typing import Final

from pydantic import Field

from imbue.imbue_common.frozen_model import FrozenModel
from imbue.imbue_common.pure import pure

# A gap longer than this did not measure a call: the conversation was idle, waiting
# on the person rather than on the model or a tool. Counting those would drown the
# real figures in wall-clock time nobody spent working.
MAX_ATTRIBUTABLE_GAP_SECONDS: Final[float] = 600.0

_TRAILING_Z = re.compile(r"Z$")


class ToolUsage(FrozenModel):
    """One kind of tool call, aggregated across the conversation."""

    tool_name: str = Field(description="The tool as the harness named it, e.g. 'Bash'")
    call_count: int = Field(description="How many calls of this kind were made")
    total_seconds: float = Field(description="Wall-clock time from each call to its result, summed")
    timed_call_count: int = Field(description="How many of those calls had both timestamps to measure")


class AgentOverview(FrozenModel):
    """Counts and durations for a conversation's model and tool activity."""

    llm_call_count: int = Field(description="Assistant messages, one per model response")
    llm_total_seconds: float = Field(description="Time the model spent producing them")
    llm_timed_call_count: int = Field(description="How many model calls could be timed")
    llm_output_tokens: int = Field(description="Tokens the model generated")
    llm_input_tokens: int = Field(description="Fresh (uncached) tokens the model read")
    llm_cache_read_tokens: int = Field(description="Tokens served from the prompt cache")
    llm_cache_write_tokens: int = Field(description="Tokens written into the prompt cache")
    tools: list[ToolUsage] = Field(description="Per tool kind, longest total first")
    tool_call_count: int = Field(description="Every tool call, all kinds")
    tool_total_seconds: float = Field(description="Every tool call's time, all kinds")
    skipped_gap_count: int = Field(description="Gaps discarded as idle rather than counted as work")


@pure
def parse_timestamp(value: Any) -> datetime | None:
    """A transcript timestamp as a datetime, or None when it is absent or malformed.

    Timestamps come from the harness's own file, so a missing or odd one is a
    normal thing to meet rather than an error: the event still counts, it just
    cannot be timed.
    """
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(_TRAILING_Z.sub("+00:00", value))
    except ValueError:
        return None


@pure
def _gap_seconds(earlier: datetime | None, later: datetime | None) -> float | None:
    """The seconds between two timestamps, or None when that is not a measurement.

    Rejects a negative gap (clock skew, or events recorded out of order) and an
    implausibly long one (see MAX_ATTRIBUTABLE_GAP_SECONDS).
    """
    if earlier is None or later is None:
        return None
    seconds = (later - earlier).total_seconds()
    if seconds < 0 or seconds > MAX_ATTRIBUTABLE_GAP_SECONDS:
        return None
    return seconds


def build_overview(events: Sequence[dict[str, Any]]) -> AgentOverview:
    """Aggregate the conversation's model and tool activity."""
    # Where each tool call was issued, so its result can be matched back to it.
    issued_at_by_call_id: dict[str, datetime | None] = {}
    tool_name_by_call_id: dict[str, str] = {}

    call_count_by_tool: dict[str, int] = {}
    seconds_by_tool: dict[str, float] = {}
    timed_count_by_tool: dict[str, int] = {}

    llm_call_count = 0
    llm_total_seconds = 0.0
    token_totals = {"output_tokens": 0, "input_tokens": 0, "cache_read_tokens": 0, "cache_write_tokens": 0}
    llm_timed_call_count = 0
    skipped_gap_count = 0
    previous_at: datetime | None = None

    for event in events:
        event_type = event.get("type")
        at = parse_timestamp(event.get("timestamp"))

        if event_type == "assistant_message":
            # One assistant message is one model response, so the gap since the
            # previous event is what the model spent producing it.
            llm_call_count += 1
            gap = _gap_seconds(previous_at, at)
            if gap is None:
                skipped_gap_count += 1
            else:
                llm_total_seconds += gap
                llm_timed_call_count += 1
            usage = event.get("usage")
            if isinstance(usage, dict):
                for field in token_totals:
                    value = usage.get(field)
                    # A harness that reports no usage, or a partial one, simply
                    # contributes nothing -- never a guess and never a crash.
                    if isinstance(value, int) and value > 0:
                        token_totals[field] += value
            for call in event.get("tool_calls") or []:
                call_id = call.get("tool_call_id")
                if not isinstance(call_id, str):
                    continue
                tool_name = str(call.get("tool_name") or "tool")
                issued_at_by_call_id[call_id] = at
                tool_name_by_call_id[call_id] = tool_name
                call_count_by_tool[tool_name] = call_count_by_tool.get(tool_name, 0) + 1

        elif event_type == "tool_result":
            call_id = event.get("tool_call_id")
            if isinstance(call_id, str) and call_id in tool_name_by_call_id:
                tool_name = tool_name_by_call_id[call_id]
                gap = _gap_seconds(issued_at_by_call_id.get(call_id), at)
                if gap is None:
                    skipped_gap_count += 1
                else:
                    seconds_by_tool[tool_name] = seconds_by_tool.get(tool_name, 0.0) + gap
                    timed_count_by_tool[tool_name] = timed_count_by_tool.get(tool_name, 0) + 1

        else:
            # A user message or a harness marker: neither a call nor a result, so
            # nothing to count. It still advances the clock below, which is what
            # makes the next model call's gap start from the right place.
            pass

        if at is not None:
            previous_at = at

    # Longest total first: the summary's job is to say where the time went.
    tools = sorted(
        (
            ToolUsage(
                tool_name=tool_name,
                call_count=count,
                total_seconds=round(seconds_by_tool.get(tool_name, 0.0), 3),
                timed_call_count=timed_count_by_tool.get(tool_name, 0),
            )
            for tool_name, count in call_count_by_tool.items()
        ),
        key=lambda usage: (-usage.total_seconds, -usage.call_count, usage.tool_name),
    )

    return AgentOverview(
        llm_call_count=llm_call_count,
        llm_total_seconds=round(llm_total_seconds, 3),
        llm_timed_call_count=llm_timed_call_count,
        llm_output_tokens=token_totals["output_tokens"],
        llm_input_tokens=token_totals["input_tokens"],
        llm_cache_read_tokens=token_totals["cache_read_tokens"],
        llm_cache_write_tokens=token_totals["cache_write_tokens"],
        tools=tools,
        tool_call_count=sum(usage.call_count for usage in tools),
        tool_total_seconds=round(sum(usage.total_seconds for usage in tools), 3),
        skipped_gap_count=skipped_gap_count,
    )
