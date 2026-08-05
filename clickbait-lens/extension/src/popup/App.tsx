import { useCallback, useEffect, useState } from "react";
import { getSettings, saveSettings } from "../shared/api";
import { AuthorCard } from "../content/Overlay";
import { DEFAULT_SETTINGS, type Analysis, type Settings } from "../shared/types";

async function activeTabId(): Promise<number | undefined> {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  return tab?.id;
}

export function App() {
  const [settings, setSettings] = useState<Settings>(DEFAULT_SETTINGS);
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [health, setHealth] = useState<"checking" | "up" | "down">("checking");

  const refresh = useCallback(async () => {
    const tabId = await activeTabId();
    const response = await chrome.runtime.sendMessage({ type: "analysis:get", tabId });
    setAnalysis((response?.analysis as Analysis | null) ?? null);
  }, []);

  useEffect(() => {
    void (async () => {
      const loaded = await getSettings();
      setSettings(loaded);
      await refresh();
      try {
        const response = await fetch(`${loaded.apiBase}/healthz`);
        setHealth(response.ok ? "up" : "down");
      } catch {
        setHealth("down");
      }
    })();
  }, [refresh]);

  const update = async (patch: Partial<Settings>) => {
    setSettings(await saveSettings(patch));
  };

  const send = async (type: string) => {
    const tabId = await activeTabId();
    if (typeof tabId === "number") {
      await chrome.tabs.sendMessage(tabId, { type }).catch(() => {});
    }
  };

  return (
    <main>
      <header>
        <h1>Clickbait Lens</h1>
        <span className={`status ${health}`} data-testid="popup-health">
          {health === "up" ? "backend online" : health === "down" ? "backend offline" : "checking…"}
        </span>
      </header>

      {analysis ? (
        <section data-testid="popup-analysis">
          <div className="score">
            <span className={`dot ${analysis.verdict}`}>
              {Math.round(analysis.clickbait_score)}
            </span>
            <div>
              <strong>{analysis.title}</strong>
              <small>
                {analysis.signals.length} signal(s) · {analysis.claims.length} claim(s) ·{" "}
                {analysis.outlet_domain ?? "unknown outlet"}
              </small>
            </div>
          </div>
          {analysis.authors.map((author) => (
            <AuthorCard key={author.id} author={author} />
          ))}
          {analysis.authors.length === 0 && (
            <p className="empty">No byline detected on this page.</p>
          )}
        </section>
      ) : (
        <p className="empty" data-testid="popup-empty">
          No article analyzed on this tab yet. Open a news article and the overlay appears at the
          bottom right.
        </p>
      )}

      <section className="controls">
        <button onClick={() => send("overlay:toggle")}>Toggle overlay</button>
        <button
          onClick={async () => {
            await send("analysis:rerun");
            window.setTimeout(() => void refresh(), 900);
          }}
        >
          Re-analyze
        </button>
      </section>

      <section className="settings">
        <label>
          <span>API base URL</span>
          <input
            value={settings.apiBase}
            data-testid="popup-api-base"
            onChange={(event) => void update({ apiBase: event.target.value })}
          />
        </label>
        <label className="row">
          <input
            type="checkbox"
            checked={settings.enabled}
            onChange={(event) => void update({ enabled: event.target.checked })}
          />
          <span>Analyze pages automatically</span>
        </label>
        <label className="row">
          <input
            type="checkbox"
            checked={settings.autoHighlight}
            onChange={(event) => void update({ autoHighlight: event.target.checked })}
          />
          <span>Highlight contradicting sentences in the article</span>
        </label>
      </section>
    </main>
  );
}
