An "Agent Overview" link next to the model and effort in the footer opens a summary of what the conversation spent its time on.

It lists model calls and each kind of tool call with how many there were, how long they took in total, and the average per call, ordered so the biggest consumer of time is first. On this conversation: 990 model calls over 1h 33m, and 602 tool calls over 1h 40m, of which Bash was 480 calls and essentially all of the time.

The figures come from a new `/api/agents/<id>/overview` endpoint that walks every event, so they describe the whole conversation rather than the slice the transcript happens to be holding.

Both durations are gaps between the transcript's own timestamps -- a model call from the previous event to its reply, a tool call from where it was issued to its result -- so they are wall-clock rather than metered, and the panel says so rather than implying otherwise. A call with no result yet is counted but shown as untimed instead of being rolled in as zero, and a gap long enough to be the conversation sitting idle is left out rather than charged to the model.
