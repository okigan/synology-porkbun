/** Wire types — kept in step with the FastAPI schemas in `backend/app/schemas.py`. */

export type ClaimKind = "prediction" | "factual" | "opinion" | "headline_promise";

export type Resolution =
  | "unresolved"
  | "true"
  | "mostly_true"
  | "mixed"
  | "mostly_false"
  | "false"
  | "unverifiable";

export type Verdict = "clean" | "low" | "moderate" | "high";

export interface Evidence {
  text: string;
  where: "headline" | "body";
  note: string;
}

export interface Signal {
  id: string;
  label: string;
  severity: number;
  weight: number;
  explanation: string;
  evidence: Evidence[];
}

export interface Claim {
  id: number | null;
  text: string;
  kind: ClaimKind;
  assertiveness: number;
  extraction_confidence: number;
  horizon_text: string | null;
  target_date: string | null;
  resolution: Resolution;
  resolution_method: string | null;
  resolution_notes: string | null;
  author_id: number | null;
  article_url: string | null;
  article_title: string | null;
  published_at: string | null;
}

export interface Trust {
  trust_index: number;
  grade: string;
  resolved_claims: number;
  total_claims: number;
  raw_accuracy: number | null;
  adjusted_accuracy: number;
  overconfidence: number;
  mean_clickbait: number;
  articles: number;
  notes: string[];
  breakdown: Record<string, number>;
}

export interface Author {
  id: number;
  canonical_key: string;
  display_name: string;
  primary_outlet_domain: string | null;
  bio: string | null;
  trust: Trust;
}

export interface ArticleBrief {
  id: number;
  url: string;
  title: string;
  clickbait_score: number;
  published_at: string | null;
}

export interface AuthorDetail extends Author {
  aliases: string[];
  recent_claims: Claim[];
  recent_articles: ArticleBrief[];
}

export interface Analysis {
  url: string;
  title: string;
  outlet_domain: string | null;
  outlet_name: string | null;
  analyzer: string;
  clickbait_score: number;
  verdict: Verdict;
  signals: Signal[];
  claims: Claim[];
  authors: Author[];
  article_id: number | null;
}

export interface SearchResultItem {
  title: string;
  url: string;
  snippet: string;
  source: string;
  published: string | null;
  stance: number;
  stance_reason: string;
}

export interface Verification {
  claim_id: number;
  claim_text: string;
  query: string;
  provider: string;
  suggested_resolution: Resolution;
  confidence: number;
  rationale: string;
  applied: boolean;
  evidence: SearchResultItem[];
  search_url: string;
}

/** What the content script scrapes off the page. */
export interface PageExtract {
  url: string;
  title: string;
  body: string;
  byline: string | null;
  dek: string | null;
  published_at: string | null;
  outlet_name: string | null;
  /** Whether the page looks like an article at all. */
  isArticle: boolean;
}

export interface Settings {
  apiBase: string;
  enabled: boolean;
  autoHighlight: boolean;
}

export const DEFAULT_SETTINGS: Settings = {
  apiBase: "http://127.0.0.1:8000",
  enabled: true,
  autoHighlight: true,
};

/** Messages exchanged between content script, popup, and background. */
export type RuntimeMessage =
  | { type: "analysis:ready"; analysis: Analysis }
  | { type: "analysis:none" }
  | { type: "analysis:get" }
  | { type: "analysis:rerun" }
  | { type: "overlay:toggle" };
