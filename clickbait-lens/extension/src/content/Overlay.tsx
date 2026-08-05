import { useCallback, useEffect, useMemo, useState } from "react";
import { setResolution, verifyClaim } from "../shared/api";
import type { Analysis, Author, Claim, Resolution, Signal, Verification } from "../shared/types";
import { focusHighlight } from "./highlight";

const RESOLUTION_LABEL: Record<Resolution, string> = {
  unresolved: "unresolved",
  true: "came true",
  mostly_true: "mostly true",
  mixed: "mixed",
  mostly_false: "mostly false",
  false: "did not happen",
  unverifiable: "unverifiable",
};

const TRUST_COLORS: [number, string][] = [
  [80, "#7ddc9a"],
  [62, "#b9e08a"],
  [45, "#ffc43d"],
  [28, "#ffa06b"],
  [0, "#ff7b6b"],
];

function trustColor(index: number): string {
  return TRUST_COLORS.find(([threshold]) => index >= threshold)?.[1] ?? "#ff7b6b";
}

export function ScoreBadge({
  analysis,
  onClick,
}: {
  analysis: Analysis;
  onClick: () => void;
}) {
  const author = analysis.authors[0];
  const subtitle = author
    ? `${author.display_name} · trust ${Math.round(author.trust.trust_index)}`
    : (analysis.outlet_name ?? "No byline found");
  return (
    <button className="badge" onClick={onClick} data-testid="cbl-badge">
      <span className={`dot ${analysis.verdict}`} data-testid="cbl-score">
        {Math.round(analysis.clickbait_score)}
      </span>
      <span className="badge-label">
        <strong>Clickbait Lens</strong>
        <span data-testid="cbl-badge-subtitle">{subtitle}</span>
      </span>
    </button>
  );
}

function SignalCard({ signal }: { signal: Signal }) {
  const bodyEvidence = signal.evidence.filter((e) => e.where === "body");
  const headlineEvidence = signal.evidence.filter((e) => e.where === "headline");
  return (
    <div className="signal" data-testid="cbl-signal" data-signal-id={signal.id}>
      <div className="signal-head">
        <strong>{signal.label}</strong>
        <span className={`sev ${signal.severity >= 0.6 ? "hot" : ""}`}>
          {Math.round(signal.severity * 100)}%
        </span>
      </div>
      <p>{signal.explanation}</p>
      {headlineEvidence.length > 0 && (
        <div className="chips" style={{ marginTop: 6 }}>
          {headlineEvidence.slice(0, 6).map((evidence, index) => (
            <span className="chip" key={index}>
              {evidence.text}
              {evidence.note ? ` — ${evidence.note}` : ""}
            </span>
          ))}
        </div>
      )}
      {bodyEvidence.map((evidence, index) => (
        <button
          type="button"
          className="quote"
          key={index}
          data-testid="cbl-evidence"
          onClick={() => focusHighlight(evidence.text)}
          title="Jump to this sentence in the article"
        >
          “{evidence.text}”
          <small>{evidence.note || "in the article body"} · click to jump</small>
        </button>
      ))}
    </div>
  );
}

function EvidenceList({ verification }: { verification: Verification }) {
  return (
    <div className="verdict" data-testid="cbl-verification">
      <h4>
        Suggested: {RESOLUTION_LABEL[verification.suggested_resolution]} (
        {Math.round(verification.confidence * 100)}% confidence)
      </h4>
      <p>{verification.rationale}</p>
      <ul className="evidence">
        {verification.evidence.slice(0, 5).map((item, index) => (
          <li key={index}>
            <a href={item.url} target="_blank" rel="noreferrer noopener">
              {item.title || item.url}
            </a>{" "}
            <span className={`stance ${item.stance > 0 ? "pos" : item.stance < 0 ? "neg" : ""}`}>
              {item.stance > 0 ? "supports" : item.stance < 0 ? "refutes" : "neutral"}
            </span>
            <span className="why">
              {item.source} · {item.stance_reason}
            </span>
          </li>
        ))}
        {verification.evidence.length === 0 && <li>No evidence returned for this query.</li>}
      </ul>
      <p style={{ marginTop: 6 }}>
        <a href={verification.search_url} target="_blank" rel="noreferrer noopener">
          Check the search yourself →
        </a>
      </p>
    </div>
  );
}

