import pytest

from imbue.chat.harnesses.claude.tool_labels import shell_command
from imbue.chat.harnesses.claude.tool_labels import tool_labels
from imbue.chat.harnesses.claude.tool_labels import tool_reason


@pytest.mark.parametrize(
    "tool_name, input_preview, expected",
    [
        pytest.param("Read", '{"file_path":"src/midnight.ts"}', ("read src/midnight.ts", "Reading midnight.ts"), id="read"),
        pytest.param("Edit", '{"file_path":"a/b/plugin.py"}', ("edited a/b/plugin.py", "Editing plugin.py"), id="edit"),
        # Both fields collapse MultiEdit onto the same word as Edit: the reader cares
        # that a file was edited, not which of the two tools did it.
        pytest.param(
            "MultiEdit", '{"file_path":"plugin.py"}', ("edited plugin.py", "Editing plugin.py"), id="multi_edit"
        ),
        pytest.param("Write", '{"file_path":"notes.md"}', ("wrote notes.md", "Writing notes.md"), id="write"),
        pytest.param("Grep", '{"pattern":"harness"}', ('searched "harness"', 'Searching "harness"'), id="grep_is_quoted"),
        pytest.param(
            "WebSearch",
            '{"query":"codex sdk"}',
            ('searched the web "codex sdk"', 'Searching the web "codex sdk"'),
            id="web_search",
        ),
        pytest.param("Skill", '{"skill":"commit"}', ("loaded skill commit", "Loading skill commit"), id="skill"),
        pytest.param("Monitor", "{}", ("monitored", "Monitoring…"), id="known_verb_without_target"),
        pytest.param("Agent", '{"description":"go"}', ("delegated go", "Delegating to sub-agent…"), id="agent"),
        pytest.param("Task", "{}", ("delegated to a sub-agent", "Delegating to sub-agent…"), id="task"),
    ],
)
def test_claude_tool_labels(tool_name: str, input_preview: str, expected: tuple[str, str]) -> None:
    assert tool_labels(tool_name, input_preview) == expected


def test_the_header_names_what_ran_and_never_the_tool() -> None:
    """The whole point of the header: a reader learns the work, not the machinery.

    ``Tool: Bash`` told them nothing they wanted to know, so no header may contain
    the word Tool or a bare tool name where a real operation is known.
    """
    header, _ = tool_labels("Bash", '{"command":"uv run pytest -q","description":"Run the tests"}')
    assert header == "ran uv run pytest -q"
    assert "Tool:" not in header


def test_the_header_shows_the_command_while_the_caption_shows_the_description() -> None:
    """The one tool where the two deliberately diverge.

    The caption's narrow strip prefers the agent's prose ("what this is FOR"); the
    header wants the literal command. The prose is not lost -- it becomes the reason.
    """
    raw_input = '{"command":"uv run pytest -q","description":"Run the tests"}'
    header, caption = tool_labels("Bash", raw_input)
    assert header == "ran uv run pytest -q"
    assert caption == "Running Run the tests"
    assert tool_reason("Bash", raw_input) == "Run the tests"


def test_bash_falls_back_to_the_command_when_undescribed() -> None:
    header, caption = tool_labels("Bash", '{"command":"ls -la"}')
    assert (header, caption) == ("ran ls -la", "Running ls -la")
    assert tool_reason("Bash", '{"command":"ls -la"}') is None


def test_target_key_order_is_load_bearing() -> None:
    """A WebFetch carries both url and description; the url is the better target."""
    _, caption_label = tool_labels("WebFetch", '{"url":"https://example.com","description":"read it"}')
    assert caption_label == "Fetching page https://example.com"


def test_a_long_path_keeps_its_tail_so_the_file_is_still_named() -> None:
    """Clipping a path from the right would leave the directory and lose the file."""
    header, _ = tool_labels("Read", '{"file_path":"/mngr-vol/home/workspace/system/apps/chat/frontend/src/index.ts"}')
    assert header == "read .../frontend/src/index.ts"


def test_a_search_leads_with_the_pattern_not_the_directory() -> None:
    """"searched system/apps/chat" says nothing about what was being looked for."""
    header, _ = tool_labels("Grep", '{"pattern":"header_label","path":"system/apps/chat"}')
    assert header == 'searched "header_label" in system/apps/chat'


@pytest.mark.parametrize(
    "input_preview",
    [
        pytest.param('{"file_path":"a.ts"', id="truncated_json"),
        pytest.param("", id="empty"),
        pytest.param("[1,2,3]", id="not_an_object"),
    ],
)
def test_an_unparseable_preview_degrades_to_the_bare_verb(input_preview: str) -> None:
    """Previews are clipped at a fixed length, so invalid JSON is expected, not exceptional."""
    assert tool_labels("Read", input_preview) == ("read", "Reading…")


def test_unknown_tool_with_a_target_still_says_something_useful() -> None:
    """No verb is known, so the tool's own name is the most informative thing left."""
    assert tool_labels("SomeNewTool", '{"path":"x/y.txt"}') == ("SomeNewTool x/y.txt", "Running y.txt")


def test_unknown_tool_without_a_target_is_generic() -> None:
    assert tool_labels("SomeNewTool", "{}") == ("SomeNewTool", "Running tool…")


def test_a_nameless_call_still_reads_as_a_sentence() -> None:
    assert tool_labels("", "{}") == ("ran a tool", "Running tool…")


def test_mcp_tool_reads_as_a_call_rather_than_a_raw_symbol() -> None:
    header_label, caption_label = tool_labels("mcp__deepwiki__ask_question", "{}")
    assert header_label == "called ask question"
    assert caption_label == "Running ask question"


def test_mcp_server_name_may_itself_contain_the_separator() -> None:
    """Split on the LAST separator, so a compound server name does not eat the tool."""
    _, caption_label = tool_labels("mcp__plugin_playwright_playwright__browser_click", "{}")
    assert caption_label == "Running browser click"


@pytest.mark.parametrize(
    "tool_name, input_preview",
    [
        pytest.param("Read", '{"file_path":"a.py"}', id="read_records_no_reason"),
        pytest.param("Edit", '{"file_path":"a.py","old_string":"x","new_string":"y"}', id="edit_records_no_reason"),
        pytest.param("Write", '{"file_path":"a.py","content":"x"}', id="write_records_no_reason"),
        pytest.param("Grep", '{"pattern":"x"}', id="grep_records_no_reason"),
        pytest.param("Skill", '{"skill":"commit"}', id="skill_records_no_reason"),
    ],
)
def test_a_tool_that_records_no_reason_reports_none_rather_than_inventing_one(
    tool_name: str, input_preview: str
) -> None:
    """Most calls have no stated reason anywhere in their input.

    A guessed reason would read exactly like a stated one and be wrong, so the
    reason line is simply absent for these.
    """
    assert tool_reason(tool_name, input_preview) is None


def test_a_delegation_states_its_reason() -> None:
    assert tool_reason("Agent", '{"description":"Audit the snapshots"}') == "Audit the snapshots"


def test_a_blank_description_is_no_reason_at_all() -> None:
    assert tool_reason("Bash", '{"command":"ls","description":"   "}') is None


def test_shell_command_reads_claudes_command_key_and_ignores_other_tools() -> None:
    assert shell_command("Bash", '{"command":"ls -la"}') == "ls -la"
    assert shell_command("Read", '{"file_path":"/x"}') is None
    assert shell_command("Bash", '{"command":123}') is None
