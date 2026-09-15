"""Tests for the agent overview's counts and durations."""

from typing import Any

from imbue.chat.overview import MAX_ATTRIBUTABLE_GAP_SECONDS
from imbue.chat.overview import build_overview
from imbue.chat.overview import parse_timestamp


def _at(second: float) -> str:
    whole = int(second)
    micros = int(round((second - whole) * 1_000_000))
    return f"2026-09-15T13:00:{whole:02d}.{micros:06d}Z"


def _user(at: str) -> dict[str, Any]:
    return {"type": "user_message", "event_id": f"u{at}", "content": "go", "timestamp": at}


def _assistant(
    at: str,
    calls: list[tuple[str, str]] | None = None,
    usage: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "type": "assistant_message",
        "event_id": f"a{at}",
        "text": "working",
        "timestamp": at,
        "tool_calls": [{"tool_call_id": call_id, "tool_name": name, "input_chars": 4} for call_id, name in calls or []],
        "usage": usage,
    }


def _result(at: str, call_id: str, name: str) -> dict[str, Any]:
    return {
        "type": "tool_result",
        "event_id": f"r{call_id}",
        "tool_call_id": call_id,
        "tool_name": name,
        "timestamp": at,
        "output_chars": 3,
        "is_error": False,
    }


def test_an_empty_conversation_reports_nothing() -> None:
    overview = build_overview([])
    assert overview.llm_call_count == 0
    assert overview.tool_call_count == 0
    assert overview.tools == []


def test_each_assistant_message_counts_as_one_model_call() -> None:
    overview = build_overview([_user(_at(0)), _assistant(_at(1)), _assistant(_at(2))])
    assert overview.llm_call_count == 2


def test_a_model_call_is_timed_from_the_event_before_it() -> None:
    """The model was working for exactly that gap."""
    overview = build_overview([_user(_at(0)), _assistant(_at(2.5))])
    assert overview.llm_total_seconds == 2.5
    assert overview.llm_timed_call_count == 1


def test_a_tool_call_is_timed_from_its_issue_to_its_result() -> None:
    overview = build_overview(
        [_user(_at(0)), _assistant(_at(1), [("c1", "Bash")]), _result(_at(3), "c1", "Bash")]
    )
    assert [(t.tool_name, t.call_count, t.total_seconds) for t in overview.tools] == [("Bash", 1, 2.0)]


def test_calls_of_the_same_kind_are_summed() -> None:
    overview = build_overview(
        [
            _user(_at(0)),
            _assistant(_at(1), [("c1", "Bash")]),
            _result(_at(2), "c1", "Bash"),
            _assistant(_at(3), [("c2", "Bash")]),
            _result(_at(7), "c2", "Bash"),
        ]
    )
    assert [(t.tool_name, t.call_count, t.total_seconds) for t in overview.tools] == [("Bash", 2, 5.0)]


def test_kinds_are_ordered_by_where_the_time_went() -> None:
    """The summary's job is to say what was slow, so the slowest kind leads."""
    overview = build_overview(
        [
            _user(_at(0)),
            _assistant(_at(1), [("c1", "Read"), ("c2", "Bash")]),
            _result(_at(2), "c1", "Read"),
            _result(_at(9), "c2", "Bash"),
        ]
    )
    assert [t.tool_name for t in overview.tools] == ["Bash", "Read"]


def test_a_call_with_no_result_still_counts_but_is_not_timed() -> None:
    """An interrupted or still-running call happened; it just cannot be measured."""
    overview = build_overview([_user(_at(0)), _assistant(_at(1), [("c1", "Bash")])])
    assert [(t.call_count, t.timed_call_count, t.total_seconds) for t in overview.tools] == [(1, 0, 0.0)]


def test_an_idle_gap_is_not_counted_as_work() -> None:
    """A long wait is the conversation sitting idle, not the model thinking."""
    idle = "2026-09-15T14:00:00.000000Z"
    overview = build_overview([_user(_at(0)), _assistant(idle)])
    assert overview.llm_total_seconds == 0.0
    assert overview.llm_timed_call_count == 0
    assert overview.skipped_gap_count == 1
    # The call itself still happened and is still counted.
    assert overview.llm_call_count == 1


