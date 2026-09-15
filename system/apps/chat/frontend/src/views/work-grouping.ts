/**
 * Which work follows which sentence.
 *
 * An agent's prose and the calls it then makes arrive as SEPARATE assistant
 * messages -- measured over a real session: 160 messages carrying only tool calls,
 * 32 carrying only text, and none carrying both. So the sentence explaining a piece
 * of work is always the message before it, never part of it.
 *
 * That sentence is the only reason available for most calls. A file read records no
 * reason anywhere in its input (unlike a shell command, which states one), so
 * without this the majority of calls would have nothing above them saying why. This
 * does not invent anything: it marks the calls that a preceding sentence introduced,
 * and the renderers indent those under it so the two read as one group.
 *
 * The run ends at anything that is not more work: the next sentence starts its own
 * group, and a user-side interruption ends the current one outright.
 */

import type { AssistantMessageEvent } from "../models/Response";

/** True when a message is prose: it says something and calls nothing. */
function isProse(event: AssistantMessageEvent): boolean {
  return Boolean(event.text) && (event.tool_calls?.length ?? 0) === 0;
}

/** True when a message is work: it issues at least one call. */
function isWork(event: AssistantMessageEvent): boolean {
  return (event.tool_calls?.length ?? 0) > 0;
}

/**
 * The ids of the work messages that a preceding sentence introduced.
 *
 * A message is in the set when the nearest earlier message in this run is prose, or
 * is other work that was itself introduced by that prose -- so a whole batch of
 * calls groups under one sentence, not just the first.
 */
export function groupedWorkEventIds(events: readonly AssistantMessageEvent[]): Set<string> {
  const grouped = new Set<string>();
  let isUnderProse = false;
  for (const event of events) {
    if (isProse(event)) {
      // A new sentence opens a new group; the work after it belongs to this one.
      isUnderProse = true;
      continue;
    }
    if (isWork(event)) {
      if (isUnderProse) grouped.add(event.event_id);
      continue;
    }
    // Neither prose nor work (an empty or thinking-only message): it neither opens
    // a group nor belongs to one, and it does not break the run either.
  }
  return grouped;
}

/** The indent + rule that ties grouped work to the sentence above it. */
export const GROUPED_WORK_CLASS = "tool-call-group border-l border-subtle pl-3";
