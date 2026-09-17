# PetroLead

**PetroLead** is a lead-research platform focused on the petroleum, oil & gas,
energy trading, fuel supply, petroleum logistics, refining, bunkering, and
tank-storage industries.

This repository implements **Phase 1** (company discovery) plus every phase
that builds directly on it — **2** (contact-page & social-profile
discovery), **3** (business email extraction & validation), **4** (business
phone extraction & validation), **7** (lead scoring), **8** (CSV/Excel
export), **9** (advanced search & filtering), and **10** (scheduled
searches). **Phases 5 and 6** (social-platform and B2B-directory discovery)
are *partially* implemented: two opt-in checkboxes on the Discover form find
LinkedIn/Facebook company pages and B2B-directory listings through your
configured search provider's `site:` operator — legitimate, permitted
public-search discovery, never by logging into or scraping those platforms.
What's still missing is a full integration (an approved platform API
partnership, reviewed per-directory terms of service) that only you can
arrange; see [Future Development Phases](#future-development-phases).

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
  `WebsiteSource`, plus `B2BSource` / `SocialSource` (Phase 5/6, partial —
  `site:`-scoped search queries, opt-in via `include_social_search` /
  `include_b2b_directories`). Both keep `website=None` on every candidate
  they produce specifically so nothing downstream ever fetches a
  directory/platform page — only the search engine's own public index is
  ever touched.
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
- **`discovery/profile_lookup.py`** is the "paste a link" fallback for a
  *personal* profile URL (`linkedin.com/in/...`) — that page is login-gated
  the same as everywhere else, so it's never fetched. Instead it queries the
  configured `SearchProvider` for whatever public snippet a search engine
  already indexed for that exact URL, and parses a name/title/company out of
  it if there is one (same trust model as `SocialSource`). Only succeeds
  when a company can be identified from the snippet — there's no standalone
  "person" record, only a named contact hanging off a `CompanyContact` row.
  Deliberately conservative: a snippet has to explicitly say "{Title} at
  {Company}" (or a clear 3-part "{Name} - {Title} - {Company}") before a
  company is reported at all — a shorter, ambiguous snippet is left
  name-only rather than guessed (an earlier version guessed wrong on a real
  profile, reporting someone's *school* as their employer).
- **`discovery/email_finder.py`** is an optional enrichment on top of that:
  once a company's domain is confirmed via an actual search result (never
  guessed — see `company_service._resolve_company_domain`), it asks
  [Hunter.io](https://hunter.io/) (`HUNTER_IO_API_KEY`) whether it has a
  confident (score ≥ 50) business email for that specific named person.
  Skipped entirely when unconfigured, in mock mode, or when Hunter has no
  confident match — the preview still succeeds either way, just without an
  email attached.
- **`discovery/lead_scoring.py`** is a transparent weighted formula (not a
  black box) over relevance + contact completeness + verified email/phone —
  see [Design Notes](#design-notes--known-limitations) for the exact
  weights.
- **`services/company_service.py`** has two entry points over the same
  scoring/dedup logic: `discover_preview()` — used by the interactive
  Discover page and "paste a link" lookup — never writes to the database;
  it just scores candidates and checks (read-only) whether each one
  already matches a saved company. Nothing is persisted until the user
  explicitly calls `POST /api/companies/save` (or `/save-bulk`) on the
  previewed results. `run_discovery()` auto-persists and is used only by
  scheduled searches (`saved_search_service.py`, via `app/worker.py`'s
  Celery task) — there's no one present to click Save on an unattended run.

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

**Schema migrations.** The schema is managed with Alembic
(`alembic/versions/`). The app applies any pending migrations when it starts
(`RUN_MIGRATIONS_ON_STARTUP=true`, the default). A database created by an
earlier version of PetroLead — before migrations existed — is adopted
automatically: its tables and data are kept and only the newer changes are
applied. When several app processes share one database (or in production),
set `RUN_MIGRATIONS_ON_STARTUP=false` and run `alembic upgrade head` once per
deploy instead. After changing a model, draft the next migration with
`alembic revision --autogenerate -m "describe the change"` and review it
before committing.

### 3. Environment Variables

Copy `.env.example` to `.env` and fill in real values. **Never commit `.env`.**

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | SQLAlchemy connection string. Defaults to local SQLite. |
| `RUN_MIGRATIONS_ON_STARTUP` | Default `true`: apply pending database migrations when the app starts. Set `false` when several app processes share a database, and run `alembic upgrade head` per deploy. |
| `CORS_ORIGINS` | Comma-separated list of allowed frontend origins. |
| `SECRET_KEY` | Signs login session tokens. **The shipped default is insecure and dev-only** — generate a real one: `python -c "import secrets; print(secrets.token_hex(32))"`. |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Login session lifetime. Default 10080 (1 week). |
| `ADMIN_EMAILS` | Comma-separated emails that get admin access (the Users page, plan and credit management). Applied on every register/login; only grants, never revokes. |
| `CRYPTO_BTC_ADDRESS` / `CRYPTO_USDT_TRC20_ADDRESS` / `CRYPTO_TRX_ADDRESS` | Your **public** receiving addresses for plan payments (see "Crypto payments" below). A coin is only offered once its address is set. Never put a private key or seed phrase anywhere in the app. |
| `CRYPTO_QUOTE_MINUTES` | How long a BTC/TRX price quote holds before an unpaid order expires. Default 60. |
| `COINGECKO_API_KEY` | Optional free CoinGecko Demo key for steadier live BTC/TRX prices; the keyless API works without it. |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM`, `SMTP_USE_TLS` | Optional. When set, admins get an email for every payment waiting for confirmation. |
| `APP_BASE_URL` | Where the web app is served, for links in those emails. |
| `BILLING_ENFORCED` | Default `true`: every non-admin account needs a plan, spends one email credit per business email found (a person lookup that finds one, or a company search result that comes with one), and is held to its plan's limits (see "Plans & credits" below). Admins are never limited. `false` switches all limits off. |
| `SEARCH_PROVIDER` | `mock` \| `google_cse` \| `bing` \| `serpapi` \| `searchapi_io` \| `serper` |
| `GOOGLE_CSE_API_KEY` / `GOOGLE_CSE_ENGINE_ID` | Required for `google_cse`. Get from [Programmable Search Engine](https://programmablesearchengine.google.com/). Note: Google requires a billing account linked to the project before the API will serve requests at all, even within the free 100/day quota. |
| `BING_SEARCH_API_KEY` | Required for `bing`. Azure Cognitive Services Bing Search resource key — also requires a card on the Azure account. |
| `SERPAPI_API_KEY` | Required for `serpapi`. From [serpapi.com](https://serpapi.com/). |
| `SEARCHAPI_IO_API_KEY` | Required for `searchapi_io`. From [searchapi.io](https://www.searchapi.io/) — free tier (100 requests) with no credit card required at signup, the least friction of the four if you want real results without linking payment info. |
| `SERPER_API_KEY` | Required for `serper`. From [serper.dev](https://serper.dev/) — Google results, 2,500 free queries with no credit card, then prepaid credit packs (the lowest cost per query of the providers here). |
| `HUNTER_IO_API_KEY` | Optional. From [hunter.io](https://hunter.io/) — enriches a "paste a LinkedIn profile link" preview with a verified business email for that specific person, once a company domain is confirmed. Everything else works without it. |
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

For a real deployment — managed Postgres, a signing key, migrations as a
release step, backups and the post-deploy checks — see
[`docs/DEPLOY.md`](docs/DEPLOY.md). `render.yaml` in the repo root is a
working blueprint for that setup.

---

## Running Tests

```bash
source venv/bin/activate
python -m pytest tests/ -v
```

348 tests, covering:

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

### Browser tests

Click-through tests for the frontend — the marketing pages, the in-app
tools, checkout and the admin payment review — with every `/api` call
mocked in the browser, so a run never touches the database or spends
credits. They need the Vite dev server running:

```bash
cd frontend
npm run dev        # in one terminal
npm run test:e2e   # in another
```

See [`frontend/e2e/README.md`](frontend/e2e/README.md) for the browser
requirements and the two environment variables that point the runner at a
different server or Chromium.

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/health` | Liveness check — one of only three endpoints that work without a logged-in user, with `/api/auth/register` and `/api/auth/login`. |
| `POST` | `/api/auth/register` | Create an account. Body: `email`, `password` (8+ chars), `full_name` (optional). Returns a bearer token + the new user. |
| `POST` | `/api/auth/login` | Body: `email`, `password`. Returns a bearer token + the user. |
| `GET` | `/api/auth/me` | The current logged-in user, from the `Authorization: Bearer <token>` header. |
| `POST` | `/api/auth/change-password` | *(logged in)* Body: `current_password`, `new_password` (8+ chars). Ends every other session; returns a fresh token for this one. |
| `POST` | `/api/auth/revoke-sessions` | *(logged in)* "Sign out other devices" — every token issued before now stops working. Returns a fresh token for the caller. |
| `POST` | `/api/discover` | Run a discovery job. Body: region, country, city, industry, activity, products[], keywords[], limit, `include_social_search`, `include_b2b_directories` (Phase 5/6, both default `false`). **Preview only — nothing is saved.** Returns deduplicated (in-memory only) candidates, each scored and flagged `already_saved`/`existing_company_id` against your saved companies. |
| `POST` | `/api/discover-url` | "Paste a link" quick lookup — body: `{"url": "..."}`. For a company website, fetches that one page (+ its Contact page if found) and extracts name/description/contact/social/emails/phones the same way discovery enrichment does. For a personal LinkedIn profile URL (`linkedin.com/in/...`), the page itself is login-gated and never fetched — instead it looks up whatever public search-engine snippet exists for it and returns `contact_person_name`/`contact_person_title` alongside the company it mentions, if any, plus a business email if `HUNTER_IO_API_KEY` is configured and finds a confident match. **Preview only — nothing is saved.** Returns `422` with a clear message if nothing usable was found. |
| `POST` | `/api/companies/save` | Persist one previewed candidate — the body is the same object `/discover` or `/discover-url` returned for that row. Creates a new company, or merges into an existing match (dedup is the same logic either way). |
| `POST` | `/api/companies/save-bulk` | Persist several previewed candidates at once — body: `{"companies": [...]}` (raw items from a `/discover` response, up to 200). Returns the saved companies plus `new_count`/`duplicate_count`. |
| `GET` | `/api/companies` | List companies. Filters: `country`, `region`, `industry`, `product`, `min_relevance`, `min_lead_score`, `has_email`, `has_phone`, `has_exported`, `search`; pagination: `page`, `page_size`. |
| `GET` | `/api/companies/export` | Export every company matching the same filters as CSV or XLSX (`format=csv\|xlsx`, capped at 5000 rows). Stamps `exported_at` on each exported company. |
| `GET` | `/api/emails` | List extracted emails across every company. Filters: `search`, `is_valid`, `country`, `industry`, `has_exported`; pagination: `page`, `page_size`. |
| `GET` | `/api/emails/export` | Export matching emails as CSV or XLSX. Stamps `exported_at` on each exported email. |
| `GET` | `/api/companies/{id}` | Full company profile — sources, contact page, social profiles, emails, phones, lead-score breakdown. |
| `GET` | `/api/searches` | Search/discovery job history, paginated. |
| `POST` | `/api/saved-searches` | Create a scheduled search (`frequency`: `daily`\|`weekly`). |
| `GET` | `/api/saved-searches` | List saved searches. |
| `PATCH` | `/api/saved-searches/{id}?is_active=` | Pause/resume a saved search. |
| `DELETE` | `/api/saved-searches/{id}` | Delete a saved search. |
| `POST` | `/api/saved-searches/run-due` | Manually run whichever saved searches are currently due (no worker required). |
| `POST` | `/api/contacts/bulk-lookup` | Look up to 25 people at once — each item is `{"url": "linkedin.com/in/..."}` or `{"full_name", "company_name"}`. **Preview only.** |
| `POST` | `/api/emails/verify` | Email Verifier — body: `{"emails": [...]}` (up to 500). Grades each address `deliverable`/`undeliverable`/`risky`/`unknown` with a `reason`. Format, throwaway domains and known typos are decided locally; MX lookups are grouped by domain and run concurrently under a whole-batch budget; mailbox-level confirmation depends on `EMAIL_VERIFY_PROVIDER` (the default `mx` has none, so nothing is graded `deliverable`). No message is ever sent to the address. |
| `GET` | `/api/billing/me` | The current user's plan, credit balance, renewal date, paid-until date, today's search count and plan limits. |
| `GET` | `/api/billing/payment-methods` | Coins accepted for plans (those with a receiving address configured). |
| `POST` | `/api/billing/orders` | Start paying for a plan — body: `plan`, `credits_per_month`, `billing_period` (`monthly`\|`yearly`), `currency` (`BTC`\|`USDT_TRC20`\|`TRX`). Returns the address and exact amount; the price comes from `app/services/plans.py`. |
| `GET` | `/api/billing/orders` / `/api/billing/orders/{id}` | The current user's payment orders. |
| `POST` | `/api/billing/orders/{id}/paid` | "I have paid" — no body needed; optional `{"tx_hash"}`. Notifies admins. A transaction ID, when given, can only be used once. |
| `POST` | `/api/billing/orders/{id}/cancel` | Cancel an order that hasn't been marked paid. |
| `GET` | `/api/admin/payments` | *(admin)* Payment orders, optionally `?status=submitted`. |
| `GET` | `/api/admin/payments/pending-count` | *(admin)* How many payments are waiting for confirmation. |
| `POST` | `/api/admin/payments/{id}/confirm` | *(admin)* Confirm a checked payment — starts, renews or changes the customer's plan. Optional body: `{"note", "tx_hash"}` to record the transaction you matched. |
| `POST` | `/api/admin/payments/{id}/reject` | *(admin)* Reject a payment — body: `{"note"}`, shown to the customer. |
| `GET` | `/api/admin/users` | *(admin)* Every account, with its plan and credit balance. |
| `PATCH` | `/api/admin/users/{id}` | *(admin)* Block/unblock — body: `{"is_active": bool}`. |
| `POST` | `/api/admin/users/{id}/revoke-sessions` | *(admin)* End every session for an account without blocking it — for a login that may have been stolen. They can log straight back in. |
| `PUT` | `/api/admin/users/{id}/subscription` | *(admin)* Put a user on a plan — body: `{"plan", "credits_per_month"}`. A new plan grants its first month of credits immediately. |
| `DELETE` | `/api/admin/users/{id}/subscription` | *(admin)* Remove a user's plan and remaining credits. |
| `POST` | `/api/admin/users/{id}/credits` | *(admin)* Add or remove credits — body: `{"amount", "note"}`. The balance never goes below zero. |

All request/response bodies are validated with Pydantic; invalid input
returns `422` with a structured error body. Unexpected server errors return
a generic `500`/`502` message — full details go to the server logs only,
never to the client.

**Authentication.** Every endpoint except `/api/health`,
`/api/auth/register` and `/api/auth/login` requires
`Authorization: Bearer <token>`; a missing/invalid/expired token gets a
`401`. Each account's saved companies, emails, search history and scheduled
searches are private to it — every query is scoped to the signed-in user, and
duplicate detection only matches against that user's own companies. Sessions
are stateless JWTs (`ACCESS_TOKEN_EXPIRE_MINUTES`, default 1 week), but they
are not unrevokable: each token carries the account's `token_version` and is
checked against the database on every request, so a password change, "sign
out other devices", or an admin ending an account's sessions invalidates
every token issued before it.

**Plans & credits.** With `BILLING_ENFORCED=true` (the default), a new
account has no plan and can't use the lookup tools until an admin assigns
one on the Users page — there's no online checkout yet. Plans and their
limits are defined in `app/services/plans.py` (mirroring the public pricing
page): one email credit is spent per business email found — for a person
lookup (LinkedIn profile, name + company, or a bulk line) that returns one,
and for each result of a company search that comes with one (scheduled runs
included). Results without a business email are free, as are website
extraction and the Email Verifier; each plan caps company discovery
searches per day and results per search, and bulk lookup and CSV/Excel
export need Professional or Enterprise. Credits are granted per
monthly period and roll over — renewal happens the next time the account is
used. Every change is recorded in the `credit_transactions` table. Admins
are never limited. Scheduled searches are limited per plan too (none on
Basic, 5 on Professional, unlimited on Enterprise), and stop running while
their owner's plan doesn't include them.

**Crypto payments.** Customers pay for plans in BTC, USDT (TRC-20) or TRX,
with no payment processor involved:

1. On the Pricing page a customer picks a plan, credit tier and billing
   period, then a coin. Checkout creates an order showing your receiving
   address (from `CRYPTO_*_ADDRESS`) and the exact amount — USDT at 1:1 with
   the dollar, BTC and TRX from a live CoinGecko price held for
   `CRYPTO_QUOTE_MINUTES`.
2. The customer sends the coins and clicks **I have paid** — nothing to
   type. Every order carries a reference the app generates (`PL-…`), which
   identifies it in the app; BTC and TRC-20 transfers have no memo field, so
   it never travels with the coins. A transaction ID is optional, from
   either side. Admins see a badge on **Payments** (and get an email if SMTP
   is configured).
3. An admin opens the payment and checks the receiving address on a block
   explorer (mempool.space for BTC, tronscan.org for TRON): at least the
   amount shown should have arrived, on the right network, around the time
   the order was marked paid. **Confirm payment** starts, renews or changes
   the plan for 1 or 12 months, and can record the transaction ID that was
   matched; **Reject** records a note the customer sees.

Paid plans end when their paid period does (credits stop renewing and the
tools are blocked until the customer pays again); nothing renews
automatically. Plans an admin assigns on the Users page have no end date.
Confirming payments is manual, so only confirm what you've verified on the
explorer — the app never holds wallet keys and can't see your wallet.

---

## Security & Data Collection Policy

- **No credential/access-control bypass.** PetroLead never bypasses logins,
  CAPTCHAs, or anti-bot systems, and never scrapes private profiles or
  personal data. `SocialSource`/`B2BSource` (Phase 5/6, opt-in) only ever
  read a search provider's own already-public result snippets via `site:`
  queries — they never log into, crawl, or fetch a page from LinkedIn,
  Facebook, or any B2B directory directly, which is why every candidate
  they produce keeps `website=None`. A full integration (richer data via
  an approved platform API partnership; fetching individual B2B listing
  pages once a directory's terms of service are reviewed) remains future
  work — see [Future Development Phases](#future-development-phases).
  Phase 2's contact/social-link discovery is separate and narrower: it only
  follows links a company published on its own public homepage.
- **Emails/phones are extracted, never contacted.** Phase 3/4 "validation"
  is a public MX-record DNS lookup (email) and structural/format checking
  via libphonenumber (phone) — PetroLead never sends an email or places a
  call to verify a lead.
- **Password guessing is rate limited.** Every client address gets
  `AUTH_RATE_LIMIT_PER_MINUTE` attempts at `/auth/login` and `/auth/register`
  and `RATE_LIMIT_PER_MINUTE` elsewhere, answered with a `429` and a
  `Retry-After` beyond that. Counting is per process and in memory, so with
  two web workers the real limit is double the configured one — it slows
  guessing down, it is not a billing control. Behind a load balancer set
  `TRUST_PROXY_HEADERS=true`, or every request looks like it came from the
  balancer; leave it off otherwise, since a caller can forge the header and
  hand themselves a fresh allowance.
- **The app won't fetch private addresses.** `POST /api/discover-url` takes
  a URL the caller chose, so `app/core/net_guard.py` resolves the hostname
  first and refuses loopback, RFC1918, link-local and reserved addresses —
  which is what stops it being used to read a cloud metadata service
  (`169.254.169.254`) or the API's own admin endpoints. Redirects are
  re-checked, because a public URL can redirect to a private one. The one
  hole left is DNS rebinding between our check and the socket's own lookup;
  closing it needs the connection pinned to the validated address.
- **A login costs the same whether or not the account exists.** The
  password is checked against a throwaway hash for an unknown address, so
  response time can't be used to enumerate which emails are registered.
- **The API describes itself in development only.** `/docs`, `/redoc` and
  `/openapi.json` are removed outside development (`DOCS_ENABLED` overrides
  it either way).
- **Hardening headers on every response.** `nosniff`, `DENY` framing, a
  `strict-origin-when-cross-origin` referrer policy, an empty CSP (every
  response is JSON), and HSTS outside development.
- **Sessions can be ended before they expire.** Tokens are stateless and
  last a week, so each one is stamped with the account's `token_version`
  and checked against the database on every request. Bumping that version
  invalidates every token issued before it: changing a password does it
  automatically, `POST /api/auth/revoke-sessions` does it on request ("sign
  out other devices"), and `POST /api/admin/users/{id}/revoke-sessions`
  lets an admin end a compromised account's sessions *without* blocking the
  account — the customer just logs in again. Each of these returns a fresh
  token so the caller isn't signed out of the device they're using. Tokens
  minted before this existed carry no version and are refused rather than
  assumed to be version zero.
- **The app refuses to start on the development signing key.** Any
  `APP_ENV` other than `development` with the default `SECRET_KEY` is a
  hard startup failure, not a warning — that key is published in this repo,
  and anyone holding it can mint a session token for any account.
- **Secrets stay in `.env`.** No API key is hard-coded; `.env` is
  git-ignored and `.env.example` ships placeholders only.
- **Authentication.** Passwords are hashed with bcrypt (salted per-user,
  never stored or logged in plain text); login sessions are signed JWTs
  (`SECRET_KEY`) carried as a Bearer token. Every endpoint except
  `/api/health` and `/api/auth/*` requires one. The shipped `SECRET_KEY`
  default is intentionally insecure and only for zero-config local dev —
  the app logs a startup warning if it's still in use outside
  `APP_ENV=development`.
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
| 5 | Social/company profile discovery via permitted sources & compliant APIs | **Partial** — search-engine `site:` discovery only (opt-in) |
| 6 | B2B source connectors (`B2BSource`) | **Partial** — search-engine `site:` discovery only (opt-in) |
| 7 | Lead scoring | **Implemented** |
| 8 | Excel/CSV export | **Implemented** |
| 9 | Advanced search & filtering | **Implemented** |
| 10 | Automated lead monitoring & scheduled searches | **Implemented** (needs a running Celery worker for true automation — see above) |

Phases 5 and 6 are partially implemented: `SocialSource` and `B2BSource`
(`app/discovery/sources.py`) run `site:linkedin.com`/`site:tradekey.com`/etc.
queries through your configured `SearchProvider` — enabled per-request via
`include_social_search`/`include_b2b_directories` (both default `false`,
since they add extra search-provider calls that cost quota/money on real
providers). This surfaces real candidates using only a search engine's own
public index, but doesn't fetch or parse the platform/directory's own
pages — every candidate they produce keeps `website=None` specifically to
guarantee that. A full implementation still needs something this app can't
obtain on its own: an approved API partnership for LinkedIn/Facebook company
data, and each B2B directory's terms of service reviewed before fetching an
individual listing page (scraping many of them outright violates those
terms). Once that access exists, extending either connector to also parse
a fetched page is additive — no other part of the app needs to change.

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
- **Emails are finalized on first extraction.** Once a company has at
  least one email on file, re-discovering it (a later search that
  dedup-matches the same company) never re-adds, re-validates, or
  replaces its emails — they're stable across repeat searches instead of
  being re-extracted every time. Phones aren't finalized this way; they
  still accumulate newly-seen numbers on each rediscovery.
- **Export tracking.** Exporting companies or emails (CSV/XLSX) stamps
  `exported_at` on each exported record — filter on `has_exported` to
  find fresh, not-yet-exported leads versus ones already sent out.
  Re-exporting just bumps the timestamp; nothing is ever excluded from
  being exported again.
- **Mock search provider.** With no real `SEARCH_PROVIDER` configured, all
  discovered companies — including their contact page, social links,
  emails, and phone numbers — are synthetic, clearly labeled `[MOCK]` /
  `is_mock: true`, and deterministically derived from the same fake mock
  domain. Real (non-mock) companies only ever get contact/email/phone data
  that was literally present in their own page's markup. Configure
  `google_cse`, `bing`, or `serpapi` (with the corresponding API key) to
  discover real companies.