def test_a_gap_at_the_limit_is_still_counted() -> None:
    overview = build_overview([_user(_at(0)), _assistant("2026-09-15T13:10:00.000000Z")])
    assert overview.llm_total_seconds == MAX_ATTRIBUTABLE_GAP_SECONDS


def test_events_out_of_order_do_not_produce_negative_time() -> None:
    """Clock skew between sources must never subtract from a total."""
    overview = build_overview([_user(_at(5)), _assistant(_at(1))])
    assert overview.llm_total_seconds == 0.0
    assert overview.skipped_gap_count == 1


def test_a_missing_timestamp_leaves_the_call_counted_but_untimed() -> None:
    event = _assistant(_at(1))
    del event["timestamp"]
    overview = build_overview([_user(_at(0)), event])
    assert overview.llm_call_count == 1
    assert overview.llm_timed_call_count == 0


def test_totals_add_up_across_kinds() -> None:
    overview = build_overview(
        [
            _user(_at(0)),
            _assistant(_at(1), [("c1", "Bash"), ("c2", "Read")]),
            _result(_at(2), "c1", "Bash"),
            _result(_at(4), "c2", "Read"),
        ]
    )
    assert overview.tool_call_count == 2
    assert overview.tool_total_seconds == 4.0


def test_a_result_for_an_unknown_call_is_ignored() -> None:
    """A result whose call scrolled out of the transcript has nothing to attribute to."""
    overview = build_overview([_result(_at(2), "orphan", "Bash")])
    assert overview.tools == []


def test_timestamps_parse_with_and_without_the_zulu_suffix() -> None:
    assert parse_timestamp("2026-09-15T13:00:00.000000Z") is not None
    assert parse_timestamp("2026-09-15T13:00:00+00:00") is not None
    assert parse_timestamp("not a time") is None
    assert parse_timestamp(None) is None


def _usage(output: int = 0, input_: int = 0, cache_read: int = 0, cache_write: int = 0) -> dict[str, Any]:
    return {
        "output_tokens": output,
        "input_tokens": input_,
        "cache_read_tokens": cache_read,
        "cache_write_tokens": cache_write,
    }


def test_tokens_are_summed_across_model_calls() -> None:
    overview = build_overview(
        [
            _user(_at(0)),
            _assistant(_at(1), usage=_usage(output=100, input_=5, cache_read=900, cache_write=50)),
            _assistant(_at(2), usage=_usage(output=20, input_=3, cache_read=80, cache_write=7)),
        ]
    )
    assert overview.llm_output_tokens == 120
    assert overview.llm_input_tokens == 8
    assert overview.llm_cache_read_tokens == 980
    assert overview.llm_cache_write_tokens == 57


def test_a_call_reporting_no_usage_contributes_nothing() -> None:
    """A harness that records no usage must not make the totals a guess."""
    overview = build_overview([_user(_at(0)), _assistant(_at(1))])
    assert overview.llm_call_count == 1
    assert overview.llm_output_tokens == 0


def test_a_partial_usage_record_contributes_what_it_has() -> None:
    overview = build_overview([_user(_at(0)), _assistant(_at(1), usage={"output_tokens": 42})])
    assert overview.llm_output_tokens == 42
    assert overview.llm_input_tokens == 0


def test_a_malformed_usage_value_is_ignored_rather_than_crashing() -> None:
    overview = build_overview([_user(_at(0)), _assistant(_at(1), usage={"output_tokens": "lots"})])
    assert overview.llm_output_tokens == 0


def test_tool_calls_carry_no_tokens_of_their_own() -> None:
    """A tool's output is charged to the model call that reads it next, not to the tool."""
    overview = build_overview(
        [_user(_at(0)), _assistant(_at(1), [("c1", "Bash")], usage=_usage(output=10)), _result(_at(2), "c1", "Bash")]
    )
    assert overview.llm_output_tokens == 10
    assert not hasattr(overview.tools[0], "output_tokens")
