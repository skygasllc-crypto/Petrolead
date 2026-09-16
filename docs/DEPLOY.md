# Deploying PetroLead

This describes a managed-platform deploy: four services (API, worker,
Postgres, cache) plus the static frontend. `render.yaml` in the repo root is
a working Render blueprint; Railway and Fly.io need the same four pieces
described in their own config format, and the environment variables below
are what actually matter on any of them.

Nothing here requires taking the app down, except the one-off data move in
step 2.

---

## 1. Before the first deploy

**Generate a signing key and keep it.**

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

`SECRET_KEY` signs login sessions. Changing it later logs every user out, so
generate it once and treat it as permanent. The app **refuses to start** with
the development default whenever `APP_ENV` is anything but `development` —
that default is in this public repo, so anyone could otherwise mint a session
token for any account, including an admin's.

**Decide what `ADMIN_EMAILS` contains.** It is a comma-separated list, applied
on every register and login, and it only ever grants admin rights — never
revokes them. Get it right the first time; removing an address later does not
demote an account that already has the flag.

**Have the wallet addresses ready.** `CRYPTO_BTC_ADDRESS`,
`CRYPTO_USDT_TRC20_ADDRESS`, `CRYPTO_TRX_ADDRESS` are **public receiving
addresses only**. A private key or seed phrase must never be set here, in the
repo, or in a platform dashboard — the app never needs one, because payments
are confirmed by hand against a block explorer. A coin is only offered at
checkout once its address is set, so an unset address simply hides that
option.

---

## 2. Moving the existing data

If you have been running locally, real accounts, subscriptions, credit
balances and payment orders are in the dev SQLite file
(`~/.petrolead-dev/petrolead.db` by default). A fresh Postgres starts empty:
deploying without moving that data means existing customers lose their plans
and paid periods.

Take a copy of the SQLite file first:

```bash
cp ~/.petrolead-dev/petrolead.db db-backup/petrolead-before-production.db
```

Then, with the production `DATABASE_URL` exported locally:

```bash
alembic upgrade head          # create the schema on Postgres
pgloader sqlite:///$HOME/.petrolead-dev/petrolead.db "$DATABASE_URL"
```

`pgloader` is the least painful route for a database this size. Whatever you
use, afterwards check the three tables that represent money and access:

```sql
SELECT count(*) FROM users;
SELECT email, plan, credits_balance, paid_until FROM subscriptions
  JOIN users ON users.id = subscriptions.user_id;
SELECT reference, status, currency, amount_crypto FROM payment_orders;
```

Every paying customer must come out the other side with the same plan,
balance and `paid_until`. If they don't, fix it before pointing DNS at the
new deploy — not after.

---

## 3. Environment variables

Set these on the API service. The worker needs the same values for
`SECRET_KEY`, `DATABASE_URL`, `REDIS_URL` and the search-provider keys.

| Variable | Required | Notes |
| --- | --- | --- |
| `APP_ENV` | yes | `production`. Makes `SECRET_KEY` mandatory. |
| `DEBUG` | yes | `false`. |
| `SECRET_KEY` | yes | 64 hex chars from step 1. Never reuse the dev value. |
| `DATABASE_URL` | yes | From the managed database. A `postgres://` URL is rewritten to `postgresql+psycopg://` automatically. |
| `REDIS_URL` | worker only | Celery broker. The API runs without it. |
| `RUN_MIGRATIONS_ON_STARTUP` | yes | `false` in production — see step 4. |
| `CORS_ORIGINS` | yes | Every origin the SPA is served from, comma-separated, e.g. `https://petrolead.com,https://www.petrolead.com`. A missing origin means every API call fails in the browser with no useful error. |
| `APP_BASE_URL` | yes | Public URL of the frontend. Used for links in admin payment emails. |
| `ADMIN_EMAILS` | yes | Who can confirm payments and manage accounts. |
| `BILLING_ENFORCED` | yes | `true` in production. `false` disables all plan and credit limits for everyone. |
| `SEARCH_PROVIDER` + its key | yes | Otherwise the app serves clearly-labelled mock data. |
| `HUNTER_IO_API_KEY` | optional | Person-email enrichment. See `docs/outreach/email-provider-permission.md` before relying on it commercially. |
| `CRYPTO_*_ADDRESS` | for payments | Public receiving addresses. Unset coins are hidden at checkout. |
| `COINGECKO_API_KEY` | optional | Steadier BTC/TRX quotes; the keyless tier is rate-limited. |
| `SMTP_*` | optional | Without it, the Payments badge in the app is the only notification that a customer paid. |
| `VITE_API_BASE_URL` | frontend build | The API's base URL **including `/api`**, e.g. `https://petrolead-api.onrender.com/api`. Baked into the bundle at build time and publicly visible — never a secret. Leave unset only if the SPA and API share an origin. |

---

## 4. Migrations

`RUN_MIGRATIONS_ON_STARTUP=true` is convenient for one local process and
wrong for production: several web workers would race to migrate the same
database at once. Run migrations once per release instead, before new
instances take traffic. On Render that is `preDeployCommand: alembic upgrade
head` (already in `render.yaml`); elsewhere it's a release command or a
manual `alembic upgrade head`.

Migrations here are additive, but check `alembic/versions/` before deploying
one that drops or rewrites a column, and take a backup first (step 5).

---

## 5. Backups

Managed platforms snapshot the database for you. That covers hardware
failure; it does not cover an account suspension, a billing lapse or someone
deleting the database — those take the snapshots too. Keep one copy
somewhere the platform doesn't control:

```bash
DATABASE_URL=postgresql://... ./scripts/backup-db.sh /var/backups/petrolead
```

Run it from cron on a machine that isn't the database host. Then actually
restore one into a scratch database — an untested backup is a guess:

```bash
gunzip -c petrolead-YYYYmmdd-HHMMSS.sql.gz | psql "$SCRATCH_DATABASE_URL"
```

---

## 6. After deploying

```bash
curl https://<api-host>/api/health     # {"status":"ok","env":"production"}
```

Then, in a browser, confirm the parts that silently break when a variable is
missing:

1. Load the site, open the network tab, sign in. A failing API call here is
   almost always `CORS_ORIGINS` or `VITE_API_BASE_URL`.
2. Refresh directly on `/pricing`. A 404 means the SPA rewrite rule is
   missing.
3. Start a checkout. The coins you configured should appear with a live
   price and a QR code.
4. Sign in as an admin address and open **Payments**.
5. Create a scheduled search and check the worker's log picks it up within
   15 minutes — that's the only way to know the worker is really running.

## 7. Rolling back

Redeploy the previous image. If the release included a migration, a rollback
is **not** automatic: `alembic downgrade -1` must be run deliberately, and
only after checking what that migration's `downgrade()` actually drops. This
is why step 5 exists.