function ClaimCard({ claim, onChanged }: { claim: Claim; onChanged: () => void }) {
  const [verification, setVerification] = useState<Verification | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [resolution, setLocalResolution] = useState<Resolution>(claim.resolution);

  const run = async (fn: () => Promise<void>) => {
    setBusy(true);
    setError(null);
    try {
      await fn();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause));
    } finally {
      setBusy(false);
    }
  };

  if (claim.id === null) return null;
  const claimId = claim.id;

  return (
    <div className="claim" data-testid="cbl-claim" data-claim-id={claimId}>
      <p className="claim-text">{claim.text}</p>
      <div className="chips">
        <span className={`chip ${claim.kind}`}>{claim.kind.replace("_", " ")}</span>
        {claim.horizon_text && <span className="chip">by {claim.horizon_text}</span>}
        <span className={`chip ${resolution}`} data-testid="cbl-claim-resolution">
          {RESOLUTION_LABEL[resolution]}
        </span>
      </div>
      <div className="actions">
        <button
          className="action primary"
          data-testid="cbl-verify"
          disabled={busy}
          onClick={() =>
            run(async () => {
              setVerification(await verifyClaim(claimId, false));
            })
          }
        >
          {busy ? "Searching…" : "Check the record"}
        </button>
        {verification && verification.suggested_resolution !== "unresolved" && (
          <button
            className="action"
            data-testid="cbl-accept"
            disabled={busy}
            onClick={() =>
              run(async () => {
                await setResolution(
                  claimId,
                  verification.suggested_resolution,
                  verification.rationale,
                );
                setLocalResolution(verification.suggested_resolution);
                onChanged();
              })
            }
          >
            Accept verdict
          </button>
        )}
        <button
          className="action"
          data-testid="cbl-mark-true"
          disabled={busy}
          onClick={() =>
            run(async () => {
              await setResolution(claimId, "true");
              setLocalResolution("true");
              onChanged();
            })
          }
        >
          Mark true
        </button>
        <button
          className="action"
          data-testid="cbl-mark-false"
          disabled={busy}
          onClick={() =>
            run(async () => {
              await setResolution(claimId, "false");
              setLocalResolution("false");
              onChanged();
            })
          }
        >
          Mark false
        </button>
      </div>
      {error && <p className="error">{error}</p>}
      {verification && <EvidenceList verification={verification} />}
    </div>
  );
}

export function AuthorCard({ author }: { author: Author }) {
  const { trust } = author;
  return (
    <div className="author" data-testid="cbl-author" data-author-id={author.id}>
      <div className="author-head">
        <span
          className="trust-ring"
          style={{ background: trustColor(trust.trust_index) }}
          data-testid="cbl-trust-index"
        >
          {Math.round(trust.trust_index)}
        </span>
        <div>
          <h3>{author.display_name}</h3>
          <span>
            {author.primary_outlet_domain ?? "unknown outlet"} · {trust.grade} ·{" "}
            {trust.resolved_claims}/{trust.total_claims} claims resolved
          </span>
        </div>
      </div>
      <div className="bars">
        {Object.entries(trust.breakdown).map(([label, value]) => (
          <div className="bar" key={label}>
            <span>{label.replace("_", " ")}</span>
            <span className="track">
              <span className="fill" style={{ width: `${Math.min(100, value * 2.5)}%` }} />
            </span>
            <span>{value.toFixed(0)}</span>
          </div>
        ))}
      </div>
      {trust.notes.length > 0 && (
        <ul className="notes">
          {trust.notes.map((note, index) => (
            <li key={index}>{note}</li>
          ))}
        </ul>
      )}
    </div>
  );
}

