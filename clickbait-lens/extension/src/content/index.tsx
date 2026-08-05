import { StrictMode, useCallback, useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import { analyze, getSettings } from "../shared/api";
import type { Analysis } from "../shared/types";
import { extractPage } from "./extract";
import { applyHighlights, clearHighlights } from "./highlight";
import { Overlay } from "./Overlay";
import { OVERLAY_CSS } from "./styles";

const ROOT_ID = "clickbait-lens-root";

function App() {
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [error, setError] = useState<string | null>(null);

  const run = useCallback(async () => {
    const settings = await getSettings();
    if (!settings.enabled) return;

    const extract = extractPage();
    if (!extract.isArticle) {
      chrome.runtime?.sendMessage?.({ type: "analysis:none" }).catch(() => {});
      return;
    }

    try {
      const result = await analyze(extract);
      setAnalysis(result);
      setError(null);
      chrome.runtime?.sendMessage?.({ type: "analysis:ready", analysis: result }).catch(() => {});
      if (settings.autoHighlight) applyHighlights(result.signals);
      else clearHighlights();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause));
    }
  }, []);

  useEffect(() => {
    void run();
    const listener = (message: { type?: string }) => {
      if (message?.type === "analysis:rerun") void run();
    };
    chrome.runtime?.onMessage?.addListener(listener);
    return () => chrome.runtime?.onMessage?.removeListener(listener);
  }, [run]);

  // An error before the first successful analysis still deserves a badge, so
  // the user can see the backend is unreachable rather than nothing at all.
  if (!analysis) {
    if (!error) return null;
    return (
      <div className="root">
        <div className="panel" data-testid="cbl-panel">
          <div className="panel-head">
            <div>
              <h1>Clickbait Lens</h1>
              <p>Could not analyze this page</p>
            </div>
          </div>
          <p className="error" data-testid="cbl-error">
            {error}
          </p>
        </div>
      </div>
    );
  }

  return <Overlay analysis={analysis} error={error} onRefresh={run} />;
}

function mount(): void {
  if (document.getElementById(ROOT_ID)) return;
  const host = document.createElement("div");
  host.id = ROOT_ID;
  // Shadow DOM keeps the host page's CSS out of the overlay and vice versa.
  const shadow = host.attachShadow({ mode: "open" });
  const style = document.createElement("style");
  style.textContent = OVERLAY_CSS;
  const container = document.createElement("div");
  shadow.append(style, container);
  document.documentElement.appendChild(host);

  createRoot(container).render(
    <StrictMode>
      <App />
    </StrictMode>,
  );
}

mount();
