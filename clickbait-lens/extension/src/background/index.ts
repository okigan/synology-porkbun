/**
 * Service worker.
 *
 * Holds the last analysis per tab so the popup can render instantly, and keeps
 * the toolbar badge in step with the page's clickbait score.
 */

import type { Analysis } from "../shared/types";

const analyses = new Map<number, Analysis>();

const BADGE_COLORS: Record<string, string> = {
  clean: "#2f9e5f",
  low: "#7a9e2f",
  moderate: "#c98a00",
  high: "#c33a26",
};

function setBadge(tabId: number, analysis: Analysis | null): void {
  if (!analysis) {
    void chrome.action.setBadgeText({ tabId, text: "" });
    return;
  }
  void chrome.action.setBadgeText({ tabId, text: String(Math.round(analysis.clickbait_score)) });
  void chrome.action.setBadgeBackgroundColor({
    tabId,
    color: BADGE_COLORS[analysis.verdict] ?? "#5a6069",
  });
}

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  const tabId = sender.tab?.id;

  switch (message?.type) {
    case "analysis:ready":
      if (typeof tabId === "number") {
        analyses.set(tabId, message.analysis as Analysis);
        setBadge(tabId, message.analysis as Analysis);
      }
      sendResponse({ ok: true });
      return false;

    case "analysis:none":
      if (typeof tabId === "number") {
        analyses.delete(tabId);
        setBadge(tabId, null);
      }
      sendResponse({ ok: true });
      return false;

    case "analysis:get": {
      // The popup asks for the active tab's analysis; it has no sender.tab.
      const requested = (message as { tabId?: number }).tabId;
      const key = typeof requested === "number" ? requested : tabId;
      sendResponse({ analysis: typeof key === "number" ? (analyses.get(key) ?? null) : null });
      return false;
    }

    default:
      return false;
  }
});

chrome.tabs.onRemoved.addListener((tabId) => analyses.delete(tabId));

chrome.tabs.onUpdated.addListener((tabId, changeInfo) => {
  if (changeInfo.status === "loading") {
    analyses.delete(tabId);
    setBadge(tabId, null);
  }
});
