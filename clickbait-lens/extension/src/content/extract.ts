import type { PageExtract } from "../shared/types";

/**
 * Readability-lite extraction.
 *
 * Deliberately small: pick the densest block of paragraph text, and read the
 * byline from the places publishers actually put it (JSON-LD, meta tags,
 * microdata, then class-name conventions).
 */

const BODY_SELECTORS = [
  "article",
  "[itemprop='articleBody']",
  "[data-component='text-block']",
  ".article-body",
  ".article__body",
  ".story-body",
  ".post-content",
  ".entry-content",
  "main",
  "[role='main']",
];

const BYLINE_SELECTORS = [
  "[rel='author']",
  "[itemprop='author'] [itemprop='name']",
  "[itemprop='author']",
  "[data-testid='byline']",
  ".byline",
  ".byline__name",
  ".author-name",
  ".c-byline__author",
  "article address",
];

const DEK_SELECTORS = [
  ".standfirst",
  ".subheadline",
  ".article__subhead",
  "[data-testid='standfirst']",
  "h2.subtitle",
];

const NOISE_SELECTORS =
  "script,style,noscript,figure,figcaption,aside,nav,footer,header,form,iframe," +
  ".advertisement,.ad,.newsletter,.related,.share,.comments";

function text(node: Element | null | undefined): string {
  return (node?.textContent ?? "").replace(/\s+/g, " ").trim();
}

function meta(...names: string[]): string | null {
  for (const name of names) {
    const node =
      document.querySelector<HTMLMetaElement>(`meta[property='${name}']`) ??
      document.querySelector<HTMLMetaElement>(`meta[name='${name}']`);
    const value = node?.content?.trim();
    if (value) return value;
  }
  return null;
}

/** Structured data is the most reliable byline source when publishers ship it. */
function fromJsonLd(): { byline?: string; published?: string; headline?: string } {
  const out: { byline?: string; published?: string; headline?: string } = {};
  const nodes = document.querySelectorAll<HTMLScriptElement>(
    "script[type='application/ld+json']",
  );
  for (const node of nodes) {
    let parsed: unknown;
    try {
      parsed = JSON.parse(node.textContent ?? "");
    } catch {
      continue;
    }
    const candidates: Record<string, unknown>[] = [];
    const push = (value: unknown) => {
      if (Array.isArray(value)) value.forEach(push);
      else if (value && typeof value === "object") {
        const record = value as Record<string, unknown>;
        candidates.push(record);
        if (record["@graph"]) push(record["@graph"]);
      }
    };
    push(parsed);

    for (const candidate of candidates) {
      const author = candidate.author;
      if (!out.byline && author) {
        const names = (Array.isArray(author) ? author : [author])
          .map((a) => (typeof a === "string" ? a : ((a as Record<string, unknown>)?.name as string)))
          .filter((n): n is string => typeof n === "string" && n.length > 0);
        if (names.length) out.byline = names.join(" and ");
      }
      if (!out.published && typeof candidate.datePublished === "string") {
        out.published = candidate.datePublished;
      }
      if (!out.headline && typeof candidate.headline === "string") {
        out.headline = candidate.headline;
      }
    }
  }
  return out;
}

function extractTitle(jsonLdHeadline?: string): string {
  return (
    meta("og:title", "twitter:title") ??
    text(document.querySelector("h1")) ??
    jsonLdHeadline ??
    document.title
  ).trim();
}

function extractByline(jsonLdByline?: string): string | null {
  if (jsonLdByline) return jsonLdByline;
  const fromMeta = meta("article:author", "author", "byl", "parsely-author");
  if (fromMeta && !fromMeta.startsWith("http")) return fromMeta;
  for (const selector of BYLINE_SELECTORS) {
    const value = text(document.querySelector(selector));
    if (value && value.length < 160) return value;
  }
  return null;
}

function extractDek(): string | null {
  for (const selector of DEK_SELECTORS) {
    const value = text(document.querySelector(selector));
    if (value) return value;
  }
  return meta("og:description", "description");
}

function extractPublished(jsonLdPublished?: string): string | null {
  const raw =
    jsonLdPublished ??
    meta("article:published_time", "datePublished", "publish-date") ??
    document.querySelector("time[datetime]")?.getAttribute("datetime") ??
    null;
  if (!raw) return null;
  const parsed = new Date(raw);
  return Number.isNaN(parsed.getTime()) ? null : parsed.toISOString();
}

function paragraphScore(container: Element): number {
  let total = 0;
  for (const p of container.querySelectorAll("p")) {
    const length = text(p).length;
    // Short <p> nodes are usually captions, credits, or promo copy.
    if (length > 60) total += length;
  }
  return total;
}

/** Pick the container holding the article prose. */
export function findBodyContainer(): Element | null {
  let best: Element | null = null;
  let bestScore = 0;

  const candidates = new Set<Element>();
  for (const selector of BODY_SELECTORS) {
    document.querySelectorAll(selector).forEach((node) => candidates.add(node));
  }
  if (candidates.size === 0) {
    document.querySelectorAll("div,section").forEach((node) => candidates.add(node));
  }

  for (const candidate of candidates) {
    const score = paragraphScore(candidate);
    // Prefer the deepest container that still holds the text, so we don't grab
    // the whole page when <main> wraps a tight .article-body.
    const deeper = best !== null && score === bestScore && best.contains(candidate);
    if (score > bestScore || deeper) {
      best = candidate;
      bestScore = score;
    }
  }
  return bestScore > 200 ? best : null;
}

function containerText(container: Element): string {
  const clone = container.cloneNode(true) as Element;
  clone.querySelectorAll(NOISE_SELECTORS).forEach((node) => node.remove());
  const paragraphs = Array.from(clone.querySelectorAll("p,li,h2,h3"))
    .map((node) => text(node))
    .filter((value) => value.length > 40);
  return paragraphs.length ? paragraphs.join("\n\n") : text(clone);
}

export function extractPage(): PageExtract {
  const jsonLd = fromJsonLd();
  const container = findBodyContainer();
  const body = container ? containerText(container) : "";
  const title = extractTitle(jsonLd.headline);
  const wordCount = body.split(/\s+/).filter(Boolean).length;

  return {
    url: location.href,
    title,
    body,
    byline: extractByline(jsonLd.byline),
    dek: extractDek(),
    published_at: extractPublished(jsonLd.published),
    outlet_name: meta("og:site_name") ?? null,
    isArticle: Boolean(title) && wordCount >= 120,
  };
}
