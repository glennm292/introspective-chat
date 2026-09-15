---
title: "Introspective Chat"
description: "A chat that shows its own work: every action says what it ran and what came back, an index tracks the conversation, and an overview counts calls, time and tokens."
thumbnail: "template.svg"
version: v2
format: v2
---

# Introspective Chat

This file is the manifest for the **Introspective Chat** template (slug:
`introspective-chat`). It is the one document a future agent reads to understand,
present, and adapt this template. If you are an agent in a mind that was
created from this template, this file is your script: read all of it, then
follow "How to adapt it" below.

## What it is

A chat that shows its own work: every action says what it ran and what came back, an index tracks the conversation, and an overview counts calls, time and tokens.

In an ordinary agent chat, the conversation is mostly the agent's prose and its
actual actions are reduced to a row of opaque `Tool: Bash` labels you have to
click open one at a time to learn anything from. This template replaces the
workspace's built-in chat app with one that reports its own work as it goes.
Four things change. A tool call's header says what was done rather than which
tool ran -- `ran uv run pytest -q`, `read scripts/run.py` -- and the opening
lines of what came back are already visible in the collapsed block, so you can
read a run of work without clicking anything. Where a tool recorded the agent's
own stated reason for a call, that reason appears above the block; where it did
not, nothing is invented, and instead a batch of calls is indented under the
sentence of prose that introduced it. A navigation rail down the left lists
every message in the whole conversation -- the first two lines of each, yours
and the agent's -- and clicking one scrolls to it. And an "Agent Overview" link
in the footer opens a panel counting model calls and each kind of tool call,
with how long each took in total and on average, plus a row of token figures.
What the user sees when it is running is their normal chat tab -- same
conversation, same input box, same agents -- with an index rail at its left
edge, tool blocks that read as sentences with their output underneath, and an
"Agent Overview" link beside the model name at the bottom.

## How it works

The snapshot includes these paths (each is a repo-root-relative path copied
from the original mind onto a clean default-workspace-template base):

- `system/apps/chat`
- `system/libs/workspace_ui`

**`system/apps/chat`** is the chat app itself -- a Python/Flask backend
(`imbue/chat/`) plus a mithril frontend (`frontend/`, built into
`imbue/chat/static/`). It is not a new app: it is the workspace template's own
built-in chat, with this feature built into it. Everything described above lives
here.

**`system/libs/workspace_ui`** is the shared frontend library the chat and the
workspace shell both build against. Exactly one line of it differs from stock:
the hover tooltip's maximum width in `src/components/hoverTooltip.ts`, raised
from 480px to 560px so the Agent Overview's longer explanatory tooltip does not
end on an orphaned two-word line. The rest of the path ships unchanged so the
chat has a consistent library to build against.

### The parts of the feature, and where they live

- **Tool-call headers.** Each harness adapter has its own `tool_labels.py`
  (`imbue/chat/harnesses/{claude,codex,antigravity,pi_coding}/`, over the shared
  `imbue/chat/harnesses/tool_labels.py`). They now emit a `header_verb` (a
  past-tense verb in normal text) and a `header_target` (the literal command or
  path, in monospace) alongside the older joined `header_label`, and the
  frontend's `views/ToolCallBlock.ts` renders the two halves differently.
- **Output previews.** `imbue/chat/harnesses/events.py` attaches the opening of
  a tool's output to the event itself as a resident `output_preview`, capped at
  4 lines / 400 characters. This is a deliberate, bounded exception to the app's
  otherwise payload-free wire contract, and the code says so at the cap.
  Expanding a block still fetches the full output, into a scrollable pane.
- **Reason lines and grouping.** A reason is shown only where the tool actually
  recorded one (a shell command's or a delegation's `description`); nothing is
  inferred. `frontend/src/views/work-grouping.ts` covers the rest by indenting a
  batch of tool calls under the assistant prose that introduced it, which works
  because prose and tool calls arrive as separate assistant messages.
