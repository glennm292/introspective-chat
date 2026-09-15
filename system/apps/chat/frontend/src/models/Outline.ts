/**
 * The conversation outline: one entry per message, for the navigation rail.
 *
 * Deliberately NOT derived from the loaded transcript window. The transcript
 * holds only a slice of a long conversation, so a rail built from it would gain
 * and lose entries as the user scrolls -- the opposite of a navigation aid. The
 * backend walks every event once and returns just the openings (see
 * imbue/chat/outline.py); the whole outline of a long session is tens of KB.
 *
 * Kept fresh by re-fetching when the transcript's newest event changes, which is
 * the cheapest signal that the conversation grew. A refetch in flight is never
 * duplicated, and a stale response never overwrites a newer one.
 */

import m from "mithril";
import { apiUrl } from "@imbue/workspace-ui/src/base-path";

export interface OutlineEntry {
  event_id: string;
  /** Global position in the transcript, so an entry outside the loaded window can
   *  still be jumped to. */
  index: number;
  role: "user" | "agent";
  /** The opening of the message. Already clipped by the backend; the rail clamps
   *  it visually to two lines. */
  text: string;
}

interface OutlineResponse {
  entries: OutlineEntry[];
  total: number;
}

interface OutlineState {
  entries: OutlineEntry[];
  /** Total events in the transcript -- the denominator for a jump fraction. */
  total: number;
  /** The newest event id this outline was built for -- the staleness check. */
  builtForEventId: string | null;
  isLoading: boolean;
  /** Monotonic per-agent fence, so a slow response cannot land on a newer one. */
  requestSeq: number;
  /** When the last fetch finished, for coalescing a streaming turn's growth. */
  lastFetchedAtMs: number;
}

/** A streaming turn appends events continuously. Refetching the whole outline on
 *  each one would walk the entire transcript server-side many times a second and
 *  redraw the chat just as often, so growth is coalesced into one refresh per
 *  window. The rail lagging a moment behind a live turn is invisible; the storm
 *  would not be. */
const REFRESH_COALESCE_MS = 3000;

const stateByAgentId = new Map<string, OutlineState>();

function stateFor(agentId: string): OutlineState {
  let state = stateByAgentId.get(agentId);
  if (state === undefined) {
    state = { entries: [], total: 0, builtForEventId: null, isLoading: false, requestSeq: 0, lastFetchedAtMs: 0 };
    stateByAgentId.set(agentId, state);
  }
  return state;
}

export function getOutline(agentId: string): readonly OutlineEntry[] {
  return stateFor(agentId).entries;
}

/** How many events the outline was built over -- the jump fraction's denominator. */
export function getOutlineTotal(agentId: string): number {
  return stateFor(agentId).total;
}

/**
 * Fetch the outline if it is missing or older than `newestEventId`.
 *
 * Cheap to call on every render: it returns immediately unless the conversation
 * has actually grown since the last fetch.
 */
export function ensureOutline(agentId: string, newestEventId: string | null): void {
  const state = stateFor(agentId);
  if (state.isLoading) return;
  if (state.builtForEventId !== null && state.builtForEventId === newestEventId) return;
  // Coalesce growth during a live turn (see REFRESH_COALESCE_MS). The FIRST load
  // is never delayed -- lastFetchedAtMs is 0 until one has landed.
  if (state.lastFetchedAtMs > 0 && performance.now() - state.lastFetchedAtMs < REFRESH_COALESCE_MS) return;

  state.isLoading = true;
  const seq = ++state.requestSeq;
  void m
    .request<OutlineResponse>({
      method: "GET",
      url: apiUrl("/api/agents/:agentId/outline"),
      params: { agentId },
    })
    .then((result) => {
      if (seq !== state.requestSeq) return; // superseded by a newer fetch
      const entries = result.entries ?? [];
      // Redraw only when the rail would actually look different: a refresh that
      // found nothing new must not repaint the chat underneath it.
      const isChanged =
        entries.length !== state.entries.length ||
        entries.some((entry, index) => entry.event_id !== state.entries[index]?.event_id);
      state.entries = entries;
      state.total = result.total ?? 0;
      state.builtForEventId = newestEventId;
      if (isChanged) m.redraw();
    })
    .catch(() => {
      // A rail that failed to load is a missing convenience, not a broken chat:
      // leave whatever entries we had and let the next growth retry.
      if (seq === state.requestSeq) state.builtForEventId = null;
    })
    .finally(() => {
      if (seq === state.requestSeq) {
        state.isLoading = false;
        state.lastFetchedAtMs = performance.now();
      }
    });
}

/** Drop an agent's outline (it switched away, or its transcript was reset). */
export function forgetOutline(agentId: string): void {
  stateByAgentId.delete(agentId);
}