type Tab = "signals" | "claims" | "authors";

export function Panel({
  analysis,
  error,
  onClose,
  onRefresh,
}: {
  analysis: Analysis;
  error: string | null;
  onClose: () => void;
  onRefresh: () => void;
}) {
  const [tab, setTab] = useState<Tab>("signals");
  const predictions = useMemo(
    () => analysis.claims.filter((c) => c.kind === "prediction" || c.kind === "headline_promise"),
    [analysis.claims],
  );

  return (
    <div className="panel" data-testid="cbl-panel">
      <div className="panel-head">
        <div>
          <h1>{analysis.title}</h1>
          <p>
            {analysis.outlet_name ?? analysis.outlet_domain ?? "unknown outlet"} · analyzer:{" "}
            {analysis.analyzer}
          </p>
        </div>
        <button className="close" onClick={onClose} aria-label="Close" data-testid="cbl-close">
          ×
        </button>
      </div>
      {error && <p className="error">{error}</p>}
      <div className="tabs" role="tablist">
        <button role="tab" aria-selected={tab === "signals"} onClick={() => setTab("signals")}>
          Headline ({analysis.signals.length})
        </button>
        <button
          role="tab"
          aria-selected={tab === "claims"}
          onClick={() => setTab("claims")}
          data-testid="cbl-tab-claims"
        >
          Claims ({predictions.length})
        </button>
        <button
          role="tab"
          aria-selected={tab === "authors"}
          onClick={() => setTab("authors")}
          data-testid="cbl-tab-authors"
        >
          Authors ({analysis.authors.length})
        </button>
      </div>
      <div className="body">
        {tab === "signals" && (
          <>
            <div className="score-row">
              <span className="score-num">{Math.round(analysis.clickbait_score)}</span>
              <span className="score-meta">
                /100 clickbait score · {analysis.verdict}
                <br />
                Higher means the headline promises more than the article delivers.
              </span>
            </div>
            {analysis.signals.length === 0 ? (
              <p className="empty">
                Nothing flagged — the headline matches what the article supports.
              </p>
            ) : (
              analysis.signals.map((signal) => <SignalCard key={signal.id} signal={signal} />)
            )}
          </>
        )}
        {tab === "claims" && (
          <>
            {predictions.length === 0 ? (
              <p className="empty">No falsifiable predictions found in this article.</p>
            ) : (
              predictions.map((claim) => (
                <ClaimCard key={claim.id ?? claim.text} claim={claim} onChanged={onRefresh} />
              ))
            )}
          </>
        )}
        {tab === "authors" && (
          <>
            {analysis.authors.length === 0 ? (
              <p className="empty">
                No byline was found on this page, so there is no track record to show.
              </p>
            ) : (
              analysis.authors.map((author) => <AuthorCard key={author.id} author={author} />)
            )}
          </>
        )}
      </div>
      <div className="foot">
        <span>{analysis.claims.length} claims extracted</span>
        <button className="action" onClick={onRefresh} data-testid="cbl-refresh">
          Re-analyze
        </button>
      </div>
    </div>
  );
}

export function Overlay({
  analysis,
  error,
  onRefresh,
}: {
  analysis: Analysis;
  error: string | null;
  onRefresh: () => void;
}) {
  const [open, setOpen] = useState(false);

  const toggle = useCallback(() => setOpen((value) => !value), []);

  useEffect(() => {
    const listener = (message: { type?: string }) => {
      if (message?.type === "overlay:toggle") toggle();
    };
    chrome.runtime?.onMessage?.addListener(listener);
    return () => chrome.runtime?.onMessage?.removeListener(listener);
  }, [toggle]);

  return (
    <div className="root">
      {open ? (
        <Panel
          analysis={analysis}
          error={error}
          onClose={() => setOpen(false)}
          onRefresh={onRefresh}
        />
      ) : (
        <ScoreBadge analysis={analysis} onClick={toggle} />
      )}
    </div>
  );
}
