"""Tests for pi's tool-call labels and the tk-input-truncation exemption."""

from __future__ import annotations

import json

from imbue.chat.harnesses.pi_coding.tool_labels import shell_command
from imbue.chat.harnesses.pi_coding.tool_labels import tool_labels
from imbue.chat.harnesses.pi_coding.tool_labels import tool_reason


def _preview(**arguments: object) -> str:
    return json.dumps(arguments)


def test_read_labels() -> None:
    header, caption = tool_labels("read", _preview(path="/home/user/workspace/README.md", limit=5))
    # Only the last three segments survive, so a long absolute path stays one short line.
    assert header == "read .../user/workspace/README.md"
    assert caption == "Reading README.md"


def test_bash_captions_the_command() -> None:
    # pi's bash has no `description`, unlike claude's; the command itself is the target.
    header, caption = tool_labels("bash", _preview(command="ls /home/user/workspace"))
    assert header == "ran ls /home/user/workspace"
    assert caption == "Running ls /home/user/workspace"


def test_grep_quotes_the_pattern() -> None:
    header, caption = tool_labels("grep", _preview(pattern="TODO"))
    assert header == 'searched "TODO"'
    assert caption == 'Searching "TODO"'


def test_web_search_labels() -> None:
    # pi-web-access extension: the shared "searched the web" wording, query quoted.
    header, caption = tool_labels("web_search", _preview(query="pi coding agent"))
    assert header == 'searched the web "pi coding agent"'
    assert caption == 'Searching the web "pi coding agent"'


def test_web_search_without_a_single_query_drops_to_bare_verb() -> None:
    # A multi-query call carries `queries` (an array), not `query`, so there is no single target.
    header, caption = tool_labels("web_search", _preview(queries=["a", "b"]))
    assert header == "searched the web"
    assert caption == "Searching the web…"


def test_fetch_content_captions_the_url() -> None:
    header, caption = tool_labels("fetch_content", _preview(url="https://pi.dev/docs"))
    assert header == "fetched https://pi.dev/docs"
    assert caption == "Fetching page https://pi.dev/docs"


def test_source_check_captions_the_claim() -> None:
    header, caption = tool_labels("source_check", _preview(claim="The earth is round"))
    assert header == "checked sources for The earth is round"
    assert caption == "Checking sources The earth is round"


def test_get_search_content_bare_verb_when_only_a_response_id() -> None:
    header, caption = tool_labels("get_search_content", _preview(responseId="abc123"))
    assert header == "retrieved results for"
    assert caption == "Retrieving results…"


def test_unknown_tool_falls_back_to_name_and_generic() -> None:
    """No verb is known, so the tool's own name is the most informative thing left."""
    header, caption = tool_labels("weirdtool", _preview())
    assert header == "weirdtool"
    assert caption == "Running tool…"


def test_pi_states_no_reason_on_any_tool() -> None:
    """Unlike claude's Bash, pi's carries no description -- so there is none to show."""
    assert tool_reason("bash", _preview(command="ls")) is None
    assert tool_reason("read", _preview(path="/x")) is None


def test_shell_command_reads_pis_command_key_and_ignores_other_tools() -> None:
    assert shell_command("bash", '{"command":"ls -la"}') == "ls -la"
    assert shell_command("read_file", '{"path":"/x"}') is None
