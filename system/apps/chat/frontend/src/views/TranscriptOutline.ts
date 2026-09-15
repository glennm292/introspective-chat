/**
 * The navigation rail: one entry per message, down the left of the transcript.
 *
 * Three behaviours, in the order they matter:
 *
 * 1. **It lists the whole conversation**, not the loaded part -- the entries come
 *    from the backend outline (models/Outline), because the transcript only holds
 *    a window and a rail that gained and lost entries while scrolling would be
 *    useless for navigating.
 * 2. **It follows the transcript.** The highlighted entry is the newest message
 *    any part of which is on screen, updated as the user scrolls, and the rail
 *    scrolls itself to keep that entry visible.
 * 3. **Clicking an entry scrolls to that message**: the whole message at the
 *    BOTTOM of the viewport when it fits, otherwise its start at the TOP. A
 *    message outside the loaded window is jumped to first and then landed on
 *    precisely once its row exists.
 *
 * The highlight is written straight to the DOM rather than through a redraw: it
 * changes on scroll, and re-rendering the whole rail on every scroll frame would
 * be visible work for a one-class change.
 */

import m from "mithril";
import type { TranscriptScrollEngine } from "./transcript-scroll-engine";
import type { OutlineEntry } from "../models/Outline";
import { getOutline } from "../models/Outline";
import { agentTurnContainerId } from "./conversation-rows";

const RAIL_CLASS =
  "transcript-outline shrink-0 w-[236px] min-h-0 flex flex-col border-r bg-sidebar " + "max-[900px]:hidden";

const LIST_CLASS = "transcript-outline-list flex-1 min-h-0 overflow-y-auto py-1.5";

const HEAD_CLASS =
  "transcript-outline-head shrink-0 border-b px-3 py-2 text-(length:--font-size-helper) " +
  "uppercase tracking-wide text-faint";

const ENTRY_BASE =
  "transcript-outline-entry block w-full cursor-pointer rounded-[5px] px-2.5 py-1.5 text-left " +
  "text-(length:--font-size-helper) leading-snug transition-colors duration-(--dur-base)";

/** The indent lives on a wrapper, not on the button: a form control sizes to its
 *  content, so `w-full` is what makes an entry fill the rail -- and `w-full` plus a
 *  margin overflows the container and clips the text. */
const AGENT_INDENT_CLASS = "pl-1.5 pr-4";
const USER_INDENT_CLASS = "pl-5 pr-1.5";

/** Two lines, never three: enough to recognise a message, not enough to read it. */
const ENTRY_TEXT_CLASS = "transcript-outline-text line-clamp-2";

/** The rail leans each entry the way its message sits in the transcript -- the
 *  agent's flush left, the user's inset and tinted like their bubble -- so the
 *  shape of the conversation is readable before any word is. */
const AGENT_ENTRY_CLASS = "transcript-outline-entry--agent text-secondary hover:bg-fill-hover";
const USER_ENTRY_CLASS = "transcript-outline-entry--user bg-fill-subtle text-primary hover:bg-fill-hover";

const CURRENT_CLASS = "transcript-outline-entry--current";

/** How long to keep working on a jumped-to landing. The row has to be FETCHED
 *  first, and the engine keeps adjusting the scroll position for several frames
 *  after a jump (deferred landing, fills), so a one-shot scroll gets overwritten.
 *  We keep re-applying until the row stops moving, or until this runs out -- by
 *  which point the viewport is at least in the right region. */
const JUMP_SETTLE_MS = 4000;
/** Input kinds that mean the user has taken the transcript over themselves. */
const USER_TAKEOVER_EVENTS = ["wheel", "touchstart", "pointerdown", "keydown"] as const;
/** How long the rail stays where the user left it after they scroll it. */
const RAIL_USER_SCROLL_QUIET_MS = 1500;
/** Consecutive frames the row must already be in place before we stop. */
const JUMP_STABLE_FRAMES = 3;
/** Sub-pixel layout jitter should not count as "moved". */
const LANDING_TOLERANCE_PX = 2;

