/**
 * Shared row builder for the main chat and a subagent's conversation.
 *
 * Both views render the same way: a single in-order walk of the transcript
 * (buildSections) into turn sections, flattened into the virtualized list's
 * top-level rows (buildRows) -- a user message, a whole ProgressBlock for a turn
 * that has tk steps, an ungrouped assistant message, a stop-hook chip, or a
 * trailing wrap-up reply. Sharing it here means a subagent's "View conversation"
 * gets the real progress view -- step timeline, statuses, summaries -- and the
 * same windowed virtualization as the main chat, with zero rendering drift.
 *
 * Structure and decoration both come from the transcript walk (tk prints its
 * step decoration on stdout, which buildSections parses); there is no
 * side-channel enrichment. `agentIsIdle` settles the frontier spinner on the
 * tail turn. The pre-login auth-error prefix is hidden here (a no-op for a
 * subagent, which never has one) so the two views stay byte-identical.
 */

import m from "mithril";
import type { TranscriptEvent, ToolResultEvent, AssistantMessageEvent } from "../models/Response";
import {
  renderUserMessage,
  renderAssistantMessage,
  renderPermissionItem,
  buildToolResultsWithSkillExpansions,
  computeAuthErrorHiddenEventIds,
} from "./message-renderers";
import { isHiddenUserMessage } from "./message-classification";
import { buildSections, type SectionView } from "./turn-grouping";
import { GROUPED_WORK_CLASS, groupedWorkEventIds } from "./work-grouping";
import { ProgressBlock } from "./ProgressBlock";

// Per-type fallback row heights, used until a row has been measured (live or
// offscreen). Rough is fine: they only affect spacer sizing for not-yet-measured
// rows, which the measurement passes correct.
export const ESTIMATED_USER_HEIGHT_PX = 90;
export const ESTIMATED_ASSISTANT_HEIGHT_PX = 240;
export const ESTIMATED_PROGRESS_HEIGHT_PX = 360;

// Layout for the message column: LEFT-ALIGNED, capped at the reading width.
// Shared by the live transcript views and the offscreen measurer, whose rows must
// lay out identically to measure identically -- the offscreen measurer reads this
// same constant, so the two cannot drift.
export const MESSAGE_LIST_CLASS = "message-list mr-auto w-full max-w-(--width-message-column) flex flex-col py-6";

export interface RowDescriptor {
  key: string;
  estimate: number;
  // The transcript event this row starts at, for mapping a row anchor to a
  // global event index (scroll persistence and fill-planner focus). Null only
  // for a turn section with no opening user message; consumers fall back to the
  // previous row's event.
  anchorEventId: string | null;
  // m.Children (not m.Vnode) because a row can be a component vnode
  // (ProgressBlock), whose typed attrs do not fit the bare Vnode<{}, {}>.
  render: () => m.Children;
}

/** A run of consecutive rows to render, `[startIndex, endIndex)`, or a spacer
 *  standing in for everything a run omits (including the virtual end spacers). */
export type WindowSegment =
  { kind: "rows"; startIndex: number; endIndex: number } | { kind: "spacer"; height: number };

/**
 * Render the ordered window segments (from the scroll engine's render plan) into
 * the message list's children: a spacer div for each spacer, and each row's own
 * vnode for each row-run. Shared by ChatPanel and SubagentView so both
 * virtualize identically. Spacer keys are role-stable (top/mid/bottom).
 */
export function renderTranscriptSegments(rows: RowDescriptor[], segments: WindowSegment[]): m.Children[] {
  const children: m.Children[] = [];
  for (let s = 0; s < segments.length; s++) {
    const segment = segments[s];
    if (segment.kind === "spacer") {
      const role = s === 0 ? "top" : s === segments.length - 1 ? "bottom" : "mid";
      children.push(
        m("div", { key: `__spacer_${role}`, style: `height: ${segment.height}px; overflow-anchor: none` }),
      );
    } else {
      for (let i = segment.startIndex; i < segment.endIndex; i++) {
        children.push(rows[i].render());
      }
    }
  }
  return children;
}

