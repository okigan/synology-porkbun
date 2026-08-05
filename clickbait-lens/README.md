# Clickbait Lens

A browser extension that reads the article you are on, flags where the headline
claims more than the body supports, and shows how the author's past predictions
actually turned out.

The product question it answers: *"this says X — but does the article support X,
and has this person been right before?"*

```
┌── Chrome MV3 extension ─────────┐        ┌── FastAPI backend ──────────────┐
│ content script                  │        │ analysis   headline signals,    │
│   extract headline/byline/body  │ POST   │            claim extraction     │
│   overlay: score, signals,  ────┼───────▶│ identity   byline → author      │
│   claims, author track record   │        │ scoring    trust index          │
│   highlight contradicting text  │        │ verify     live search + stance │
│ popup: settings + summary       │◀───────┤            scoring              │
└─────────────────────────────────┘  JSON  └─────────────────────────────────┘
                                                          │
                                                          ▼
                                              DuckDuckGo / Tavily / Brave
```

## What it does

**Headline integrity.** Eleven rule-based signals compare the headline against
the body. The three that carry the product are:

| Signal | Fires when |
| --- | --- |
| `assertive_headline_hedged_body` | The headline states it flatly; the passages backing it are hedged with *may*, *could*, *suggests*. |
| `attribution_stripped` | In the body it's something a source claims; the headline presents it as established fact. |
| `headline_body_divergence` | Substantive headline terms never appear in the article at all. |

Each signal returns the exact sentence it fired on, and the content script
highlights that sentence in the page — so "claims X but isn't X" is something
you can see, not just a number.

**Claim tracking.** Falsifiable claims are extracted from each article, with a
resolution deadline parsed from the text (*by 2030*, *within five years*, *next
year*). Predictions are the ones that count toward an author's record.

**Verification.** A claim can be checked against live web search. Evidence is
scored for stance — support cues, refutation cues, and numeric threshold
comparison (*"will exceed 40%"* vs *"reached 20.4%"*) — then aggregated into a
suggested verdict with a confidence, weighted by source and discounted when
sources disagree. Every verdict is a suggestion you can accept or overrule.

**Trust index.** Per author, 0-100 from three components: prediction accuracy (a
Brier score over resolved claims, shrunk toward neutral when the sample is
thin), calibration (does confidence track outcomes?), and headline integrity
across their articles. The components are always shown alongside the composite —
a low score from three claims should not look like a low score from three
hundred.

**Author identity.** Bylines are normalized (honorifics, initials, accents,
`Smith, Jane`, job titles) and merged through an alias table, so the same person
carries one record across outlets.

## Running it

```bash
# 1. Backend — no API keys needed
cd backend && uv sync --group dev && uv run clickbait-lens

# 2. Extension
cd extension && npm install && npm run build

# 3. Load it: chrome://extensions → Developer mode → Load unpacked → extension/dist
```

Open a news article. A badge appears bottom-right with the clickbait score;
click it for signals, claims, and author track records. Seed data gives two
demo authors an existing record, so the trust index means something on the
first run.

## Tests

```bash
cd backend && uv run pytest          # 51 tests: signals, claims, identity, verification, trust, API
cd e2e     && npm install && npm test  # 8 Playwright tests: real Chromium, extension loaded
```

The E2E suite starts its own backend on port 8901 with the offline `fixture`
search provider and serves article fixtures on 8902, so it is deterministic and
needs no network. It builds the extension first (`pretest`).

## Design decisions

**LLM-free by default.** The analyzer is a rule-based implementation behind an
`Analyzer` protocol; it runs instantly, anywhere, with no key. An optional
Claude adapter (`CBL_ANALYZER=llm`) implements the same protocol so its output
can be compared against the rules as they mature — the direction of travel is
toward rules, not away from them. Verification is LLM-free too: stance comes
from cue lexicons and numeric comparison, not a model.

**Live verification, deterministic tests.** Search providers are pluggable —
keyless DuckDuckGo by default, Tavily or Brave with a key, and a fixture
provider that reads a local JSON corpus. Tests use the fixture provider; nothing
in CI depends on the live web.

**Suggestions, not verdicts.** Automated resolution is always reviewable: the
query, the evidence, the per-result stance and the reason for it are all
returned, along with a link to run the same search yourself.

## Known limits

- **Extraction is heuristic.** Paywalls, infinite-scroll feeds, and heavily
  client-rendered pages will yield partial or no body text; the extension stays
  silent rather than scoring something it hasn't read.
- **DuckDuckGo scraping is fragile.** It is the keyless default so the prototype
  works out of the box; use Tavily or Brave for anything load-bearing.
- **Stance scoring is lexical.** It catches explicit refutation and numeric
  shortfalls, not implication or sarcasm. It reports low confidence rather than
  guessing, and unresolved is a normal outcome.
- **Alias merging is manual.** Same-name-different-person is not handled
  automatically; the alias table is outlet-scoped so you can disambiguate, but
  someone has to make the call.
- **Single-machine prototype.** SQLite, no auth, CORS wide open. Fine for local
  use, not for deployment.

## Layout

| Path | |
| --- | --- |
| `backend/` | FastAPI + uv. See `backend/README.md` for configuration and endpoints. |
| `extension/` | Chrome MV3, React + TypeScript, built with Vite. |
| `e2e/` | Playwright tests against a real browser with the extension loaded. |
