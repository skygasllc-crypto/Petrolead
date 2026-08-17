# PetroLead

**PetroLead** is a lead-research platform focused on the petroleum, oil & gas,
energy trading, fuel supply, petroleum logistics, refining, bunkering, and
tank-storage industries.

This repository currently implements **Phase 1: Company Identification /
Discovery** — searching public sources for petroleum-industry companies
matching a set of criteria (region, country, city, industry, activity,
product, keywords), then normalizing, deduplicating, scoring, and storing
them for review in a professional B2B dashboard.

> PetroLead only discovers companies from legitimate public/business
> information. It never bypasses logins, CAPTCHAs, or anti-bot protections,
> and never scrapes private profiles or personal data. See
> [Security & Data Collection Policy](#security--data-collection-policy).

---

## Architecture

```text
PetroLead/
│
├── app/                        # FastAPI backend
│   ├── main.py                 # App entrypoint, middleware, error handlers
│   ├── config.py                # Settings (env-driven, pydantic-settings)
│   │
│   ├── database/
│   │   ├── connection.py        # SQLAlchemy engine/session (Postgres or SQLite)
│   │   └── models.py            # Company, CompanySource, SearchQuery ORM models
│   │
│   ├── discovery/                # Discovery engine (source-agnostic)
│   │   ├── types.py              # DiscoveryRequest / DiscoveredCompany contracts
│   │   ├── search.py             # QueryBuilder + SearchProvider abstraction
│   │   ├── sources.py            # BaseSource → SearchSource / WebsiteSource / (B2B, Social — future)
│   │   ├── extractor.py          # Search result → DiscoveredCompany, website enrichment
│   │   ├── normalizer.py         # Company name normalization, domain extraction
│   │   ├── deduplicator.py       # Match/merge logic
│   │   └── relevance.py          # Petroleum-industry relevance scoring
│   │
│   ├── services/
│   │   └── company_service.py    # Orchestrates search → extract → score → dedup → persist
│   │
│   ├── api/
│   │   └── companies.py          # /api/discover, /api/companies, /api/searches
│   │
│   └── core/
│       └── logging.py            # Centralized logging setup
│
├── frontend/                    # React + Vite + Tailwind CSS dashboard
│   └── src/
│       ├── pages/                # Dashboard, Discover, Companies, CompanyProfile, SearchHistory, Settings
│       ├── components/           # Layout, CompanyTable, RelevanceBadge, DiscoveryProgress, ...
│       ├── api/client.js          # Typed fetch wrapper for the backend API
│       └── lib/constants.js       # Form option lists shared across pages
│
├── tests/                        # pytest suite (normalization, dedup, relevance, API, DB)
├── docker-compose.yml             # Postgres + Redis + backend
├── Dockerfile                     # Backend container image
├── requirements.txt / pyproject.toml
├── .env.example
└── README.md
```

### Why this shape?

- **`discovery/types.py`** defines one contract — `DiscoveredCompany` — that
  every source connector returns. The database layer, services, and API
  never need to know whether a company came from a web search, a B2B
  directory, or (later) a compliant social API.
- **`discovery/sources.py`** implements `BaseSource` → `SearchSource` /
  `WebsiteSource` today, and stubs `B2BSource` / `SocialSource` for future
  phases so new sources are additive, not disruptive.
- **`discovery/search.py`** abstracts the web-search backend behind
  `SearchProvider` (Google CSE / Bing / SerpApi / a labeled mock), selected
  purely through `SEARCH_PROVIDER` in `.env` — no provider is hard-coded and
  no key ever lives in source.
- **`database/models.py`** is a normalized relational schema. `Company` is
  intentionally narrow; `CompanySource` records *every* discovery event so
  dedup merges never lose provenance. Later phases add `contacts`, `emails`,
  `phone_numbers`, `social_profiles`, `lead_scores`, and
  `verification_results` as new tables with a foreign key onto
  `companies.id` — no migration of this table required.
- **`services/company_service.py`** is a plain async function
  (`run_discovery`) operating on a SQLAlchemy `Session`. It runs inline on
  FastAPI's event loop today; lifting it into a Celery task later is a
  matter of calling it from a task instead of a request handler — the logic
  itself doesn't change.

---

## Requirements

- Python 3.12+
- Node.js 18+ (frontend)
- PostgreSQL 14+ for staging/production (optional for local dev — see below)
- (Optional) Docker + Docker Compose

## Installation

### 1. Backend

```bash
cd PetroLead
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# Edit .env — see "Environment Variables" below.
```

### 2. Database

**Zero-config local development:** leave `DATABASE_URL` unset (or pointed at
SQLite) and the app will automatically use a local `petrolead.db` SQLite
file — no server to install. This is what the test suite and the commands
below use out of the box.

**PostgreSQL (staging/production):**

```bash
# Using Docker:
docker compose up -d postgres

# Or against an existing Postgres instance, create the database/user:
psql -U postgres -c "CREATE USER petrolead WITH PASSWORD 'petrolead';"
psql -U postgres -c "CREATE DATABASE petrolead OWNER petrolead;"
```

Then set in `.env`:

```env
DATABASE_URL=postgresql+psycopg://petrolead:petrolead@localhost:5432/petrolead
```

Tables are created automatically on startup for Phase 1 convenience
(`init_db()` in `app/database/connection.py`). Production deployments
should switch to Alembic migrations before making further schema changes.

### 3. Environment Variables

Copy `.env.example` to `.env` and fill in real values. **Never commit `.env`.**

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | SQLAlchemy connection string. Defaults to local SQLite. |
| `CORS_ORIGINS` | Comma-separated list of allowed frontend origins. |
| `SEARCH_PROVIDER` | `mock` \| `google_cse` \| `bing` \| `serpapi` |
| `GOOGLE_CSE_API_KEY` / `GOOGLE_CSE_ENGINE_ID` | Required for `google_cse`. Get from [Programmable Search Engine](https://programmablesearchengine.google.com/). |
| `BING_SEARCH_API_KEY` | Required for `bing`. Azure Cognitive Services Bing Search resource key. |
| `SERPAPI_API_KEY` | Required for `serpapi`. From [serpapi.com](https://serpapi.com/). |
| `HTTP_TIMEOUT_SECONDS`, `MAX_CONCURRENT_FETCHES` | Extraction/enrichment tuning. |
| `RATE_LIMIT_PER_MINUTE` | Reserved for API rate limiting. |
| `LOG_LEVEL` | Python logging level. |

Without any search provider configured, PetroLead runs in **mock mode**
(`SEARCH_PROVIDER=mock`, the default) — every discovered company is clearly
labeled `[MOCK]` and flagged `is_mock: true` in the API response. This is
synthetic data for exercising the UI/pipeline only and is never presented as
a real discovered company.

### 4. Running the backend

```bash
source .venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

- API root: `http://localhost:8000/api`
- Interactive docs: `http://localhost:8000/docs`
- Health check: `http://localhost:8000/api/health`

### 5. Running the frontend

```bash
cd frontend
npm install
npm run dev
```

- Dashboard: `http://localhost:5173`
- The Vite dev server proxies `/api/*` to `http://127.0.0.1:8000` (see
  `frontend/vite.config.js`), so no CORS configuration is needed in dev.

### 6. Running with Docker

```bash
docker compose up --build
```

Starts PostgreSQL, Redis (reserved for future background-job phases), and
the backend. Run the frontend separately with `npm run dev` (or add a
frontend service/Dockerfile when it's ready to containerize).

---

## Running Tests

```bash
source .venv/bin/activate
python -m pytest tests/ -v
```

The suite covers:

- **Normalization** — corporate-suffix stripping, punctuation/case handling,
  domain extraction.
- **Deduplication** — same company via domain match, exact-name +
  compatible location, conflicting locations kept separate, unrelated
  companies never merged.
- **Relevance scoring** — clear petroleum company vs. unrelated business,
  score bounds, negative-term penalties (e.g. "petroleum jelly").
- **API validation** — invalid `limit`, 404s, pagination bounds, mock-data
  labeling.
- **Database** — create/read `Company`, `CompanySource`, `SearchQuery`.

Tests run against an isolated SQLite database and the mock search provider
— no external services or API keys required.

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/health` | Liveness check. |
| `POST` | `/api/discover` | Run a discovery job. Body: region, country, city, industry, activity, products[], keywords[], limit. Returns the persisted, deduplicated companies. |
| `GET` | `/api/companies` | List discovered companies. Filters: `country`, `region`, `industry`, `min_relevance`, `search`; pagination: `page`, `page_size`. |
| `GET` | `/api/companies/{id}` | Full company profile, including discovery-source history. |
| `GET` | `/api/searches` | Search/discovery job history, paginated. |

All request/response bodies are validated with Pydantic; invalid input
returns `422` with a structured error body. Unexpected server errors return
a generic `500`/`502` message — full details go to the server logs only,
never to the client.

---

## Security & Data Collection Policy

- **No credential/access-control bypass.** PetroLead never bypasses logins,
  CAPTCHAs, or anti-bot systems, and never scrapes private profiles or
  personal contact information. Social-network connectors (LinkedIn,
  Facebook, Instagram) are explicitly deferred to Phase 5 and will only use
  compliant, official APIs or permitted public data.
- **Secrets stay in `.env`.** No API key is hard-coded; `.env` is
  git-ignored and `.env.example` ships placeholders only.
- **Input validation.** All API input is validated via Pydantic schemas
  before touching the database or discovery pipeline.
- **SQL injection.** All database access goes through SQLAlchemy's ORM /
  parameterized queries — no raw string-built SQL.
- **CORS.** Configured explicitly via `CORS_ORIGINS`; nothing defaults to
  `*`.
- **Safe URL handling & timeouts.** All outbound HTTP (search providers,
  website enrichment) goes through `httpx` with an explicit timeout
  (`HTTP_TIMEOUT_SECONDS`) and a bounded concurrency
  (`MAX_CONCURRENT_FETCHES`); malformed responses/HTML fail soft and are
  logged, never crash a discovery job.
- **No arbitrary code execution.** User input is never `eval`'d, templated
  into shell commands, or otherwise executed.
- **Rate limiting.** `RATE_LIMIT_PER_MINUTE` is reserved in configuration
  for a rate-limiting middleware to be added alongside real search-provider
  usage (mock mode has no external rate limits to respect).
- **Error handling.** Source-unavailable, timeout, malformed-page, and
  database failures are all caught and logged with context; a failed
  discovery job is recorded with `status=failed` and a user-safe message
  rather than crashing the request. Stack traces are never returned to
  clients.

---

## Future Development Phases

Phase 1 (this repository) covers company discovery only. The architecture
is deliberately laid out so these phases can be added without rewriting
existing code:

| Phase | Scope |
|---|---|
| 2 | Website discovery and business contact discovery |
| 3 | Business email extraction & validation |
| 4 | Business telephone extraction & validation |
| 5 | Social/company profile discovery via permitted sources & compliant APIs |
| 6 | B2B source connectors (`B2BSource`) |
| 7 | Lead scoring |
| 8 | Excel/CSV export |
| 9 | Advanced search & filtering |
| 10 | Automated lead monitoring & scheduled searches |

---

## Design Notes / Known Limitations (Phase 1)

- **Relevance scoring** is a curated keyword/weight model
  (`app/discovery/relevance.py`), not an ML classifier — deliberately
  simple and swappable behind one function (`score_relevance`).
- **Deduplication** uses domain match → exact normalized-name + compatible
  location → fuzzy name similarity, in that order of trust, and never
  auto-merges below an 85% confidence threshold. Ambiguous cases are kept
  as separate records rather than risking an incorrect merge.
- **Discovery jobs run synchronously** on FastAPI's async event loop
  (non-blocking to other requests, since all I/O is `async`/`httpx`), not
  on a background worker. `run_discovery()` is written so it can be called
  from a Celery task with no logic changes once Phase 2+ needs long-running
  jobs; `docker-compose.yml` already provisions Redis for that transition.
- **Mock search provider.** With no real `SEARCH_PROVIDER` configured, all
  discovered companies are synthetic and prefixed `[MOCK]`, with
  `is_mock: true` in the API response and a banner in the UI. Configure
  `google_cse`, `bing`, or `serpapi` (with the corresponding API key) to
  discover real companies.
