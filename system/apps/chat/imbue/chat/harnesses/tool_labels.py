"""Human labels for a tool call, computed where the harness is already known.

Every tool call a parser emits carries two strings, plus an optional third:

- ``header_label``  -- what the call actually DID, for the transcript block
  header: a past-tense verb and the thing it acted on (``ran sha256sum …``,
  ``read scripts/run.py``). It deliberately does NOT name the tool: the tool's
  identity is an implementation detail, and a header that reads ``Tool: Bash``
  tells the reader nothing they wanted to know.
- ``caption_label`` -- verb + target, for the live activity strip. Present tense
  and narrower, because it describes a call still in flight (``Reading foo.py``).
- ``reason_label`` -- the agent's OWN stated reason for making the call, when the
  tool records one. Only some tools do (a shell command's ``description``, a
  delegation's), so this is None far more often than not, and a missing reason is
  rendered as nothing rather than guessed at.

They are computed HERE, in the harness's own parser, rather than in the frontend.
The frontend renders whichever it needs and so has to know nothing about which
harness produced the event -- which matters most for codex, where code mode names
every operation ``exec`` and buries the real one in a JavaScript argument.

This module holds only the pieces every harness shares; the per-harness verb
tables live in each harness's own ``tool_labels`` module.
"""

import json
import re
from collections.abc import Mapping
from typing import Any

from imbue.imbue_common.pure import pure

# Targets are appended to a verb in a narrow strip, so they are truncated well
# before the strip would wrap.
MAX_TARGET_LENGTH = 60

# The block header is a full-width row rather than a narrow strip, so it can carry
# a real shell command -- but it is still one line that must not wrap.
MAX_HEADER_TARGET_LENGTH = 110

# A stated reason is one sentence above the block; longer than that is prose the
# agent should have put in its message instead.
MAX_REASON_LENGTH = 200

GENERIC_CAPTION = "Running tool…"

# The input key an agent states its reason in. Claude's Bash and Agent tools both
# use ``description``; the other harnesses' equivalents are mapped onto it in
# their own modules.
REASON_INPUT_KEY = "description"

_MCP_PREFIX = "mcp__"
_MCP_SEPARATOR = "__"


@pure
def basename(path: str) -> str:
    """The final path segment, or the whole string when there is no separator."""
    return path.rstrip("/").rsplit("/", 1)[-1] or path


@pure
def shorten(text: str, max_length: int = MAX_TARGET_LENGTH) -> str:
    """Collapse whitespace and clip to ``max_length``, marking the clip with an ellipsis."""
    collapsed = re.sub(r"\s+", " ", text).strip()
    if len(collapsed) <= max_length:
        return collapsed
    return collapsed[: max_length - 1] + "…"


@pure
def quoted(text: str) -> str:
    """A search term as it should read in a caption: shortened and in quotes."""
    return f'"{shorten(text)}"'


@pure
def mcp_caption(tool_name: str) -> str | None:
    """``mcp__<server>__<tool>`` -> ``Running <tool with spaces>``; None for non-MCP names.

    Splits on the LAST separator because a server name may itself contain one
    (both harnesses sanitise dots to underscores, so ``server.one`` arrives as
    ``server_one`` but a hand-named server can still be ``a__b``).
    """
    if not tool_name.startswith(_MCP_PREFIX):
        return None
    separator_index = tool_name.rfind(_MCP_SEPARATOR)
    if separator_index <= len(_MCP_PREFIX) - 1:
        return None
    tool_part = tool_name[separator_index + len(_MCP_SEPARATOR) :]
    if not tool_part:
        return None
    return f"Running {tool_part.replace('_', ' ')}"


@pure
def parse_input_preview(input_preview: str) -> dict[str, Any]:
    """The tool input as a dict, or empty when it is absent, not JSON, or not an object.

    Some harness inputs are not JSON objects at all (codex's code-mode JS program,
    a bare string argument). That is expected, not exceptional: the caller falls
    back to a generic label rather than guessing at an unparseable input.
    """
    try:
        parsed = json.loads(input_preview)
    except (ValueError, TypeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


@pure
def first_string_value(source: dict[str, Any], *keys: str) -> str | None:
    """The first key present with a non-empty string value, in the order given."""
    for key in keys:
        value = source.get(key)
        if isinstance(value, str) and value:
            return value
    return None


# How many trailing path segments a header keeps. Three is enough to tell two
# same-named files apart in practice, and short enough that an absolute path from
# the filesystem root does not swamp the row.
_HEADER_PATH_SEGMENTS = 3


@pure
def shorten_path(path: str, max_length: int = MAX_HEADER_TARGET_LENGTH) -> str:
    """A path trimmed to its informative tail: the last few segments.

    ``shorten`` keeps the head, which is right for prose and wrong for a path:
    clipping ``system/apps/chat/frontend/src/views/ToolCallBlock.ts`` from the
    right would leave the reader with the directory and no file. Trimming by
    segment rather than by character also means the result is always a readable
    path fragment rather than a string cut mid-name.
    """
    collapsed = re.sub(r"\s+", " ", path).strip()
    segments = [segment for segment in collapsed.split("/") if segment]
    if len(segments) > _HEADER_PATH_SEGMENTS:
        collapsed = ".../" + "/".join(segments[-_HEADER_PATH_SEGMENTS:])
    if len(collapsed) <= max_length:
        return collapsed
    return "…" + collapsed[-(max_length - 1) :]


@pure
def shorten_command(command: str, max_length: int = MAX_HEADER_TARGET_LENGTH) -> str:
    """A shell command as one header line: newlines collapsed, clipped from the right.

    The head is what identifies a command (the program and its first arguments),
    so unlike a path this clips from the right.
    """
    return shorten(command, max_length)


@pure
def stated_reason(tool_input: Mapping[str, Any]) -> str | None:
    """The agent's own reason for this call, or None when the tool records none.

    Deliberately never inferred. A tool whose input has no reason field (every
    file read, edit, and write) yields None, and the reason line is then simply
    absent -- a guessed reason would be worse than no reason at all.
    """
    value = tool_input.get(REASON_INPUT_KEY)
    if not isinstance(value, str) or not value.strip():
        return None
    return shorten(value, MAX_REASON_LENGTH)
