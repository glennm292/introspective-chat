Tool calls now render as a two-level block that says what happened rather than which tool ran.

The header is the work itself -- `ran uv run pytest -q`, `read scripts/run.py`, `searched "header_label" in system/apps/chat` -- replacing the old `Tool: Bash` / `Tool: Read` form in all four harnesses (claude, codex, antigravity, pi-coding) and in the frontend's fallback.

Under it, the result is now visible without clicking: the opening lines of the output ride the event as a resident `output_preview`, so a collapsed transcript shows what came back with no fetch at all. Expanding still loads the whole output, now in a scrollable pane rather than an unbounded one.

Above the block, a call shows the agent's own stated reason when the tool records one (a shell command's or a delegation's `description`). It is never inferred: the tools that record no reason -- every read, edit and write -- show no reason line rather than a guess. To cover those, a batch of work is indented under the sentence that introduced it, which is the only honest reason available for most calls.