export interface TranscriptOutlineAttrs {
  agentId: string;
  engine: TranscriptScrollEngine;
  /** The transcript's scroll container, once ChatPanel has mounted it. */
  getScrollElement: () => HTMLElement | null;
}

/**
 * The element an entry scrolls to.
 *
 * Prefers the turn CONTAINER (conversation-rows wraps each agent turn in one named
 * after the same event the outline names it by). That matters because most of the
 * agent's prose renders inside a collapsed step and has no element of its own --
 * the container is the only thing in the page that stands for that reply. Falls
 * back to the message element, which is what a user message always has.
 */
function elementForEntry(entry: OutlineEntry): HTMLElement | null {
  return document.getElementById(agentTurnContainerId(entry.event_id)) ?? document.getElementById(entry.event_id);
}

/** One entry's extent in the transcript, in the scroller's content coordinates. */
interface EntrySpan {
  top: number;
  height: number;
}

/** The content-space offset of an element within `scroller`.
 *
 * Measured through the viewport rather than via offsetTop: offsetTop is relative
 * to the nearest POSITIONED ancestor, which is not the scroller, so arithmetic on
 * it is off by however far those two are apart.
 */
function contentTopOf(scroller: HTMLElement, element: HTMLElement, scrollerTop: number): number {
  return element.getBoundingClientRect().top - scrollerTop + scroller.scrollTop;
}

/**
 * How much of the transcript one entry stands for.
 *
 * An entry is not one row. An agent entry points at the FIRST speaking message of
 * a reply, which is frequently a single line ("On it.") -- landing that row alone
 * shows one line and leaves the actual reply below the fold. What the entry means
 * is the whole reply, so its span runs from its own row down to wherever the NEXT
 * entry begins. A user entry's span is just its message, which is the same rule
 * with the next entry immediately after it.
 *
 * Returns null when the entry's own row is not currently mounted.
 */
function entrySpan(scroller: HTMLElement, entries: readonly OutlineEntry[], index: number): EntrySpan | null {
  const row = elementForEntry(entries[index]);
  if (row === null) return null;
  const scrollerTop = scroller.getBoundingClientRect().top;
  const top = contentTopOf(scroller, row, scrollerTop);

  // The span ends where the next mounted entry starts. If none of the later
  // entries is mounted, this is the tail of the loaded content, so run to the end.
  let end = top + row.offsetHeight;
  let isBounded = false;
  for (let next = index + 1; next < entries.length; next++) {
    const nextRow = elementForEntry(entries[next]);
    if (nextRow === null) continue;
    end = contentTopOf(scroller, nextRow, scrollerTop);
    isBounded = true;
    break;
  }
  if (!isBounded) end = Math.max(end, scroller.scrollHeight);
  return { top, height: Math.max(row.offsetHeight, end - top) };
}

/** Where a span should sit: whole thing at the bottom if it fits in the viewport,
 *  else its start at the top. */
function landingScrollTop(scroller: HTMLElement, span: EntrySpan): number {
  const viewport = scroller.clientHeight;
  const fits = span.height <= viewport;
  return Math.max(0, fits ? span.top + span.height - viewport : span.top);
}

