# Browser tests

Click-through tests for the whole frontend: the marketing pages, the app
tools, checkout and the admin payment review. Every `/api` call is mocked
inside the browser, so a run never touches the database, spends credits or
calls a search provider — but it does need the Vite dev server running,
because it drives the real React app.

```bash
npm run dev          # in one terminal
npm run test:e2e     # in another
```

A run prints one line per test and exits non-zero if any fail.

## Requirements

`playwright-core` drives a Chromium that it does **not** download for you.
If you have Playwright's browsers installed already the default path is
found automatically; otherwise install them once:

```bash
npx playwright install chromium
```

Two environment variables cover everything else:

| Variable | Default | Use it when |
| --- | --- | --- |
| `E2E_BASE_URL` | `http://localhost:5173` | The dev server is on another port, or you're testing a deployed preview. |
| `E2E_CHROMIUM` | Playwright's `chromium_headless_shell` path | Chromium lives somewhere else, or you want to run against a system browser. |

On a bare Linux box Chromium also needs `libnss3`, `libnspr4` and
`libasound2`. If a run fails with a missing `.so`, install them:

```bash
sudo apt-get install -y libnss3 libnspr4 libasound2t64
```

## Writing a test

Tests are plain functions registered with `test(name, fn)`; there is no
framework to learn. `mockApi(page)` installs the shared `/api` handlers —
extend those fixtures rather than adding per-test network stubs, so every
test sees one consistent fake backend.
