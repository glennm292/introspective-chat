/**
 * "Agent Overview": what this conversation spent its time on.
 *
 * A table of model calls and each kind of tool call, with how many there were and
 * how long they took. Ordered by time rather than by name or count, because the
 * question a summary answers is where the time went -- a hundred fast reads matter
 * less than a handful of slow commands.
 *
 * Every figure is derived from timestamps in the transcript, so the panel says so
 * rather than presenting wall-clock gaps as if they were metered. Where calls
 * could not be timed (no result yet, a missing timestamp) the count still shows
 * and the time is marked, never silently rolled in as zero.
 */

import m from "mithril";
import { MODAL_TITLE_CLASS, Modal } from "@imbue/workspace-ui/src/components/Modal";
import { Button } from "@imbue/workspace-ui/src/components/Button";
import { hoverTooltipAttrs } from "@imbue/workspace-ui/src/components/hoverTooltip";
import type { AgentOverview, ToolUsage } from "../models/Overview";
import {
  averageSeconds,
  closeAgentOverview,
  formatDuration,
  formatTokens,
  getOverviewState,
} from "../models/Overview";

const TABLE_CLASS = "agent-overview-table w-full border-collapse text-(length:--font-size-body)";
const HEAD_CELL_CLASS =
  "agent-overview-head px-2 py-1.5 text-left text-(length:--font-size-helper) font-medium text-faint " +
  "uppercase tracking-wide border-b";
const NUM_HEAD_CLASS = `${HEAD_CELL_CLASS} text-right`;
const CELL_CLASS = "agent-overview-cell px-2 py-1.5 border-b border-subtle text-primary";
const NUM_CELL_CLASS = `${CELL_CLASS} text-right tabular-nums`;
const MUTED_NUM_CELL_CLASS = `${NUM_CELL_CLASS} text-secondary`;
const TOTAL_ROW_CLASS = "agent-overview-total font-medium";
/** The circled ? beside a column that needs a word of explanation. Sized to the
 *  header it sits in, and dotted-outlined so it reads as "ask me" rather than as
 *  data. */
const HINT_CLASS =
  "agent-overview-hint ml-1 inline-flex h-[13px] w-[13px] cursor-help items-center justify-center " +
  "rounded-full border border-current align-[0.05em] text-[9px] leading-none font-normal normal-case";

/** What the Total column is actually measuring. In a tooltip because it qualifies
 *  one column rather than the panel, and a reader who already knows should not
 *  have to scroll past it. */
const TIMING_EXPLANATION =
  "Measured between the conversation's own recorded timestamps: a model call from the previous event " +
  "to its reply, a tool call from where it was issued to its result. Wall-clock, so anything else that " +
  "happened in the same gap is counted with it.";

/** A row: label, count, total time, and the average that makes the total legible. */
function renderRow(label: string, callCount: number, totalSeconds: number, timedCallCount: number): m.Vnode {
  const average = averageSeconds(totalSeconds, timedCallCount);
  // A count of calls we could not time is worth saying: it explains a total that
  // looks low for the number of calls beside it.
  const untimed = callCount - timedCallCount;
  return m("tr", { key: label }, [
    m("td", { class: CELL_CLASS }, [
      label,
      untimed > 0
        ? m(
            "span",
            { class: "agent-overview-untimed ml-1.5 text-(length:--font-size-helper) text-faint" },
            `(${untimed} untimed)`,
          )
        : null,
    ]),
    m("td", { class: NUM_CELL_CLASS }, String(callCount)),
    m("td", { class: NUM_CELL_CLASS }, formatDuration(totalSeconds)),
    m("td", { class: MUTED_NUM_CELL_CLASS }, average === null ? "—" : formatDuration(average)),
  ]);
}