export function TranscriptOutline(): m.Component<TranscriptOutlineAttrs> {
  let listElement: HTMLElement | null = null;
  let boundScroller: HTMLElement | null = null;
  let boundHandler: (() => void) | null = null;
  let boundTakeover: (() => void) | null = null;
  let currentEventId: string | null = null;
  let isFramePending = false;
  /** Bumped whenever the user takes over the transcript, or a new jump starts.
   *  A converge loop that no longer owns this generation stops immediately. */
  let scrollGeneration = 0;
  /** Set while the user is scrolling the RAIL itself, so the highlight does not
   *  yank the list back out from under them while they browse it. */
  let railUserScrollUntilMs = 0;

  /** The newest entry whose message has any part on screen.
   *
   * Measured in content space off the viewport rect. The previous version did the
   * arithmetic on offsetTop, which is relative to the nearest positioned ancestor
   * rather than the scroller -- so every comparison was off by the distance
   * between them and the highlight landed on the wrong entry.
   */
  function computeCurrentEventId(entries: readonly OutlineEntry[], scroller: HTMLElement): string | null {
    const bottom = scroller.scrollTop + scroller.clientHeight;
    const scrollerTop = scroller.getBoundingClientRect().top;
    let current: string | null = null;
    for (const entry of entries) {
      const row = elementForEntry(entry);
      if (row === null) continue;
      if (contentTopOf(scroller, row, scrollerTop) < bottom) current = entry.event_id;
    }
    return current;
  }

  /** Move the highlight and keep it in view, without a redraw. */
  function applyHighlight(eventId: string | null): void {
    if (listElement === null || eventId === currentEventId) return;
    currentEventId = eventId;
    const entries = Array.from(listElement.querySelectorAll<HTMLElement>(".transcript-outline-entry"));
    let active: HTMLElement | null = null;
    for (const entry of entries) {
      const isActive = entry.dataset.eventId === eventId;
      entry.classList.toggle(CURRENT_CLASS, isActive);
      if (isActive) active = entry;
    }
    if (active === null) return;
    // Scrolling one pane auto-scrolls only the OTHER. While the user is scrolling
    // the rail itself, leave it where they put it rather than dragging it back to
    // follow the transcript.
    if (performance.now() < railUserScrollUntilMs) return;
    const top = active.offsetTop;
    const bottom = top + active.offsetHeight;
    if (top < listElement.scrollTop || bottom > listElement.scrollTop + listElement.clientHeight) {
      listElement.scrollTo({ top: Math.max(0, bottom - listElement.clientHeight + 12), behavior: "smooth" });
    }
  }

  function onTranscriptScroll(agentId: string, scroller: HTMLElement): void {
    if (isFramePending) return;
    isFramePending = true;
    requestAnimationFrame(() => {
      isFramePending = false;
      applyHighlight(computeCurrentEventId(getOutline(agentId), scroller));
    });
  }

  /** Re-bind the scroll listener when ChatPanel's container appears or changes. */
  function bindScroller(agentId: string, scroller: HTMLElement | null): void {
    if (scroller === boundScroller) return;
    unbindScroller();
    boundScroller = scroller;
    if (scroller === null) return;
    boundHandler = (): void => onTranscriptScroll(agentId, scroller);
    scroller.addEventListener("scroll", boundHandler, { passive: true });
    // Direct input means the user has taken the transcript over; a programmatic
    // scroll (ours or the engine's) raises no such event, so this never
    // self-cancels.
    boundTakeover = (): void => {
      scrollGeneration++;
    };
    for (const kind of USER_TAKEOVER_EVENTS) {
      scroller.addEventListener(kind, boundTakeover, { passive: true });
    }
    boundHandler();
  }

  function unbindScroller(): void {
    if (boundScroller !== null && boundHandler !== null) {
      boundScroller.removeEventListener("scroll", boundHandler);
    }
    if (boundScroller !== null && boundTakeover !== null) {
      for (const kind of USER_TAKEOVER_EVENTS) {
        boundScroller.removeEventListener(kind, boundTakeover);
      }
    }
    boundScroller = null;
    boundHandler = null;
    boundTakeover = null;
  }

  /**
   * Scroll `entry`'s message into place, converging rather than scrolling once.
   *
   * A single scrollTo cannot land this: the transcript is virtualized, so the act
   * of scrolling mounts and unmounts rows and resizes the spacers, which moves the
   * target after we arrived at where it used to be. Measured on a real transcript,
   * a one-shot landing finished ~400px off. So we re-measure and re-apply each
   * frame until the row has stayed put, or until the deadline.
   */
  function goToEntry(attrs: TranscriptOutlineAttrs, entry: OutlineEntry): void {
    const scroller = attrs.getScrollElement();
    if (scroller === null) return;

    // Not mounted: ask the engine to bring that region in. Most of the agent's
    // prose lives inside progress blocks that are themselves virtualized away, so
    // this is the common case, not the rare one. It must go through the engine --
    // the engine owns the viewport over unloaded regions and reverts an external
    // scrollTo into one, and scrolling there proportionally lands on whatever
    // message happens to be nearby, which reads as jumping to the wrong entry.
    if (elementForEntry(entry) === null) {
      attrs.engine.jumpToEventIndex(entry.index);
    }

    // A new jump supersedes any loop still running from a previous click.
    const generation = ++scrollGeneration;
    const deadline = performance.now() + JUMP_SETTLE_MS;
    let stableFrames = 0;
    const settle = (): void => {
      // The user is always in charge: the moment they scroll, wheel, touch or
      // key the transcript themselves, this stops. Without this the loop spends
      // its whole deadline re-pinning the transcript to the clicked message and
      // the chat simply refuses to scroll.
      if (generation !== scrollGeneration) return;
      const entries = getOutline(attrs.agentId);
      const index = entries.findIndex((candidate) => candidate.event_id === entry.event_id);
      const span = index < 0 ? null : entrySpan(scroller, entries, index);
      if (span !== null) {
        const target = landingScrollTop(scroller, span);
        if (Math.abs(scroller.scrollTop - target) <= LANDING_TOLERANCE_PX) {
          // Only stop once it has STAYED in place: the engine can still be
          // mid-adjustment on the first frame we agree with it.
          if (++stableFrames >= JUMP_STABLE_FRAMES) {
            applyHighlight(entry.event_id);
            return;
          }
        } else {
          stableFrames = 0;
          // Instant, not smooth: a smooth scroll re-issued every frame restarts
          // its own animation and never converges.
          scroller.scrollTo({ top: target, behavior: "auto" });
        }
        applyHighlight(entry.event_id);
      }
      if (performance.now() < deadline) requestAnimationFrame(settle);
    };
    requestAnimationFrame(settle);
  }

  return {
    oncreate(vnode) {
      bindScroller(vnode.attrs.agentId, vnode.attrs.getScrollElement());
    },
    onupdate(vnode) {
      bindScroller(vnode.attrs.agentId, vnode.attrs.getScrollElement());
    },
    onremove() {
      unbindScroller();
    },
    view(vnode) {
      const attrs = vnode.attrs;
      const entries = getOutline(attrs.agentId);
      if (entries.length === 0) return null;
      return m("nav", { class: RAIL_CLASS, "aria-label": "Conversation outline" }, [
        m("div", { class: HEAD_CLASS }, "This conversation"),
        m(
          "div",
          {
            class: LIST_CLASS,
            oncreate: (listVnode: m.VnodeDOM) => {
              listElement = listVnode.dom as HTMLElement;
            },
            onupdate: (listVnode: m.VnodeDOM) => {
              listElement = listVnode.dom as HTMLElement;
            },
            onwheel: () => {
              railUserScrollUntilMs = performance.now() + RAIL_USER_SCROLL_QUIET_MS;
            },
            ontouchstart: () => {
              railUserScrollUntilMs = performance.now() + RAIL_USER_SCROLL_QUIET_MS;
            },
          },
          entries.map((entry) =>
            m(
              "div",
              {
                key: entry.event_id,
                class: `py-[1px] ${entry.role === "user" ? USER_INDENT_CLASS : AGENT_INDENT_CLASS}`,
              },
              m(
                "button",
                {
                  type: "button",
                  "data-event-id": entry.event_id,
                  title: entry.text,
                  class:
                    `${ENTRY_BASE} ${entry.role === "user" ? USER_ENTRY_CLASS : AGENT_ENTRY_CLASS}` +
                    (entry.event_id === currentEventId ? ` ${CURRENT_CLASS}` : ""),
                  onclick: () => goToEntry(attrs, entry),
                },
                m("span", { class: ENTRY_TEXT_CLASS }, entry.text),
              ),
            ),
          ),
        ),
      ]);
    },
  };
}
