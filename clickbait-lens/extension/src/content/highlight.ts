import type { Signal } from "../shared/types";
import { findBodyContainer } from "./extract";

/**
 * Highlight the body sentences that contradict the headline.
 *
 * This is the payoff of the whole product — "claims something is like that, but
 * actually isn't" only lands when the user can see the sentence that hedges or
 * attributes what the headline stated flatly.
 */

export const HIGHLIGHT_CLASS = "clickbait-lens-highlight";
const STYLE_ID = "clickbait-lens-highlight-style";

const HIGHLIGHT_CSS = `
.${HIGHLIGHT_CLASS} {
  background: linear-gradient(transparent 55%, rgba(255, 196, 61, 0.55) 55%);
  border-bottom: 2px solid rgba(214, 130, 0, 0.85);
  cursor: help;
  scroll-margin-top: 96px;
}
.${HIGHLIGHT_CLASS}[data-cbl-active="true"] {
  background: rgba(255, 196, 61, 0.75);
  outline: 2px solid rgba(214, 130, 0, 0.9);
}
`;

function ensureStyle(): void {
  if (document.getElementById(STYLE_ID)) return;
  const style = document.createElement("style");
  style.id = STYLE_ID;
  style.textContent = HIGHLIGHT_CSS;
  document.head.appendChild(style);
}

function normalize(value: string): string {
  return value.replace(/\s+/g, " ").trim();
}

/** Body sentences called out by the signals, deduped, longest first. */
export function highlightTargets(signals: Signal[]): string[] {
  const seen = new Set<string>();
  const targets: string[] = [];
  for (const signal of signals) {
    for (const evidence of signal.evidence) {
      if (evidence.where !== "body") continue;
      const value = normalize(evidence.text);
      if (value.length < 25 || seen.has(value)) continue;
      seen.add(value);
      targets.push(value);
    }
  }
  return targets.sort((a, b) => b.length - a.length);
}

function textNodesUnder(root: Element): Text[] {
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
    acceptNode(node) {
      const parent = (node as Text).parentElement;
      if (!parent) return NodeFilter.FILTER_REJECT;
      if (parent.closest(`.${HIGHLIGHT_CLASS}, script, style, #clickbait-lens-root`)) {
        return NodeFilter.FILTER_REJECT;
      }
      return (node.textContent ?? "").trim().length > 0
        ? NodeFilter.FILTER_ACCEPT
        : NodeFilter.FILTER_REJECT;
    },
  });
  const nodes: Text[] = [];
  let current = walker.nextNode();
  while (current) {
    nodes.push(current as Text);
    current = walker.nextNode();
  }
  return nodes;
}

/**
 * Locate a normalized sentence inside a raw text node.
 *
 * The backend works on whitespace-normalized prose, but the DOM keeps the
 * source's line wrapping and indentation, so a plain `indexOf` misses almost
 * every multi-line paragraph. Build a normalized projection of the node, search
 * that, then map the offsets back to the original text.
 */
function findInTextNode(node: Text, target: string): { start: number; end: number } | null {
  const raw = node.textContent ?? "";
  let normalized = "";
  const offsets: number[] = [];
  let inWhitespace = false;

  for (let index = 0; index < raw.length; index += 1) {
    const char = raw[index]!;
    if (/\s/.test(char)) {
      if (!inWhitespace && normalized.length > 0) {
        normalized += " ";
        offsets.push(index);
      }
      inWhitespace = true;
    } else {
      normalized += char;
      offsets.push(index);
      inWhitespace = false;
    }
  }

  const found = normalized.indexOf(target);
  if (found === -1) return null;

  const start = offsets[found]!;
  const lastIndex = found + target.length - 1;
  const end = (offsets[lastIndex] ?? raw.length - 1) + 1;
  return { start, end };
}

function wrap(node: Text, start: number, length: number, label: string): HTMLElement | null {
  try {
    const range = document.createRange();
    range.setStart(node, start);
    range.setEnd(node, start + length);
    const mark = document.createElement("mark");
    mark.className = HIGHLIGHT_CLASS;
    mark.title = label;
    range.surroundContents(mark);
    return mark;
  } catch {
    // surroundContents throws when the range straddles element boundaries;
    // skipping is the right call — a partial highlight is worse than none.
    return null;
  }
}

/** Highlight one sentence, if it can be found. Returns the mark it created. */
export function highlightSentence(sentence: string): HTMLElement | null {
  const target = normalize(sentence);
  if (target.length < 25) return null;
  ensureStyle();

  const container = findBodyContainer() ?? document.body;
  if (!container) return null;

  for (const node of textNodesUnder(container)) {
    const match = findInTextNode(node, target);
    if (!match) continue;
    const mark = wrap(
      node,
      match.start,
      match.end - match.start,
      "Clickbait Lens: the headline overstates this",
    );
    if (mark) mark.dataset.cblSentence = target;
    return mark;
  }
  return null;
}

/** Apply highlights for every body sentence the signals call out. */
export function applyHighlights(signals: Signal[]): number {
  clearHighlights();
  let applied = 0;
  for (const target of highlightTargets(signals)) {
    if (highlightSentence(target)) applied += 1;
  }
  return applied;
}

export function clearHighlights(): void {
  document.querySelectorAll(`.${HIGHLIGHT_CLASS}`).forEach((mark) => {
    const parent = mark.parentNode;
    if (!parent) return;
    while (mark.firstChild) parent.insertBefore(mark.firstChild, mark);
    parent.removeChild(mark);
    parent.normalize();
  });
}

/**
 * Scroll to a sentence and flash it, highlighting it first if needed — so the
 * "jump to this sentence" affordance works even with auto-highlight turned off.
 */
export function focusHighlight(sentence: string): void {
  const normalized = normalize(sentence);
  const target =
    Array.from(document.querySelectorAll<HTMLElement>(`.${HIGHLIGHT_CLASS}`)).find(
      (mark) => mark.dataset.cblSentence === normalized,
    ) ?? highlightSentence(normalized);
  if (!target) return;
  target.scrollIntoView({ behavior: "smooth", block: "center" });
  target.dataset.cblActive = "true";
  window.setTimeout(() => {
    delete target.dataset.cblActive;
  }, 2000);
}
