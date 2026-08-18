# PetroLead

**PetroLead** is a lead-research platform focused on the petroleum, oil & gas,
energy trading, fuel supply, petroleum logistics, refining, bunkering, and
tank-storage industries.

This repository implements **Phase 1** (company discovery) plus the phases
that build directly on it — **2** (contact-page & social-profile discovery),
**3** (business email extraction & validation), **4** (business phone
extraction & validation), **7** (lead scoring), **8** (CSV/Excel export),
**9** (advanced search & filtering), and **10** (scheduled searches).
**Phases 5 and 6** (social-platform discovery via compliant APIs, and B2B
directory connectors) are architected but intentionally not wired up — they
need external prerequisites (an approved platform API partnership, reviewed
B2B directory terms of service) that only you can arrange; see
[Future Development Phases](#future-development-phases).

> PetroLead only discovers companies and contact info from legitimate
> public/business information. It never bypasses logins, CAPTCHAs, or
> anti-bot protections, never scrapes private profiles, and never sends
> email or places calls. See
> [Security & Data Collection Policy](#security--data-collection-policy).

---

## Architecture

```text
PetroLead/
│
├── app/                        # FastAPI backend
│   ├── main.py                  # App entrypoint, middleware, error handlers
│   ├── worker.py                # Celery app + beat schedule (Phase 10)
│   ├── config.py                # Settings (env-driven, pydantic-settings)
│   │
│   ├── database/
│   │   ├── connection.py        # SQLAlchemy engine/session (Postgres or SQLite)
│   │   └── models.py            # Company + CompanySource/Contact/SocialProfile/
│   │                             # Email/Phone/LeadScore, SearchQuery, SavedSearch
│   │
│   ├── discovery/                # Discovery engine (source-agnostic)
│   │   ├── types.py              # DiscoveryRequest / DiscoveredCompany contracts
│   │   ├── search.py             # QueryBuilder + SearchProvider abstraction
│   │   ├── sources.py            # BaseSource → SearchSource / WebsiteSource / (B2B, Social — future)
│   │   ├── extractor.py          # Search result → DiscoveredCompany; homepage + contact-page enrichment
│   │   ├── contacts.py           # Phase 2: contact-page + social-profile link extraction
│   │   ├── emails.py             # Phase 3: email extraction + MX-record validation
│   │   ├── phones.py             # Phase 4: phone extraction + libphonenumber validation
│   │   ├── lead_scoring.py       # Phase 7: composite lead-score formula
│   │   ├── normalizer.py         # Company name normalization, domain extraction
│   │   └── deduplicator.py       # Match/merge logic
│   │
│   ├── services/
│   │   ├── company_service.py       # search → extract → score → dedup → persist → export
│   │   └── saved_search_service.py  # Phase 10: saved-search CRUD + due-search execution
│   │
│   ├── api/
│   │   ├── companies.py          # /api/discover, /api/companies (+ /export), /api/searches
│   │   └── saved_searches.py     # /api/saved-searches (Phase 10)
│   │
│   └── core/
│       └── logging.py            # Centralized logging setup
│
├── frontend/                    # React + Vite + Tailwind CSS dashboard
│   └── src/
│       ├── pages/                # Dashboard, Discover, Companies, CompanyProfile,
│       │                          # SearchHistory, ScheduledSearches, Settings
│       ├── components/           # Layout, CompanyTable, RelevanceBadge, DiscoveryProgress, ...
│       ├── api/client.js          # Typed fetch wrapper for the backend API
│       └── lib/constants.js       # Form option lists shared across pages
│
├── tests/                        # pytest suite (91 tests — see "Running Tests")
├── docker-compose.yml             # Postgres + Redis + backend + worker
├── Dockerfile                     # Backend/worker container image
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
  `WebsiteSource` today, and stubs `B2BSource` / `SocialSource` for Phase 5/6
  so new sources are additive, not disruptive.
- **`discovery/search.py`** abstracts the web-search backend behind
  `SearchProvider` (Google CSE / Bing / SerpApi / a labeled mock), selected
  purely through `SEARCH_PROVIDER` in `.env` — no provider is hard-coded and
  no key ever lives in source.
- **`database/models.py`** is a normalized relational schema. `Company` stays
  narrow; `CompanySource` records *every* discovery event so dedup merges
  never lose provenance. `CompanyContact`/`SocialProfile` (Phase 2),
  `CompanyEmail`/`CompanyPhone` (Phase 3/4), and `LeadScore` (Phase 7) each
  hang off `companies.id` the same way — no migration of the `companies`
  table itself was needed to add any of them, and `verification_results`
  can follow the same pattern later.
- **`discovery/contacts.py` / `emails.py` / `phones.py`** each extract only
  what a company already published in its own page markup (a link, a
  `mailto:`, a `tel:`, visible text) — never guessing, never visiting a
  login-gated page, and "validation" means syntax + a public DNS/format
  check, never sending mail or placing a call.
- **`discovery/lead_scoring.py`** is a transparent weighted formula (not a
  black box) over relevance + contact completeness + verified email/phone —
  see [Design Notes](#design-notes--known-limitations) for the exact
  weights.
- **`services/company_service.py`** is a plain async function
  (`run_discovery`) operating on a SQLAlchemy `Session`. It runs inline on
  FastAPI's event loop for interactive searches; `saved_search_service.py`
  calls the exact same function from `app/worker.py`'s Celery task for
  scheduled ones, so results are identical either way.

---

## Requirements

- Python 3.12+
- Node.js 18+ (frontend)
- PostgreSQL 14+ for staging/production (optional for local dev — see below)
- Redis (only if you use Phase 10 scheduled searches)
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

Tables are created automatically on startup for convenience (`init_db()` in
`app/database/connection.py`). Production deployments should switch to
Alembic migrations before making further schema changes.

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
| `REDIS_URL` | Only needed for Phase 10's Celery worker/beat. |
| `RATE_LIMIT_PER_MINUTE` | Reserved for API rate limiting. |
| `LOG_LEVEL` | Python logging level. |

Without any search provider configured, PetroLead runs in **mock mode**
(`SEARCH_PROVIDER=mock`, the default) — every discovered company (and its
contact page, social links, emails, and phone numbers) is clearly labeled
`[MOCK]` / `is_mock: true`. This is synthetic data for exercising the
UI/pipeline only and is never presented as real.

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

### 6. Running the background worker (Phase 10 only)

Everything except *scheduled* searches works without this. If you create a
saved search (`POST /api/saved-searches` or the "Scheduled Searches" page)
and want it to run automatically instead of via the manual "Run due
searches now" button, run a Celery worker + beat process alongside the API:

```bash
docker compose up -d redis   # or point REDIS_URL at any reachable Redis
source .venv/bin/activate
celery -A app.worker worker --beat --loglevel=info
```

### 7. Running with Docker

```bash
docker compose up --build
```

Starts PostgreSQL, Redis, the backend API, and the Celery worker/beat
process for scheduled searches. Run the frontend separately with
`npm run dev` (or add a frontend service/Dockerfile when it's ready to
containerize).

---

## Running Tests

```bash
source .venv/bin/activate
python -m pytest tests/ -v
```

91 tests, covering:

- **Normalization** — corporate-suffix stripping, punctuation/case handling,
  domain extraction.
- **Deduplication** — same company via domain match, exact-name +
  compatible location, conflicting locations kept separate, unrelated
  companies never merged.
- **Relevance scoring** — clear petroleum company vs. unrelated business,
  score bounds, negative-term penalties (e.g. "petroleum jelly").
- **Contact/email/phone extraction** — contact-page and social-profile link
  discovery from page markup; email extraction from `mailto:`/text with
  placeholder-domain and asset-filename false positives filtered out;
  phone extraction from `tel:`/text with libphonenumber validation.
- **Lead scoring** — component weighting, bounds, verified-contact impact.
- **API validation** — invalid `limit`/`frequency`, 404s, pagination
  bounds, advanced filters (`has_email`, `has_phone`, `product`,
  `min_lead_score`), export (CSV/XLSX), mock-data labeling.
- **Saved searches** — CRUD, immediate-due-on-create, idempotent
  `run-due` (a search already run this period isn't re-run).
- **Database** — create/read across every model.

Tests run against an isolated SQLite database and the mock search provider
— no external services or API keys required. (One email-validation test
does a real DNS lookup against the reserved `.invalid` TLD, which is
guaranteed never to resolve — it tolerates a network-less environment by
accepting either `False` or `None`.)

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/health` | Liveness check. |
| `POST` | `/api/discover` | Run a discovery job. Body: region, country, city, industry, activity, products[], keywords[], limit. Returns the persisted, deduplicated companies. |
| `GET` | `/api/companies` | List companies. Filters: `country`, `region`, `industry`, `product`, `min_relevance`, `min_lead_score`, `has_email`, `has_phone`, `search`; pagination: `page`, `page_size`. |
| `GET` | `/api/companies/export` | Export every company matching the same filters as CSV or XLSX (`format=csv\|xlsx`, capped at 5000 rows). |
| `GET` | `/api/companies/{id}` | Full company profile — sources, contact page, social profiles, emails, phones, lead-score breakdown. |
| `GET` | `/api/searches` | Search/discovery job history, paginated. |
| `POST` | `/api/saved-searches` | Create a scheduled search (`frequency`: `daily`\|`weekly`). |
| `GET` | `/api/saved-searches` | List saved searches. |
| `PATCH` | `/api/saved-searches/{id}?is_active=` | Pause/resume a saved search. |
| `DELETE` | `/api/saved-searches/{id}` | Delete a saved search. |
| `POST` | `/api/saved-searches/run-due` | Manually run whichever saved searches are currently due (no worker required). |

All request/response bodies are validated with Pydantic; invalid input
returns `422` with a structured error body. Unexpected server errors return
a generic `500`/`502` message — full details go to the server logs only,
never to the client.

---

## Security & Data Collection Policy

- **No credential/access-control bypass.** PetroLead never bypasses logins,
  CAPTCHAs, or anti-bot systems, and never scrapes private profiles or
  personal data. Social-network *discovery* connectors (LinkedIn, Facebook,
  Instagram) are explicitly deferred to Phase 5 and will only use
  compliant, official APIs or permitted public data — see
  [Future Development Phases](#future-development-phases). What *is*
  implemented (Phase 2) only follows links a company published on its own
  public homepage; it never logs into or scrapes the social platforms
  themselves.
- **Emails/phones are extracted, never contacted.** Phase 3/4 "validation"
  is a public MX-record DNS lookup (email) and structural/format checking
  via libphonenumber (phone) — PetroLead never sends an email or places a
  call to verify a lead.
- **Secrets stay in `.env`.** No API key is hard-coded; `.env` is
  git-ignored and `.env.example` ships placeholders only.
- **Input validation.** All API input is validated via Pydantic schemas
  before touching the database or discovery pipeline.
- **SQL injection.** All database access goes through SQLAlchemy's ORM /
  parameterized queries — no raw string-built SQL.
- **CORS.** Configured explicitly via `CORS_ORIGINS`; nothing defaults to
  `*`.
- **Safe URL handling & timeouts.** All outbound HTTP (search providers,
  website/contact-page enrichment) goes through `httpx` with an explicit
  timeout (`HTTP_TIMEOUT_SECONDS`) and bounded concurrency
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

| Phase | Scope | Status |
|---|---|---|
| 2 | Website discovery and business contact discovery | **Implemented** — contact-page & social-profile link discovery |
| 3 | Business email extraction & validation | **Implemented** |
| 4 | Business telephone extraction & validation | **Implemented** |
| 5 | Social/company profile discovery via permitted sources & compliant APIs | Blocked — needs an approved platform API partnership |
| 6 | B2B source connectors (`B2BSource`) | Blocked — needs reviewed ToS/API access per directory |
| 7 | Lead scoring | **Implemented** |
| 8 | Excel/CSV export | **Implemented** |
| 9 | Advanced search & filtering | **Implemented** |
| 10 | Automated lead monitoring & scheduled searches | **Implemented** (needs a running Celery worker for true automation — see above) |

Phases 5 and 6 are architected (`SocialSource`, `B2BSource` in
`app/discovery/sources.py`, both raising a clear `NotImplementedError`) but
not wired to a real backend, because doing so responsibly requires
something this app can't obtain on its own: LinkedIn/Facebook/etc. require
an approved API partnership to access company data at all, and each B2B
directory has its own terms of service that need reviewing before any
integration (scraping many of them outright violates those terms). Once
that access exists, implementing the connector is additive — no other part
of the app needs to change.

---

## Design Notes / Known Limitations

- **Relevance scoring** is a curated keyword/weight model
  (`app/discovery/relevance.py`), not an ML classifier — deliberately
  simple and swappable behind one function (`score_relevance`).
- **Deduplication** uses domain match → exact normalized-name + compatible
  location → fuzzy name similarity, in that order of trust, and never
  auto-merges below an 85% confidence threshold. Ambiguous cases are kept
  as separate records rather than risking an incorrect merge.
- **Lead scoring** (`app/discovery/lead_scoring.py`) is a transparent
  weighted sum, not a black box: 50% petroleum relevance, up to 20% for
  having a website/contact page/social profile, up to 15% for a
  domain-verified email, up to 15% for a structurally valid phone number.
  Each component is exposed in the API/UI so a user can see exactly why a
  company scored the way it did.
- **Discovery jobs run synchronously** on FastAPI's async event loop
  (non-blocking to other requests, since all I/O is `async`/`httpx`) for
  interactive searches. Scheduled searches (Phase 10) run the identical
  `run_discovery()` function from a Celery task instead — see "Running the
  background worker" above.
- **Contact/email/phone extraction fetches at most two pages per
  company** — the homepage, and its Contact page if one was found — capped
  at 5 emails and 5 phone candidates each, to keep a discovery job's
  latency bounded.
- **Mock search provider.** With no real `SEARCH_PROVIDER` configured, all
  discovered companies — including their contact page, social links,
  emails, and phone numbers — are synthetic, clearly labeled `[MOCK]` /
  `is_mock: true`, and deterministically derived from the same fake mock
  domain. Real (non-mock) companies only ever get contact/email/phone data
  that was literally present in their own page's markup. Configure
  `google_cse`, `bing`, or `serpapi` (with the corresponding API key) to
  discover real companies.
