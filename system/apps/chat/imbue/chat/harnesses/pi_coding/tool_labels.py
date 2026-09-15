"""pi's tool-call labels: ``read foo.py`` for the header, ``Reading foo.py`` for the caption.

pi reports the real tool name on every call (``read`` / ``bash`` / ``edit`` / ...),
so -- like claude, unlike codex's code-mode ``exec`` -- the verb comes straight off
that name and only the target has to be derived. The claude peer is
:mod:`harnesses.claude.tool_labels`; this mirrors it for pi's lowercase tool names
and argument shapes (verified live: ``read {path,limit}``, ``bash {command}``, ...).

pi's ``bash`` call carries no model-written description, so unlike claude it has no
stated reason to show: :func:`tool_reason` returns None for every pi tool.
"""

from typing import Any

from imbue.chat.harnesses.tool_labels import GENERIC_CAPTION
from imbue.chat.harnesses.tool_labels import basename
from imbue.chat.harnesses.tool_labels import first_string_value
from imbue.chat.harnesses.tool_labels import mcp_caption
from imbue.chat.harnesses.tool_labels import parse_input_preview
from imbue.chat.harnesses.tool_labels import quoted
from imbue.chat.harnesses.tool_labels import shorten
from imbue.chat.harnesses.tool_labels import shorten_command
from imbue.chat.harnesses.tool_labels import shorten_path
from imbue.imbue_common.pure import pure

# pi's built-in tool names are lowercase; title-case them for the header so it reads
# like claude's ("Tool: Read"). A tool absent from this table falls back to its raw name.
#
# The web_* entries are the pi-web-access extension (npm:pi-web-access), not built-ins.
# Their header nouns match claude's WebSearch/WebFetch (and codex's web__run -> WebSearch)
# so the three harnesses read alike. Names verified live against pi-web-access 0.19.0:
# web_search {query|queries}, fetch_content {url|urls}, source_check {claim},
# get_search_content {responseId,...}. These are the package's default tool names; a
# web-search.json `toolNames` override would rename them and skip this table.
_HEADER_NOUN_BY_TOOL: dict[str, str] = {
    "read": "Read",
    "write": "Write",
    "edit": "Edit",
    "bash": "Bash",
    "grep": "Grep",
    "find": "Find",
    "ls": "List",
    "web_search": "WebSearch",
    "fetch_content": "WebFetch",
    "source_check": "SourceCheck",
    "get_search_content": "SearchContent",
}

# Caption verb per tool. Absent -> the generic path (mcp / "Running <target>" / fallback).
_VERB_BY_TOOL_NAME: dict[str, str] = {
    "read": "Reading",
    "write": "Writing",
    "edit": "Editing",
    "bash": "Running",
    "grep": "Searching",
    "find": "Searching",
    "ls": "Listing",
    "web_search": "Searching the web",
    "fetch_content": "Fetching page",
    "source_check": "Checking sources",
    "get_search_content": "Retrieving results",
}

# The header's verb: past tense and lowercase, so the eye goes to the target beside
# it. Mirrors claude's table for the same operations.
_HEADER_VERB_BY_TOOL: dict[str, str] = {
    "read": "read",
    "write": "wrote",
    "edit": "edited",
    "bash": "ran",
    "grep": "searched",
    "find": "searched",
    "ls": "listed",
    "web_search": "searched the web",
    "fetch_content": "fetched",
    "source_check": "checked sources for",
    "get_search_content": "retrieved results for",
}

_SEARCH_TOOL_NAMES = ("grep", "find", "web_search")

# Input keys that name what a call acts on, most specific first (mirrors claude's order).
# ``url`` covers fetch_content; ``query`` covers web_search / get_search_content; ``claim``
# covers source_check's assertion (read like claude's plain ``description`` target).
_TARGET_PATH_KEYS = ("file_path", "path")
_TARGET_TEXT_KEYS = ("command", "url")
_TARGET_QUOTED_KEYS = ("pattern", "query")
_TARGET_PLAIN_KEYS = ("claim", "description")

# tk lifecycle verbs whose Bash command must survive input truncation, so the chat
# progress view can read the ``--step`` titles / close summaries out of the command
# (mirrors the claude/codex parsers' set).

# pi's shell tool -- the one whose command can be a tk lifecycle op.
_BASH_TOOL_NAME = "bash"