- **The conversation index.** `imbue/chat/outline.py` serves
  `GET /api/agents/<id>/outline`, walking every event once and returning just
  the opening lines of each message. It exists because the transcript in the
  page only holds a window, so a rail built from resident events would gain and
  lose entries while scrolling. `frontend/src/views/TranscriptOutline.ts`
  renders it; clicking an entry calls `jumpToEventIndex` on
  `views/transcript-scroll-engine.ts`, which loads the region when the target is
  not resident.
- **The Agent Overview.** `imbue/chat/overview.py` serves
  `GET /api/agents/<id>/overview` and `frontend/src/views/AgentOverviewModal.ts`
  renders it as a table of model calls and each kind of tool call, with counts,
  total time and average, plus a row of token figures. Durations are gaps
  between the transcript's own timestamps, so they are wall-clock rather than
  metered -- the panel says so in a tooltip, a call with no result yet is
  counted but marked untimed rather than rolled in as zero, and a gap long
  enough to be the conversation sitting idle is dropped rather than charged to
  the model.

### Runtime wiring

Nothing new runs. The `chat` program already declared in
`system/supervisord.conf` runs this app's `chat-app` console script (under the
OOM-priority tagger), and at startup the app registers its own manifest
(`system/apps/chat/app.toml`) and port 8010 through
`system/scripts/forward_port.py` -- unchanged by this template. The two new
endpoints are additional routes on that same server; the frontend changes are
compiled into the same bundle by the npm workspace the template already ships
(`system/apps/README.md`). Nothing calls out to the network: both endpoints read
the same on-disk transcript the chat app already reads.

## Recipe

This template is version `v1`. It is not a fork of the
workspace it came from -- it is DERIVED from it by a recipe: include these
paths, leave these out, apply these published-version rules. An update re-runs
the recipe against the current workspace and publishes the result as the next
version, so anything excluded stays excluded even though it still exists in the
source workspace.

The recipe is machine-read, so it lives in the sibling
[`template.toml`](template.toml) -- its `[recipe]` table -- along with
the structured requirements and the environment this template needs
installed. That file is authoritative for all of it; this one holds the prose.

## Requirements

Everything the adopting mind must deal with before this template is really
theirs. Two kinds of entry, handled at different times:

- **Activation** -- what must be SET UP before anything runs, in the
  machine-readable `requires_` forms below. The adopting agent acts on these
  ITSELF, first, before asking anything.
- **Adaptation** -- what must be DECIDED or REWIRED, in prose. Worked through
  interactively with the user, after activation.

### Activation -- nothing to set up

**There is nothing to activate.** This template needs no permission, no secret
and no LLM: there are deliberately no `requires_` lines below, and the
`[requirements]` table in `template.toml` is empty to match. None of the
included code calls an external service, an API, or a model. Both new endpoints
read the transcript the chat app is already reading from disk and render it. An
adopting agent should not prompt the user for anything before this runs; boot
the workspace and the chat is already the one described here.

### Adaptation -- what an adopter must deal with

- **One published-version change was applied to the snapshot.** The claude
  harness's queue-session test fixtures are stock upstream data that happens to
  contain a real contributor's work email, captured from a live session. It is
  replaced with an `example.com` placeholder here, because a public repo should
  not carry it. No test asserts on the address, and the harness suite (901 tests)
  passes against the scrubbed fixtures. If you diff this template against stock
  Minds, that is the difference you will see in those three files.

- **This template modifies a BUILT-IN app rather than adding a new one.** A mind
  created fresh from this template gets the chat exactly as published, and there
  is nothing to reconcile. A mind ADOPTING this into an existing workspace is
  merging these files against its own copy of `system/apps/chat` and
  `system/libs/workspace_ui`, which are live template code that upstream also
  changes. An adopter on a different Minds version should EXPECT merge conflicts
  in those two paths. Resolve them by reading the conflict, not by taking either
  side wholesale: "ours" silently drops the feature, "theirs" silently reverts
  whatever the adopting workspace's own chat had. The published base here is the
  upstream template at minds-v0.5.2.