/**
 * Flatten the turn-grouped sections into the virtualized list's top-level rows.
 *
 * Each row is one mounted node in the message list. Keeping the grouping here
 * (rather than virtualizing raw events) preserves turn structure, the progress
 * timeline, skill expansions and auth-error hiding while still mounting only the
 * windowed rows. Render closures are invoked lazily so off-window rows never
 * build their vnodes (so MarkdownContent is only parsed for on-screen rows).
 * Every row's rendered root carries a DOM ``id`` equal to its ``key`` so
 * measureRows can read its height.
 */
/** The DOM id of the container wrapping one agent turn. */
export function agentTurnContainerId(anchorEventId: string): string {
  return `turn-${anchorEventId}`;
}

/**
 * The event the outline's agent entry for this turn points at: the first
 * assistant message in the turn that actually says something.
 *
 * This MIRRORS the rule in imbue/chat/outline.py (`build_outline`) -- keep the two
 * in step. They meet at the container id: the outline names an entry by that
 * event, and the turn is wrapped in a container named after it, so the navigation
 * rail has something to scroll to even when the message itself is inside a
 * collapsed step and has no element of its own.
 *
 * A mismatch is not fatal: the rail falls back to the message element, which is
 * exactly the behaviour it had before containers existed.
 */
export function agentTurnAnchorEventId(section: SectionView): string | null {
  const speaks = (event: AssistantMessageEvent): boolean => Boolean(event.text && event.text.trim());
  for (const item of section.items) {
    if (item.kind === "step") {
      for (const event of item.step.events) if (speaks(event)) return event.event_id;
    } else if (item.kind === "ungrouped") {
      for (const event of item.events) if (speaks(event)) return event.event_id;
    } else if (item.kind === "permission") {
      if (speaks(item.event)) return item.event.event_id;
    }
  }
  for (const event of section.trailing_reply) if (speaks(event)) return event.event_id;
  return null;
}