function renderTable(overview: AgentOverview): m.Vnode {
  const rows: m.Vnode[] = [
    renderRow("Model calls", overview.llm_call_count, overview.llm_total_seconds, overview.llm_timed_call_count),
  ];
  for (const tool of overview.tools as ToolUsage[]) {
    rows.push(renderRow(tool.tool_name, tool.call_count, tool.total_seconds, tool.timed_call_count));
  }
  return m("table", { class: TABLE_CLASS }, [
    m(
      "thead",
      m("tr", [
        m("th", { class: HEAD_CELL_CLASS }, "Activity"),
        m("th", { class: NUM_HEAD_CLASS }, "Calls"),
        m("th", { class: NUM_HEAD_CLASS }, [
          "Total",
          m(
            "span",
            { class: HINT_CLASS, "aria-label": TIMING_EXPLANATION, ...hoverTooltipAttrs(TIMING_EXPLANATION) },
            "?",
          ),
        ]),
        m("th", { class: NUM_HEAD_CLASS }, "Average"),
      ]),
    ),
    m("tbody", rows),
    m(
      "tfoot",
      m("tr", { class: TOTAL_ROW_CLASS }, [
        m("td", { class: CELL_CLASS }, "All tool calls"),
        m("td", { class: NUM_CELL_CLASS }, String(overview.tool_call_count)),
        m("td", { class: NUM_CELL_CLASS }, formatDuration(overview.tool_total_seconds)),
        m("td", { class: MUTED_NUM_CELL_CLASS }, ""),
      ]),
    ),
  ]);
}

/**
 * Tokens: one row, three figures.
 *
 * Kept out of the activity table because only model calls use tokens at all -- a
 * tool's output is charged to whichever model call reads it next -- so every tool
 * row there would be a dash.
 *
 * Cache WRITES are counted under Input: the model read those tokens for the first
 * time as well as storing them, so they are new traffic rather than a saving.
 * Cached is what came back out of the cache instead of being read afresh, which is
 * why the two are worth seeing side by side.
 */
function renderTokenTable(overview: AgentOverview): m.Vnode {
  // mb-4: the last row's rule would otherwise sit directly on the Close button.
  return m("table", { class: `${TABLE_CLASS} agent-overview-tokens mt-4 mb-4` }, [
    // The label sits in the data row, in the same first column the activity table
    // labels its rows in, so the two tables read as one grid rather than two.
    m(
      "thead",
      m("tr", [
        m("th", { class: HEAD_CELL_CLASS }, ""),
        m("th", { class: NUM_HEAD_CLASS }, "Input"),
        m("th", { class: NUM_HEAD_CLASS }, "Cached"),
        m("th", { class: NUM_HEAD_CLASS }, "Output"),
      ]),
    ),
    m(
      "tbody",
      m("tr", [
        m("td", { class: CELL_CLASS }, "Tokens"),
        m("td", { class: NUM_CELL_CLASS }, formatTokens(overview.llm_input_tokens + overview.llm_cache_write_tokens)),
        m("td", { class: NUM_CELL_CLASS }, formatTokens(overview.llm_cache_read_tokens)),
        m("td", { class: NUM_CELL_CLASS }, formatTokens(overview.llm_output_tokens)),
      ]),
    ),
  ]);
}

function renderBody(): m.Children {
  const state = getOverviewState();
  if (state.kind === "loading") {
    return m("p", { class: "agent-overview-loading text-secondary" }, "Reading this conversation…");
  }
  if (state.kind === "failed") {
    return m("p", { class: "agent-overview-error text-danger" }, state.message);
  }
  if (state.kind !== "loaded") return null;
  const overview = state.overview;
  if (overview.llm_call_count === 0 && overview.tool_call_count === 0) {
    return m("p", { class: "agent-overview-empty text-secondary" }, "Nothing has happened in this conversation yet.");
  }
  return [renderTable(overview), renderTokenTable(overview)];
}

export function AgentOverviewModal(): m.Component {
  return {
    view() {
      if (getOverviewState().kind === "closed") return null;
      return m(
        Modal,
        {
          onDismiss: closeAgentOverview,
          onEscape: closeAgentOverview,
          width: 520,
          card: { role: "dialog", "aria-modal": "true", "aria-label": "Agent Overview" },
          // No icon: the shared set has no glyph that means "summary", and a
          // near-miss (a box, a star) would say something untrue about the panel.
          header: [m("h3", { class: MODAL_TITLE_CLASS }, "Agent Overview")],
          actions: [
            m(
              Button,
              {
                variant: "primary",
                onclick: closeAgentOverview,
                oncreate: (vnode) => {
                  (vnode.dom as HTMLButtonElement).focus();
                },
              },
              "Close",
            ),
          ],
        },
        renderBody(),
      );
    },
  };
}