- **The scroll engine's `jumpToEventIndex` is new.** The transcript scroll engine
  (`frontend/src/views/transcript-scroll-engine.ts`) gained this method so the
  index rail could navigate to a message outside the loaded window. It works, but
  it is lightly exercised outside this feature, and it has one known limit: an
  entry whose message renders inside a COLLAPSED step block cannot be scrolled
  to, because that message has no element in the page until the step is
  expanded. Most agent prose sits in that position, so most agent entries in the
  rail do not navigate. Fixing it means having the rail target (and expand) the
  containing step rather than the message. An adopter who touches the scroll
  engine for their own reasons should know this method exists and is depended on.
- **Some of this app's end-to-end tests are flaky on the stock template too.**
  The `test_a_new_chat_*` tests in `system/apps/chat` fail roughly one run in
  three on the UNMODIFIED upstream app, for reasons that predate and are
  unrelated to this template. An adopter running the suite will see it. Re-run
  before investigating, and do not treat it as damage this template caused.

## Environment

What this template needs INSTALLED, beyond what the template already has.
Declared in `template.toml`'s `[environment]` table; an adopting mind
converges it at ITS OWN pinned apt snapshot timestamp, so package versions come
out consistent with the rest of that mind's environment rather than frozen to
whatever this publisher happened to have.

Nothing extra -- runs on the stock workspace environment.

No apt packages, no global npm/uv/cargo tools, no `env.d` units: the
`[environment]` tables in `template.toml` are all empty. The backend is Python
that imports only what the chat app already depended on, and the frontend builds
with the npm workspace the template already ships. The included code shells out
to no binaries of its own.

## How to adapt it

Instructions for the NEXT agent -- the one adapting this template into a
new mind. This is the `use-template` skill's template path; in short:

1. Read this entire file first, especially "Requirements" below. It holds two
   kinds of entry and they are handled at different times: the machine-readable
   `requires_` lines are ACTIVATION (set them up before anything runs), and
   the prose bullets are ADAPTATION (decide or rewire them afterwards).
2. Present the template to the user in plain, non-technical language: what
   it is, what it does, and what it needs from them (name the activation
   requirements).
3. Ask whether they want to use the same connectors (e.g. their own Slack).
   If YES: ACTIVATE FIRST -- initiate every `requires_permission` line NOW
   via a latchkey permission request (see the `latchkey` skill; the request
   opens the approval/login flow in the minds app), wire up any
   `requires_secret` values, start the services, and get the app showing
   THE USER'S OWN DATA. Done for a data-backed app means the user can open it
   and see their own data -- NOT that a service starts or an endpoint returns
   200. Then tell them it is live and to take a look.
4. Only AFTER that (or immediately, if they chose different connectors -- the
   swap is then the first adaptation) ask: "How do you want to adapt it?"
5. Work through each requirement interactively, one at a time. Translate each
   into plain language, ask for a decision only when you genuinely need one,
   and resolve the obvious ones yourself.
6. When done, append a dated entry to "Adaptation history" below (never
   rewrite earlier entries) and commit.

## Publication history

This template's changelog: what each published version changed. The PUBLISHER
appends one entry per version (newest last); earlier entries are never rewritten.
This is distinct from "Adaptation history" below, which is the ADOPTERS' log.

### v1 (2026-09-15) -- first publication: the chat app with self-reporting tool calls, a conversation index rail, and the Agent Overview panel

### v2 (2026-09-15) -- same feature, rebuilt on the correct base

v1 was cut from the wrong commit: the publisher's workspace had merged a newer
upstream template, and the snapshot was taken from the MERGE commit rather than
from its upstream side. A merge commit's tree is the merged RESULT, so v1
carried one of the publisher's own unrelated apps (`system/apps/music_scout`)
that the recipe's `exclude` list claimed was left out. v2 is assembled by the
same recipe on the upstream parent instead, and ships exactly the six apps the
stock template has. No file belonging to this feature changed between v1 and
v2 -- only what surrounds it.

If you are reading this in a repo you adopted from v1, the fix is to delete
`system/apps/music_scout` and drop its `[program:music-scout]` block from
`system/supervisord.conf`; nothing in this template depends on it.

## Adaptation history

Each mind that adapts this template appends one dated entry below. Earlier
entries are never rewritten.
