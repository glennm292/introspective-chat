/**
 * The agent overview: how many model and tool calls this conversation made, and
 * how long they took.
 *
 * Fetched rather than derived from the loaded transcript, for the same reason the
 * outline is: the transcript holds only a window, and a summary of a slice would
 * quietly under-report. The backend walks every event once (imbue/chat/overview.py).
 *
 * Fetched on open rather than kept fresh: a summary read while the agent works is
 * a snapshot by nature, and re-polling it would walk the whole transcript on a
 * timer for a panel nobody is looking at.
 */

import m from "mithril";
import { apiUrl } from "@imbue/workspace-ui/src/base-path";

export interface ToolUsage {
  tool_name: string;
  call_count: number;
  total_seconds: number;
  /** How many of those calls had both timestamps, so the time is measured rather
   *  than assumed. Fewer than call_count means some calls could not be timed. */
  timed_call_count: number;
}

export interface AgentOverview {
  llm_call_count: number;
  llm_total_seconds: number;
  llm_timed_call_count: number;
  /** Tokens belong to model calls alone: a tool's output is charged to whichever
   *  model call reads it next, so tool kinds report none. */
  llm_output_tokens: number;
  llm_input_tokens: number;
  llm_cache_read_tokens: number;
  llm_cache_write_tokens: number;
  tools: ToolUsage[];
  tool_call_count: number;
  tool_total_seconds: number;
  /** Gaps discarded as idle waiting rather than counted as work. */
  skipped_gap_count: number;
}

export type OverviewState =
  | { kind: "closed" }
  | { kind: "loading"; agentId: string }
  | { kind: "loaded"; agentId: string; overview: AgentOverview }
  | { kind: "failed"; agentId: string; message: string };

let state: OverviewState = { kind: "closed" };
let requestSeq = 0;

export function getOverviewState(): OverviewState {
  return state;
}

export function closeAgentOverview(): void {
  state = { kind: "closed" };
  requestSeq += 1; // a response still in flight no longer applies
}

/** Open the panel for `agentId` and fetch its figures. */
export function openAgentOverview(agentId: string): void {
  state = { kind: "loading", agentId };
  const seq = ++requestSeq;
  void m
    .request<AgentOverview>({
      method: "GET",
      url: apiUrl("/api/agents/:agentId/overview"),
      params: { agentId },
    })
    .then((overview) => {
      if (seq !== requestSeq) return;
      state = { kind: "loaded", agentId, overview };
      m.redraw();
    })
    .catch((error: unknown) => {
      if (seq !== requestSeq) return;
      state = {
        kind: "failed",
        agentId,
        message: error instanceof Error ? error.message : "Could not read this conversation's activity.",
      };
      m.redraw();
    });
}

/**
 * A duration as a person would say it.
 *
 * Coarse on purpose: the panel answers "where did the time go", and a total of
 * "1h 41m" says that better than 6,073.412 seconds. Sub-second values keep
 * milliseconds, because that is the range where a tool call being fast is the
 * interesting fact about it.
 */
export function formatDuration(totalSeconds: number): string {
  if (!Number.isFinite(totalSeconds) || totalSeconds <= 0) return "—";
  if (totalSeconds < 1) return `${Math.round(totalSeconds * 1000)} ms`;
  if (totalSeconds < 60) return `${totalSeconds < 10 ? totalSeconds.toFixed(1) : Math.round(totalSeconds)} s`;
  const minutes = Math.floor(totalSeconds / 60);
  if (minutes < 60) return `${minutes}m ${Math.round(totalSeconds % 60)}s`;
  return `${Math.floor(minutes / 60)}h ${minutes % 60}m`;
}

/** An average per call, or null when nothing was timed. */
export function averageSeconds(totalSeconds: number, timedCallCount: number): number | null {
  return timedCallCount > 0 ? totalSeconds / timedCallCount : null;
}

/**
 * A token count at a glance: 1.2M, 45.3k, 812.
 *
 * Rounded because the panel compares magnitudes -- whether a figure is thousands
 * or millions is the point, and the exact digit never is.
 */
export function formatTokens(count: number): string {
  if (!Number.isFinite(count) || count <= 0) return "—";
  if (count >= 1_000_000) return `${(count / 1_000_000).toFixed(1)}M`;
  if (count >= 1_000) return `${(count / 1_000).toFixed(1)}k`;
  return String(count);
}
