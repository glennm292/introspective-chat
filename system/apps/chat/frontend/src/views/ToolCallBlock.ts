/**
 * The tool-call block: two levels, always. The header says what the call DID
 * (`ran uv run pytest -q`, `read scripts/run.py` -- never the tool's name), and
 * the pane under it shows the RESULT, clipped to its opening lines until the
 * header is clicked, at which point it expands to the whole output in a
 * scrollable pane. One shared renderer for assistant tool calls
 * (views/message-renderers.ts) and collapsed system/hook chips
 * (views/user-message-display.ts). The markdown variant (fenced blocks wrapped
 * by src/markdown.ts) shares only the class NAMES; its look is the
 * `.markdown-content .tool-call-block` rules in style.css.
 *
 * The clipped preview is resident on the event (`output_preview`); only the full
 * output is fetched on expand. So a collapsed transcript renders its results with
 * no requests at all, and the payload-free wire contract still holds for
 * everything past those first few lines.
 *
 * Expansion is deliberately a DOM class (`tool-call-block--expanded`) toggled
 * on the real element rather than component state: the open state then
 * survives memoized redraws (StableAssistantMessage skips re-rendering, and a
 * re-render would reset vnode state). The children react to it through
 * `group-[.tool-call-block--expanded]/tool:*` variants, so the whole state
 * machine still lives in the markup. A caller that also passes `expansionKey`
 * gets persistence across full unmounts too (virtualization evicting the row):
 * the toggle is recorded in the session-scoped expansion store and a fresh
 * mount renders back in the recorded state.
 */

import m from "mithril";
import { isBlockExpanded, setBlockExpanded } from "./expansion-state";

/** The class names are bare markers (markdown.ts drives the same state class;
 *  the inspector reads them); the utilities beside them carry the look. */
const BLOCK_CLASS = "tool-call-block group/tool overflow-hidden rounded-md border bg-sidebar";

const HEADER_CLASS =
  "tool-call-header flex cursor-pointer items-center gap-1.5 px-2.5 py-[3px] " +
  "text-(length:--font-size-body) select-none transition-colors duration-(--dur-base) hover:bg-fill-hover";

/** The verb is prose about what happened, so it is set in the reading face at full
 *  contrast -- it is the part a person scans. */
const HEADER_VERB_CLASS = "tool-call-verb flex-none text-primary";

/** The target is the machine's own text -- a command, a path -- so it keeps the
 *  monospace face and the quieter colour that marks it as quoted material. */
const HEADER_TARGET_CLASS = "tool-call-target truncate font-mono text-secondary";

// text-[10px]: icon glyph (the chevron), sized independently of the text scale.
const CHEVRON_CLASS =
  "tool-call-chevron inline-block text-[10px] transition-transform duration-(--dur-base) " +
  "group-[.tool-call-block--expanded]/tool:rotate-90";

const DETAILS_CLASS = "tool-call-details hidden border-t group-[.tool-call-block--expanded]/tool:block";

const PANE_CLASS = "px-3 py-2";

/** The always-visible result pane: a few lines, clipped, with the overflow faded
 *  out so it reads as "there is more" rather than as a sentence cut in half. */
const PREVIEW_CLASS =
  "tool-call-preview relative overflow-hidden border-t px-3 py-1.5 " +
  "group-[.tool-call-block--expanded]/tool:hidden";

/** The fade over the clipped preview's last line. Purely decorative, so it is
 *  pointer-transparent and disappears the moment the block expands. */
const PREVIEW_FADE_CLASS =
  "pointer-events-none absolute inset-x-0 bottom-0 h-[1.6em] bg-linear-to-b from-transparent to-sidebar";

/** The expanded output pane: the whole output, scrollable rather than unbounded,
 *  so one enormous result cannot push the rest of the conversation off screen. */
const SCROLL_PANE_CLASS = "max-h-[22rem] overflow-y-auto";

/** A pane's deferred-payload state: events are payload-free on the wire, so a
 *  pane may still be fetching or reference a payload the backend no longer holds. */
export type PayloadState = "loaded" | "loading" | "unavailable";

/** One monospace pane of the expanded body. Color inherits, so the error tint
 *  sits on the pane and reaches the code text. */
function renderPane(marker: string, text: string, extra = ""): m.Vnode {
  return m("div", { class: `${marker} ${PANE_CLASS} ${extra}`.trim() }, [
    m(
      "pre",
      { class: "overflow-x-auto" },
      m(
        "code",
        { class: "font-mono text-(length:--font-size-helper) leading-normal break-all whitespace-pre-wrap" },
        text,
      ),
    ),
  ]);
}

/** A pane that isn't loaded yet renders as a quiet italic note instead of code. */
function renderPaneNote(marker: string, state: "loading" | "unavailable", extra = ""): m.Vnode {
  return m(
    "div",
    {
      class:
        `${marker} tool-call-payload-note ${PANE_CLASS} text-(length:--font-size-helper) italic text-secondary ${extra}`.trim(),
    },
    state === "loading" ? "Loading…" : "No longer available",
  );
}

/** One section of the expanded body, or nothing (loaded with no text). */
function renderSection(marker: string, text: string, state: PayloadState, extra = ""): m.Vnode | null {
  if (state !== "loaded") return renderPaneNote(marker, state, extra);
  return text ? renderPane(marker, text, extra) : null;
}

/** The clipped result shown under a collapsed header.
 *
 * Deliberately a separate element from the expanded output pane rather than the
 * same one restyled: the two show different TEXT (a resident preview vs. the
 * fetched whole), so collapsing never has to un-fetch anything and expanding
 * never blanks the pane while a request is in flight.
 */
