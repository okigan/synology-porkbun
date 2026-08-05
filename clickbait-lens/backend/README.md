# Clickbait Lens — backend

FastAPI service behind the extension. Managed with [uv](https://docs.astral.sh/uv/).

```bash
uv sync --group dev          # install
uv run pytest                # tests (offline, deterministic)
uv run clickbait-lens        # serve on http://127.0.0.1:8000
```

Interactive API docs: <http://127.0.0.1:8000/docs>

## Layout

| Path | What it does |
| --- | --- |
| `app/analysis/` | Clickbait signals and claim extraction. `heuristic.py` is the default, LLM-free path; `llm.py` is an opt-in Claude adapter behind the same `Analyzer` protocol. |
| `app/identity/` | Byline normalization and the alias table that merges spellings across outlets. |
| `app/verification/` | Live search providers and the LLM-free stance scorer that turns evidence into a suggested verdict. |
| `app/scoring/trust.py` | Brier-style prediction accuracy, calibration, and the composite trust index. |
| `app/api/` | HTTP routes. |

## Configuration

All settings are environment variables prefixed `CBL_`, and all have working
defaults — the service runs with no API keys.

| Variable | Default | Notes |
| --- | --- | --- |
| `CBL_ANALYZER` | `heuristic` | `llm` requires `uv sync --extra llm` and an API key. |
| `CBL_SEARCH_PROVIDER` | `duckduckgo` | `duckduckgo` (keyless), `tavily`, `brave`, `fixture` (offline). |
| `CBL_TAVILY_API_KEY` / `CBL_BRAVE_API_KEY` | unset | Needed for those providers. |
| `CBL_ANTHROPIC_API_KEY` | unset | Only for `CBL_ANALYZER=llm`. |
| `CBL_DATABASE_URL` | `sqlite+pysqlite:///./clickbait_lens.db` | Any SQLAlchemy URL. |
| `CBL_SEED_ON_STARTUP` | `true` | Loads two demo authors with resolved predictions. |
| `CBL_SEARCH_MAX_RESULTS` | `8` | Evidence items fetched per verification. |

## Endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/api/v1/analyze` | Score a page, extract claims, resolve authors. |
| `GET` | `/api/v1/authors` | Look up authors by name/outlet. |
| `GET` | `/api/v1/authors/{id}` | Track record: trust index, claims, articles, aliases. |
| `POST` | `/api/v1/authors/{id}/aliases` | Merge another byline spelling onto an author. |
| `GET` | `/api/v1/claims` | Filter claims by author, kind, or resolution. |
| `POST` | `/api/v1/claims/{id}/verify` | Live web search + stance scoring → suggested verdict. |
| `POST` | `/api/v1/claims/{id}/resolution` | Record a human verdict. |
