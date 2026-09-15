"""Claude's tool-call labels: ``ran pytest -q`` for the header, ``Running the tests`` for the caption.

Claude reports the real tool name on every call, so both the header verb and the
caption verb come straight off that name -- no translation table needed to work
out what happened. What differs is what each says about it: the header names the
thing the call acted on (the command, the file), the caption names it in the
present tense for the live strip, and the reason is whatever the agent itself
said it was doing (shell commands and delegations only).
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
from imbue.chat.harnesses.tool_labels import stated_reason
from imbue.imbue_common.pure import pure

_BASH_TOOL_NAME = "Bash"

# Agent / Task are handled before this table -- they caption as a delegation
# rather than as a verb over a target.
_VERB_BY_TOOL_NAME: dict[str, str] = {
    "Read": "Reading",
    "Edit": "Editing",
    "MultiEdit": "Editing",
    "Write": "Writing",
    "Bash": "Running",
    "Grep": "Searching",
    "Glob": "Searching",
    "Skill": "Loading skill",
    "ToolSearch": "Loading tool",
    "WebSearch": "Searching the web",
    "WebFetch": "Fetching page",
    "LSP": "Querying language server",
    "NotebookEdit": "Editing notebook",
    "Monitor": "Monitoring",
    "SendMessage": "Sending message",
}

# The header's verb: past tense, because the block describes a call that already
# happened. Lowercase so the eye goes to the target beside it, which is the part
# that actually identifies the call.
_HEADER_VERB_BY_TOOL_NAME: dict[str, str] = {
    "Read": "read",
    "Edit": "edited",
    "MultiEdit": "edited",
    "Write": "wrote",
    "Bash": "ran",
    "Grep": "searched",
    "Glob": "searched",
    "Skill": "loaded skill",
    "ToolSearch": "loaded tool",
    "WebSearch": "searched the web",
    "WebFetch": "fetched",
    "LSP": "queried language server",
    "NotebookEdit": "edited notebook",
    "Monitor": "monitored",
    "SendMessage": "messaged",
}

_SEARCH_TOOL_NAMES = ("Grep", "Glob", "WebSearch")
_SUBAGENT_TOOL_NAMES = ("Agent", "Task")
_SUBAGENT_CAPTION = "Delegating to sub-agent…"
_SUBAGENT_HEADER_VERB = "delegated"

# Input keys that can name what a call is acting on, most specific first: a Read
# has a file_path, a Grep has a pattern, an unrecognised tool may only have a
# description. Order is load-bearing -- a WebFetch has both url and description.
_TARGET_PATH_KEYS = ("file_path", "path")
_TARGET_TEXT_KEYS = ("url", "command")
_TARGET_QUOTED_KEYS = ("pattern", "query")
_TARGET_PLAIN_KEYS = ("skill", "description")


@pure
def _target(tool_name: str, tool_input: dict[str, Any]) -> str | None:
    """What the call is acting on, as it should read after the verb."""
    # Bash: the agent's own description says what the command is FOR, which reads
    # far better than a shell line that the preview may have clipped mid-word.
    if tool_name == "Bash":
        described = first_string_value(tool_input, "description", "command")
        return shorten(described) if described is not None else None

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
    """What the call acted on, for the header: the literal thing, not a summary.

    The caption's target and this one diverge on exactly one tool, and
    deliberately: for a shell call the caption prefers the agent's prose
    description, while the header wants the command that actually ran. The
    description is not lost -- it becomes the reason line above the block.
    """
    if tool_name == _BASH_TOOL_NAME:
        command = first_string_value(tool_input, "command")
        return shorten_command(command) if command is not None else None

    # A search names what it looked FOR first; its path is the scope, and reading
    # "searched system/apps/chat" tells you nothing about what was being sought.
    if tool_name in _SEARCH_TOOL_NAMES:
        searched = first_string_value(tool_input, *_TARGET_QUOTED_KEYS)
        if searched is not None:
            scope = first_string_value(tool_input, *_TARGET_PATH_KEYS)
            return f"{quoted(searched)} in {shorten_path(scope)}" if scope is not None else quoted(searched)

    path = first_string_value(tool_input, *_TARGET_PATH_KEYS)
    if path is not None:
        return shorten_path(path)
    url = first_string_value(tool_input, "url")
    if url is not None:
        return shorten_command(url)
    searched = first_string_value(tool_input, *_TARGET_QUOTED_KEYS)
    if searched is not None:
        return quoted(searched)
    plain = first_string_value(tool_input, *_TARGET_PLAIN_KEYS)
    if plain is not None:
        return shorten(plain)
    return None


@pure
def tool_labels(tool_name: str, input_preview: str) -> tuple[str, str]:
    """``(header_label, caption_label)`` for one claude tool call."""
    tool_input = parse_input_preview(input_preview)
    header_label = _header_label(tool_name, tool_input)

    if tool_name in _SUBAGENT_TOOL_NAMES:
        return header_label, _SUBAGENT_CAPTION

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
def header_parts(tool_name: str, input_preview: str) -> tuple[str, str]:
    """``(verb, target)`` for the block header, from a raw input preview."""
    return _header_parts(tool_name, parse_input_preview(input_preview))


@pure
def _header_parts(tool_name: str, tool_input: dict[str, Any]) -> tuple[str, str]:
    """``(verb, target)`` for the block header -- the two halves, rendered differently.

    The verb is prose ("ran", "read") and the target is the literal thing the call
    acted on (a command, a path), so the view sets them in different type: only the
    target is machine text. They are returned separately rather than joined because
    splitting a joined label back apart would have to guess where a multi-word verb
    like "loaded skill" ends.

    An unrecognised tool has no verb to offer, so its own name becomes the verb --
    the one case where the header still names the tool, because there is nothing
    more informative to say. ``target`` is empty when the call acted on nothing
    nameable.
    """
    if not tool_name:
        return "ran a tool", ""
    if tool_name in _SUBAGENT_TOOL_NAMES:
        description = first_string_value(tool_input, "description")
        target = shorten(description) if description is not None else None
        return (_SUBAGENT_HEADER_VERB, target) if target else (f"{_SUBAGENT_HEADER_VERB} to a sub-agent", "")

    target = _header_target(tool_name, tool_input)
    verb = _HEADER_VERB_BY_TOOL_NAME.get(tool_name)
    if verb is not None:
        return verb, target or ""

    mcp = mcp_caption(tool_name)
    if mcp is not None:
        # "Running <tool with spaces>" -> "called <tool with spaces>".
        return f"called {mcp.removeprefix('Running ')}", target or ""
    return tool_name, target or ""


@pure
def _header_label(tool_name: str, tool_input: dict[str, Any]) -> str:
    """The two header halves joined, for the single-string ``header_label`` field."""
    verb, target = _header_parts(tool_name, tool_input)
    return f"{verb} {target}" if target else verb


@pure
def tool_reason(tool_name: str, input_preview: str) -> str | None:
    """The agent's own stated reason for this call, or None when it stated none.

    Only claude's shell and delegation tools take a description; a read, edit, or
    write records no reason anywhere, and this returns None for them rather than
    inventing one.
    """
    if tool_name != _BASH_TOOL_NAME and tool_name not in _SUBAGENT_TOOL_NAMES:
        return None
    return stated_reason(parse_input_preview(input_preview))


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