@pure
def _target(tool_name: str, tool_input: dict[str, Any]) -> str | None:
    """What the call is acting on, as it should read after the verb.

    Unlike claude's Bash (which carries a model-written ``description``), pi's ``bash``
    call has only ``command``, so the command itself is the target.
    """
    path = first_string_value(tool_input, *_TARGET_PATH_KEYS)
    if path is not None:
        return basename(path)
    text = first_string_value(tool_input, *_TARGET_TEXT_KEYS)
    if text is not None:
        return shorten(text)
    searched = first_string_value(tool_input, *_TARGET_QUOTED_KEYS)
    if searched is not None:
        return quoted(searched)
    plain = first_string_value(tool_input, *_TARGET_PLAIN_KEYS)
    if plain is not None:
        return shorten(plain)
    return None


@pure
def _header_target(tool_name: str, tool_input: dict[str, Any]) -> str | None:
    """What the call acted on, for the header: the literal thing, not a summary."""
    if tool_name == _BASH_TOOL_NAME:
        command = first_string_value(tool_input, "command")
        return shorten_command(command) if command is not None else None

    # A search names what it looked FOR first; its path is only the scope.
    if tool_name in _SEARCH_TOOL_NAMES:
        searched = first_string_value(tool_input, *_TARGET_QUOTED_KEYS)
        if searched is not None:
            scope = first_string_value(tool_input, *_TARGET_PATH_KEYS)
            return f"{quoted(searched)} in {shorten_path(scope)}" if scope is not None else quoted(searched)

    path = first_string_value(tool_input, *_TARGET_PATH_KEYS)
    if path is not None:
        return shorten_path(path)
    text = first_string_value(tool_input, *_TARGET_TEXT_KEYS)
    if text is not None:
        return shorten_command(text)
    searched = first_string_value(tool_input, *_TARGET_QUOTED_KEYS)
    if searched is not None:
        return quoted(searched)
    plain = first_string_value(tool_input, *_TARGET_PLAIN_KEYS)
    if plain is not None:
        return shorten(plain)
    return None


@pure
def header_parts(tool_name: str, input_preview: str) -> tuple[str, str]:
    """``(verb, target)`` for the block header, from a raw input preview."""
    return _header_parts(tool_name, parse_input_preview(input_preview))


@pure
def _header_parts(tool_name: str, tool_input: dict[str, Any]) -> tuple[str, str]:
    """``(verb, target)``: prose verb, then the literal thing the call acted on.

    Kept apart rather than joined because the view sets them in different type --
    only the target is machine text -- and a joined label could not be split back
    apart without guessing where a multi-word verb ends.
    """
    if not tool_name:
        return "ran a tool", ""
    target = _header_target(tool_name, tool_input)
    verb = _HEADER_VERB_BY_TOOL.get(tool_name)
    if verb is not None:
        return verb, target or ""

    mcp = mcp_caption(tool_name)
    if mcp is not None:
        return f"called {mcp.removeprefix('Running ')}", target or ""
    return _HEADER_NOUN_BY_TOOL.get(tool_name, tool_name), target or ""


@pure
def _header_label(tool_name: str, tool_input: dict[str, Any]) -> str:
    """The two header halves joined, for the single-string ``header_label`` field."""
    verb, target = _header_parts(tool_name, tool_input)
    return f"{verb} {target}" if target else verb


@pure
def tool_reason(tool_name: str, input_preview: str) -> str | None:
    """pi records no model-written reason on any tool, so this is always None.

    Kept so every harness answers the same question, and so a pi tool that later
    grows a description field only has to be listed here.
    """
    return None


@pure
def tool_labels(tool_name: str, input_preview: str) -> tuple[str, str]:
    """``(header_label, caption_label)`` for one pi tool call."""
    tool_input = parse_input_preview(input_preview)
    header_label = _header_label(tool_name, tool_input)

    verb = _VERB_BY_TOOL_NAME.get(tool_name)
    target = _target(tool_name, tool_input)

    if verb is not None:
        return header_label, f"{verb} {target}" if target is not None else f"{verb}…"

    mcp = mcp_caption(tool_name)
    if mcp is not None:
        return header_label, mcp

    if target is not None:
        return header_label, f"Running {target}"
    return header_label, GENERIC_CAPTION


@pure
def shell_command(tool_name: str, raw_input: str) -> str | None:
    """The shell command this tool call runs, or None if it is not a shell call.

    The ONE question each harness answers for itself. Whether that command is a tk lifecycle
    invocation is decided centrally (``tool_output.is_pure_tk_lifecycle_command`` for the hide
    rule, ``is_tk_lifecycle_anywhere`` for the resident tk_command stamp), so the rules live in one
    place and cannot drift between harnesses.
    """
    if tool_name != _BASH_TOOL_NAME:
        return None
    command = parse_input_preview(raw_input).get("command")
    return command if isinstance(command, str) else None