function renderPreview(previewText: string, isError: boolean, lineCount: number): m.Vnode {
  return m("div", { class: `${PREVIEW_CLASS} ${isError ? "text-danger" : ""}`.trim() }, [
    m(
      "pre",
      { class: "overflow-hidden" },
      m(
        "code",
        { class: "font-mono text-(length:--font-size-helper) leading-normal break-all whitespace-pre-wrap" },
        previewText,
      ),
    ),
    lineCount >= PREVIEW_FADE_MIN_LINES ? m("div", { class: PREVIEW_FADE_CLASS }) : null,
  ]);
}

/** Below this many preview lines the pane is plainly the whole (short) result, so
 *  fading its last line would promise more output that does not exist. */
const PREVIEW_FADE_MIN_LINES = 3;

/**
 * The collapsible block. `extra` is appended to the root's class string --
 * margins and width belong to the call site (the assistant flow gives it the
 * markdown rhythm, the system chip caps its width instead).
 */
export function renderToolBlock(options: {
  /** The header's prose half: what the call did ("ran", "read", "edited"). */
  headerVerb: string;
  /** The header's machine half: the command or path it acted on. May be empty. */
  headerTarget?: string;
  inputText?: string;
  outputText?: string;
  isError?: boolean;
  extra?: string;
  /** Stable identity in the expansion store (e.g. the tool call's id), so the
   *  open state survives the row unmounting and remounting (virtualization)
   *  or re-rendering (streaming). Omitted: open state is this-mount-only. */
  expansionKey?: string;
  /** A failed call's stamped first line -- the fallback glance for a failure that
   *  produced no preview at all (a hook refusal, an empty output). When a preview
   *  exists it already leads with this line, so this is not rendered as well. */
  errorSnippet?: string;
  /** The resident opening lines of the result, shown under the collapsed header.
   *  This is the block's second level: what came back, without a fetch. */
  previewText?: string;
  /** The agent's own stated reason for the call, rendered above the block. Absent
   *  for the many tools that record no reason -- never a guess. */
  reasonText?: string;
  /** Deferred-payload states; default "loaded" (the text is already in hand). */
  inputState?: PayloadState;
  outputState?: PayloadState;
  /** Called when the header toggles the block open -- the hook for kicking off
   *  on-demand payload fetches. */
  onExpand?: () => void;
}): m.Vnode {
  const {
    headerVerb,
    headerTarget = "",
    inputText = "",
    outputText = "",
    isError = false,
    extra = "",
    expansionKey,
    errorSnippet,
    previewText = "",
    reasonText,
    inputState = "loaded",
    outputState = "loaded",
    onExpand,
  } = options;
  const startExpanded = expansionKey !== undefined && isBlockExpanded(expansionKey);
  const inputSection = renderSection("tool-call-input", inputText, inputState);
  const outputSection = renderSection(
    isError ? "tool-call-output tool-call-output--error" : "tool-call-output",
    outputText,
    outputState,
    // The hairline between the panes exists exactly when both do --
    // resolved here instead of by a sibling-combinator rule.
    `${inputSection ? "border-t border-subtle " : ""}${isError ? "text-danger" : ""}`.trim(),
  );
  const previewLineCount = previewText ? previewText.split("\n").length : 0;
  // The error snippet is a fallback, not a second copy: a preview already opens with
  // that same first line, so showing both would print the failure twice.
  const errorLine = isError && errorSnippet && !previewText ? errorSnippet : "";
  const block = m(
    "div",
    { class: `${BLOCK_CLASS}${startExpanded ? " tool-call-block--expanded" : ""} ${extra}`.trim() },
    [
      m(
        "div",
        {
          class: HEADER_CLASS,
          onclick(e: Event) {
            const block = (e.currentTarget as HTMLElement).parentElement;
            if (block) {
              // Toggle the DOM directly (memoized wrappers skip re-patching)
              // AND record it so a fresh mount renders in the same state.
              const isNowExpanded = block.classList.toggle("tool-call-block--expanded");
              if (expansionKey !== undefined) {
                setBlockExpanded(expansionKey, isNowExpanded);
              }
              if (isNowExpanded) {
                onExpand?.();
              }
            }
          },
        },
        [
          m("span", { class: CHEVRON_CLASS }, "▸"),
          m("span", { class: HEADER_VERB_CLASS }, headerVerb),
          headerTarget ? m("span", { class: HEADER_TARGET_CLASS }, headerTarget) : null,
        ],
      ),
      // Level two, always visible: what came back. Resident, so no fetch.
      previewText ? renderPreview(previewText, isError, previewLineCount) : null,
      // A failure that produced no preview at all still has to be glanceable.
      errorLine
        ? m(
            "div",
            {
              class:
                "tool-call-error-snippet border-t px-2.5 py-[3px] font-mono text-(length:--font-size-helper) text-danger",
            },
            errorLine,
          )
        : null,
      inputSection || outputSection
        ? m("div", { class: `${DETAILS_CLASS} ${SCROLL_PANE_CLASS}` }, [inputSection, outputSection])
        : null,
    ],
  );
  // The stated reason sits ABOVE the block, not inside it: it explains why the call
  // was made, which is context for the whole block rather than part of its result.
  if (!reasonText) return block;
  return m("div", { class: "tool-call-with-reason" }, [
    m("div", { class: "tool-call-reason mb-[2px] flex gap-1.5 text-(length:--font-size-helper) text-secondary" }, [
      m("span", { class: "text-faint select-none" }, "↳"),
      m("span", reasonText),
    ]),
    block,
  ]);
}