function buildRows(
  agentId: string,
  sections: SectionView[],
  toolResults: Map<string, ToolResultEvent>,
): RowDescriptor[] {
  const rows: RowDescriptor[] = [];
  for (const section of sections) {
    const userEvent = section.user_event;
    if (userEvent !== null && !isHiddenUserMessage(userEvent)) {
      rows.push({
        key: userEvent.event_id,
        estimate: ESTIMATED_USER_HEIGHT_PX,
        anchorEventId: userEvent.event_id,
        render: () => renderUserMessage(userEvent) as m.Vnode,
      });
    }

    const hasSteps = section.items.some((i) => i.kind === "step");
    if (hasSteps) {
      const key = `progress-${section.key}`;
      // The whole agent turn gets an outer container named after the event the
      // outline points at. Inside a progress block most of the agent's prose is
      // in a collapsed step and has no element of its own, so this container is
      // what the navigation rail actually scrolls to. The row's own id stays on
      // the block itself, where measureRows expects it.
      const turnAnchorId = agentTurnAnchorEventId(section);
      rows.push({
        key,
        estimate: ESTIMATED_PROGRESS_HEIGHT_PX,
        anchorEventId: userEvent?.event_id ?? null,
        render: () => {
          // The ROW's rendered root must carry the row key as its DOM id: the
          // engine caches measured heights under `element.id` and reads them back
          // under `row.key`, so a root with any other id leaves the row stuck on
          // its crude estimate and the geometry the scroll position derives from
          // goes badly wrong. When this row is wrapped, the wrapper IS the root,
          // so the key goes there and the turn container id moves inside.
          const block = m(ProgressBlock, {
            id: turnAnchorId === null ? key : agentTurnContainerId(turnAnchorId),
            key,
            items: section.items,
            trailing_reply: section.trailing_reply,
            toolResults,
            agentId,
          });
          // Keyed like every other row: these land in one children array, and
          // mithril requires all-or-none keys among siblings.
          return turnAnchorId === null ? block : m("div", { key, id: key, class: "agent-turn" }, block);
        },
      });
      continue;
    }

    // No steps this turn: render the body as plain chat -- prose and tool-call
    // blocks inline, the same as assistant messages outside a progress section.
    for (const item of section.items) {
      if (item.kind === "ungrouped") {
        // Work introduced by a sentence renders indented under it. The rows stay
        // one-per-message so the virtualized list still measures them individually;
        // only the indent marks the grouping (see work-grouping).
        const grouped = groupedWorkEventIds(item.events);
        for (const event of item.events) {
          const groupClass = grouped.has(event.event_id) ? GROUPED_WORK_CLASS : "";
          rows.push({
            key: event.event_id,
            estimate: ESTIMATED_ASSISTANT_HEIGHT_PX,
            anchorEventId: event.event_id,
            render: () => renderAssistantMessage(event, toolResults, agentId, groupClass),
          });
        }
      } else if (item.kind === "permission") {
        // A permission request lifted out of its step: rendered inline as an
        // always-visible card so the user can act on it without expanding a step.
        const permissionEvent = item.event;
        const resolutionsByRequestId = item.resolutionsByRequestId;
        const permKey = `perm-${permissionEvent.event_id}`;
        rows.push({
          key: permKey,
          estimate: ESTIMATED_ASSISTANT_HEIGHT_PX,
          anchorEventId: permissionEvent.event_id,
          // Pass the row key as the DOM id so the measured height is cached under
          // the same key the window math looks up (see renderPermissionItem).
          render: () => renderPermissionItem(permissionEvent, toolResults, agentId, resolutionsByRequestId, permKey),
        });
      } else if (item.kind === "chip") {
        const chipEvent = item.event;
        if (!isHiddenUserMessage(chipEvent)) {
          rows.push({
            key: chipEvent.event_id,
            estimate: ESTIMATED_USER_HEIGHT_PX,
            anchorEventId: chipEvent.event_id,
            render: () => renderUserMessage(chipEvent) as m.Vnode,
          });
        }
      }
    }
    for (const event of section.trailing_reply) {
      rows.push({
        key: event.event_id,
        estimate: ESTIMATED_ASSISTANT_HEIGHT_PX,
        anchorEventId: event.event_id,
        render: () => renderAssistantMessage(event, toolResults, agentId),
      });
    }
  }
  return rows;
}

/**
 * The full events -> virtualized rows pipeline shared by both conversation
 * views: hide the pre-login auth-error prefix, walk the transcript into turn
 * sections, then flatten into top-level rows. The structure and decoration --
 * which steps exist, their order, grouping, titles, summaries -- come purely
 * from the transcript walk.
 */
export function buildConversationRows(
  agentId: string,
  events: TranscriptEvent[],
  agentIsIdle: boolean,
): RowDescriptor[] {
  const toolResults = buildToolResultsWithSkillExpansions(events);
  const hiddenEventIds = computeAuthErrorHiddenEventIds(events);
  const visibleEvents = hiddenEventIds.size > 0 ? events.filter((e) => !hiddenEventIds.has(e.event_id)) : events;
  const sections = buildSections(visibleEvents, toolResults, agentIsIdle);
  return buildRows(agentId, sections, toolResults);
}

/**
 * Whether a subagent is still running, used in place of the parent agent's
 * server-derived `activity_state` (which doesn't apply to a subagent). Minimal
 * by design: the subagent is running while its last assistant turn has no
 * terminal stop_reason (it's mid-tool-use or hasn't stopped); once it stops
 * with `end_turn`/`stop_sequence` it's settled. Drives whether the subagent's
 * frontier step may show a spinner.
 */
export function isSubagentRunning(events: TranscriptEvent[]): boolean {
  for (let i = events.length - 1; i >= 0; i--) {
    const event = events[i];
    if (event.type === "assistant_message") {
      return event.stop_reason === null || event.stop_reason === "tool_use";
    }
  }
  return false;
}
