// Browser click-through tests for the PetroLead frontend.
// Runs against the Vite dev server with every /api call mocked, so no real
// lookups, credits or database writes happen.
import { chromium } from "playwright-core";

// Point these at a running dev server / an installed browser when they
// aren't in the default place — see e2e/README.md.
const BASE = process.env.E2E_BASE_URL || "http://localhost:5173";
const EXECUTABLE =
  process.env.E2E_CHROMIUM ||
  `${process.env.HOME}/.cache/ms-playwright/chromium_headless_shell-1234/chrome-headless-shell-linux64/chrome-headless-shell`;

const results = [];
async function test(name, fn) {
  try {
    await fn();
    results.push([true, name]);
    console.log(`PASS  ${name}`);
  } catch (err) {
    results.push([false, name]);
    console.log(`FAIL  ${name}\n      ${String(err.message).split("\n").slice(0, 4).join("\n      ")}`);
  }
}
function assert(cond, message) {
  if (!cond) throw new Error(message);
}
async function expectVisible(locator, what) {
  await locator.first().waitFor({ state: "visible", timeout: 5000 }).catch(() => {
    throw new Error(`expected visible: ${what}`);
  });
}
async function expectUrl(page, pathWithQueryOrHash, what) {
  await page.waitForURL((u) => `${u.pathname}${u.search}${u.hash}` === pathWithQueryOrHash, { timeout: 5000 }).catch(() => {
    throw new Error(`expected URL ${pathWithQueryOrHash} (${what}), got ${page.url()}`);
  });
}
// Waits (up to 5s) for an element to be rendered and scrolled into view —
// on a cross-page link the target page can take a moment to render first.
async function expectInViewport(page, selector) {
  await page
    .waitForFunction(
      (sel) => {
        const el = document.querySelector(sel);
        if (!el) return false;
        const r = el.getBoundingClientRect();
        return r.top < window.innerHeight && r.bottom > 0 && r.top >= -5;
      },
      selector,
      { timeout: 5000 },
    )
    .catch(() => {
      throw new Error(`${selector} not scrolled into view`);
    });
}

const USER = { id: "u1", email: "qa@petrolead.example", full_name: "QA Tester", is_admin: false, is_active: true };
const BILLING = {
  exempt: false,
  plan: "professional",
  plan_name: "Professional",
  credits_balance: 1999,
  credits_per_month: 2000,
  renews_at: "2026-10-15T00:00:00",
  discovery_searches_today: 3,
  discovery_searches_per_day: 50,
  max_results_per_search: 50,
  bulk_lookup: true,
  export: true,
  scheduled_searches: 5,
  paid_until: "2027-09-16T00:00:00",
  expired: false,
};
const METHODS = [
  { currency: "BTC", symbol: "BTC", name: "Bitcoin", network: "Bitcoin", address: "bc1qexampleaddress" },
  { currency: "USDT_TRC20", symbol: "USDT", name: "Tether (USDT)", network: "TRON (TRC-20)", address: "TExampleUsdtAddress" },
];
const ORDER = {
  id: "order-1",
  reference: "PL-TEST1234",
  plan: "professional",
  plan_name: "Professional",
  credits_per_month: 2000,
  billing_period: "yearly",
  amount_usd: "348.00",
  currency: "USDT_TRC20",
  coin_symbol: "USDT",
  coin_name: "Tether (USDT)",
  network: "TRON (TRC-20)",
  pay_address: "TExampleUsdtAddress",
  amount_crypto: "348.00",
  usd_rate: null,
  status: "awaiting_payment",
  tx_hash: null,
  explorer_url: null,
  admin_note: null,
  created_at: "2026-09-16T10:00:00",
  expires_at: "2099-01-01T00:00:00",
  submitted_at: null,
  reviewed_at: null,
};

const basePreview = {
  source: "fake",
  source_url: null,
  is_mock: false,
  relevance_score: 80,
  lead_score: 70,
  country: null,
  city: null,
  industry: null,
  products: [],
  description: null,
  already_saved: false,
  existing_company_id: null,
  contact_person_name: null,
  contact_person_title: null,
  contact_page_url: null,
  social_profiles: [],
  emails: [],
  phones: [],
};
const PERSON = {
  ...basePreview,
  company_name: "Gulfstar Refining",
  website: "https://gulfstar.example",
  contact_person_name: "Amira Haddad",
  contact_person_title: "Procurement Director",
  social_profiles: [{ platform: "linkedin", url: "https://linkedin.com/in/amira-haddad" }],
  emails: [{ email: "a.haddad@gulfstar.example", is_valid: true }],
};
const COMPANY = {
  ...basePreview,
  company_name: "Nordic Bunker AS",
  website: "https://nordicbunker.example",
  contact_page_url: "https://nordicbunker.example/contact",
  social_profiles: [{ platform: "facebook", url: "https://facebook.com/nordicbunker" }],
  emails: [{ email: "sales@nordicbunker.example", is_valid: true }],
  phones: [{ phone: "+47 22 00 00 00", is_valid: true }],
};

async function mockApi(page, { loggedIn, admin = false }) {
  const calls = [];
  const orderState = {
    order: null,
    adminOrders: admin
      ? [{ ...ORDER, status: "submitted", tx_hash: "c".repeat(64), explorer_url: `https://tronscan.org/#/transaction/${"c".repeat(64)}`, customer_email: "buyer@example.com", paid_after_quote_expired: false, submitted_at: "2026-09-16T10:05:00" }]
      : [],
  };
  // Match on the request path — a "**/api/**" glob would also catch Vite's
  // /src/api/client.js module and break the app before it renders.
  await page.route((url) => url.pathname.startsWith("/api/"), async (route) => {
    const req = route.request();
    const url = new URL(req.url());
    const path = url.pathname.replace(/^\/api/, "");
    const body = req.postDataJSON?.() ?? null;
    calls.push({ method: req.method(), path, body });
    const json = (status, data) => route.fulfill({ status, contentType: "application/json", body: JSON.stringify(data) });

    if (path === "/auth/me") return loggedIn ? json(200, { ...USER, is_admin: admin }) : json(401, { detail: "Not authenticated" });
    if (path === "/billing/me") return json(200, BILLING);
    if (path === "/billing/payment-methods") return json(200, METHODS);
    if (path === "/billing/orders" && req.method() === "GET") return json(200, orderState.order ? [orderState.order] : []);
    if (path === "/billing/orders" && req.method() === "POST") {
      orderState.order = { ...ORDER, plan: body.plan, credits_per_month: body.credits_per_month, billing_period: body.billing_period };
      return json(200, orderState.order);
    }
    if (path === `/billing/orders/${ORDER.id}`) return json(200, orderState.order ?? ORDER);
    if (path === `/billing/orders/${ORDER.id}/paid`) {
      const txHash = body?.tx_hash ?? null;
      orderState.order = { ...orderState.order, status: "submitted", tx_hash: txHash, submitted_at: "2026-09-16T10:05:00", explorer_url: txHash ? `https://tronscan.org/#/transaction/${txHash}` : null };
      return json(200, orderState.order);
    }
    if (path === "/admin/payments/pending-count") return json(200, { count: orderState.adminOrders.filter((o) => o.status === "submitted").length });
    if (path === "/admin/payments") return json(200, orderState.adminOrders.filter((o) => !url.searchParams.get("status") || o.status === url.searchParams.get("status")));
    if (path.startsWith("/admin/payments/") && path.endsWith("/confirm")) {
      orderState.adminOrders = orderState.adminOrders.map((o) => ({ ...o, status: "confirmed" }));
      return json(200, orderState.adminOrders[0]);
    }
    if (path === "/discover-url") {
      if (body.url.includes("nobody")) return json(422, { detail: "No business email found for Nobody — skipped." });
      return json(200, body.url.includes("linkedin.com/in/") ? PERSON : COMPANY);
    }
    if (path === "/contacts/bulk-lookup") {
      return json(200, {
        results: body.items.map((item, i) =>
          i === 0
            ? { success: true, error: null, preview: PERSON, input_url: item.url ?? null, input_full_name: item.full_name ?? null, input_company_name: item.company_name ?? null }
            : { success: false, error: "No business email found — skipped.", preview: null, input_url: item.url ?? null, input_full_name: item.full_name ?? null, input_company_name: item.company_name ?? null },
        ),
        succeeded_count: 1,
        failed_count: body.items.length - 1,
      });
    }
    if (path === "/emails/verify") {
      // Stands in for a configured verification provider, so the deliverable
      // path — the one that matters — is what gets exercised.
      const verdictFor = (e) => {
        if (!e.includes("@")) return ["undeliverable", "invalid_format"];
        if (e.includes("dead")) return ["undeliverable", "no_mail_server"];
        return ["deliverable", "mailbox_confirmed"];
      };
      const res = body.emails.map((email) => {
        const [status, reason] = verdictFor(email);
        return {
          email,
          status,
          reason,
          syntax_valid: email.includes("@"),
          domain_accepts_mail: reason !== "invalid_format" ? reason !== "no_mail_server" : null,
        };
      });
      const count = (s) => res.filter((r) => r.status === s).length;
      return json(200, {
        results: res,
        deliverable_count: count("deliverable"),
        undeliverable_count: count("undeliverable"),
        risky_count: count("risky"),
        unknown_count: count("unknown"),
        mailbox_checks_available: true,
      });
    }
    if (path === "/companies/save") return json(200, { id: "c-123", company_name: body.company_name });
    return json(200, { items: [], total: 0, page: 1, page_size: 25 });
  });
  return calls;
}

const browser = await chromium.launch({ executablePath: EXECUTABLE, args: ["--no-sandbox"] });

async function newPage({ loggedIn = false, mobile = false, admin = false } = {}) {
  const context = await browser.newContext({
    viewport: mobile ? { width: 390, height: 844 } : { width: 1440, height: 900 },
    baseURL: BASE,
  });
  await context.grantPermissions(["clipboard-read", "clipboard-write"], { origin: BASE });
  if (loggedIn) await context.addInitScript(() => localStorage.setItem("petrolead_token", "test-token"));
  const page = await context.newPage();
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  page.on("console", (m) => m.type() === "error" && !/Failed to load resource/.test(m.text()) && errors.push(m.text()));
  const calls = await mockApi(page, { loggedIn, admin });
  page.on("dialog", (dialog) => dialog.accept());
  return { page, context, errors, calls };
}
function assertNoErrors(errors) {
  assert(errors.length === 0, `console/page errors: ${errors.join(" | ")}`);
}

// ---------- Public marketing pages ----------

await test("Product dropdown opens, closes on Escape and on outside click", async () => {
  const { page, context, errors } = await newPage();
  await page.goto("/");
  const header = page.locator("header");
  const productButton = header.getByRole("button", { name: "Product" });
  const menuItem = header.getByRole("link", { name: /Email Verifier/ });

  await productButton.click();
  assert((await productButton.getAttribute("aria-expanded")) === "true", "aria-expanded not true after click");
  await expectVisible(menuItem, "Email Verifier item in dropdown");
  await page.keyboard.press("Escape");
  assert((await menuItem.count()) === 0, "dropdown still open after Escape");

  await productButton.click();
  await expectVisible(menuItem, "dropdown reopened");
  await page.mouse.click(40, 600);
  assert((await menuItem.count()) === 0, "dropdown still open after outside click");
  assertNoErrors(errors);
  await context.close();
});

await test("Dropdown item navigates to its product page and scrolls to top", async () => {
  const { page, context, errors } = await newPage();
  await page.goto("/");
  await page.mouse.wheel(0, 1500);
  await page.locator("header").getByRole("button", { name: "Product" }).click();
  await page.locator("header").getByRole("link", { name: /Email Verifier/ }).click();
  await expectUrl(page, "/email-verifier", "Email Verifier page");
  await expectVisible(page.getByRole("heading", { level: 1, name: "Email Verifier" }), "Email Verifier h1");
  assert((await page.evaluate(() => window.scrollY)) < 5, "page not scrolled to top after navigation");
  assert((await page.locator("header").getByRole("link", { name: /Email Verifier/ }).count()) === 0, "dropdown stayed open after navigating");
  assertNoErrors(errors);
  await context.close();
});

await test("Every product page in the menu renders its heading", async () => {
  const { page, context, errors } = await newPage();
  const pages = [
    ["/company-search", "Company Search"],
    ["/linkedin-email-finder", "LinkedIn Email Finder"],
    ["/email-extractor", "Email Extractor"],
    ["/email-verifier", "Email Verifier"],
    ["/pricing", "Simple pricing that grows with your pipeline"],
  ];
  for (const [path, heading] of pages) {
    await page.goto(path);
    await expectVisible(page.getByRole("heading", { level: 1, name: heading }), `${path} h1`);
  }
  assertNoErrors(errors);
  await context.close();
});

await test("Header Pricing link and cross-page #features link", async () => {
  const { page, context, errors } = await newPage();
  await page.goto("/company-search");
  await page.locator("header").getByRole("link", { name: "Pricing" }).click();
  await expectUrl(page, "/pricing", "pricing page");
  await page.locator("header").getByRole("link", { name: "Features" }).click();
  await expectUrl(page, "/#features", "landing features section");
  await expectInViewport(page, "#features");
  assertNoErrors(errors);
  await context.close();
});

await test("Footer reaches the Terms and Privacy pages", async () => {
  const { page, context, errors } = await newPage();
  await page.goto("/pricing");

  await page.locator("footer").getByRole("link", { name: "Terms of Service" }).click();
  await expectUrl(page, "/terms", "terms page");
  await expectVisible(page.getByRole("heading", { name: "Terms of Service" }), "terms heading");

  await page.locator("footer").getByRole("link", { name: "Privacy Policy" }).click();
  await expectUrl(page, "/privacy", "privacy page");
  await expectVisible(page.getByRole("heading", { name: "Privacy Policy" }), "privacy heading");

  // The unfilled placeholders are meant to be impossible to miss — if this
  // ever stops matching, check it was filled in rather than deleted.
  await expectVisible(page.getByText("[LEGAL ENTITY NAME]").first(), "visible placeholder");

  assertNoErrors(errors);
  await context.close();
});

await test("Public pages set their own title and canonical; private pages are noindex", async () => {
  const { page, context, errors } = await newPage();

  await page.goto("/");
  const homeTitle = await page.title();
  assert(homeTitle.includes("PetroLead"), `home title was ${homeTitle}`);

  // The tags are written by an effect after mount, so wait for the value
  // rather than reading whatever index.html shipped with.
  await page.goto("/pricing");
  await page
    .waitForFunction(
      () =>
        document.querySelector('link[rel="canonical"]')?.getAttribute("href") ===
        "https://petrolead.org/pricing",
      { timeout: 5000 },
    )
    .catch(() => {
      throw new Error("canonical never became https://petrolead.org/pricing");
    });

  const pricingTitle = await page.title();
  assert(pricingTitle !== homeTitle, "every route shares one title");
  assert(/pricing/i.test(pricingTitle), `pricing title was ${pricingTitle}`);
  const robots = await page.getAttribute('meta[name="robots"]', "content");
  assert(/index/.test(robots) && !/noindex/.test(robots), `public robots was ${robots}`);

  // Nobody should reach the sign-in page from a search result.
  await page.goto("/login");
  await page
    .waitForFunction(
      () =>
        /noindex/.test(
          document.querySelector('meta[name="robots"]')?.getAttribute("content") || "",
        ),
      { timeout: 5000 },
    )
    .catch(() => {
      throw new Error("the login page never became noindex");
    });
  assert(
    (await page.locator('link[rel="canonical"]').count()) === 0,
    "the login page claims a canonical URL, which invites indexing",
  );

  assertNoErrors(errors);
  await context.close();
});

await test("Pricing: billing toggle, tier slider and comparison dropdown stay in sync", async () => {
  const { page, context, errors } = await newPage();
  await page.goto("/pricing");
  // Yearly by default: Basic $15 (was $20), Professional $29 (was $39), Enterprise $262 (was $349).
  for (const price of ["$15", "$29", "$262"]) {
    await expectVisible(page.getByText(price, { exact: true }), `yearly price ${price}`);
  }
  assert((await page.getByRole("heading", { name: "Free" }).count()) === 0, "Free plan still shown");

  await page.getByRole("button", { name: "Monthly" }).click();
  assert((await page.getByRole("button", { name: "Monthly" }).getAttribute("aria-pressed")) === "true", "Monthly not pressed");
  assert((await page.getByText("$29", { exact: true }).count()) === 0, "$29 still shown on monthly billing");
  for (const price of ["$20", "$39", "$349"]) {
    await expectVisible(page.getByText(price, { exact: true }), `monthly price ${price}`);
  }

  await page.getByRole("radio", { name: "5,000 credits", exact: true }).click();
  await expectVisible(page.getByText("$99", { exact: true }), "5K tier price $99");
  const proSelect = page.locator('select[aria-label="Professional credits per month"]');
  assert((await proSelect.inputValue()) === "1", `table select not synced to slider (value ${await proSelect.inputValue()})`);
  await expectVisible(page.getByText("5,000 / month"), "comparison row shows 5,000 / month");

  await proSelect.selectOption("3");
  await expectVisible(page.getByText("$199", { exact: true }), "25K tier price $199 after table select");
  assert((await page.getByRole("radio", { name: "25,000 credits", exact: true }).getAttribute("aria-checked")) === "true", "slider not synced to table select");
  assertNoErrors(errors);
  await context.close();
});

await test("Pricing: 'See all features' jumps to the comparison table", async () => {
  const { page, context, errors } = await newPage();
  await page.goto("/pricing");
  await page.getByRole("link", { name: "See all features" }).first().click();
  await expectInViewport(page, "#compare");
  assertNoErrors(errors);
  await context.close();
});

await test("FAQ accordion opens one answer at a time", async () => {
  const { page, context, errors } = await newPage();
  await page.goto("/linkedin-email-finder");
  const questions = page.locator("#faq button[aria-expanded]");
  assert((await questions.nth(0).getAttribute("aria-expanded")) === "true", "first FAQ not open by default");
  await questions.nth(1).click();
  assert((await questions.nth(1).getAttribute("aria-expanded")) === "true", "second FAQ did not open");
  assert((await questions.nth(0).getAttribute("aria-expanded")) === "false", "first FAQ did not close");
  await expectVisible(page.getByText("PetroLead never opens LinkedIn pages"), "second answer text");
  await questions.nth(1).click();
  assert((await questions.nth(1).getAttribute("aria-expanded")) === "false", "second FAQ did not collapse on second click");
  assertNoErrors(errors);
  await context.close();
});

await test("Logged-out CTAs go to sign-up; app pages redirect to login", async () => {
  const { page, context, errors } = await newPage();
  await page.goto("/linkedin-email-finder");
  await page.getByRole("link", { name: "Start finding emails" }).first().click();
  await expectUrl(page, "/register", "hero CTA → register");
  await page.goto("/email-finder");
  await expectUrl(page, "/login", "protected /email-finder → login");
  assertNoErrors(errors);
  await context.close();
});

await test("Mobile menu opens, navigates and closes; no sideways scrolling", async () => {
  const { page, context, errors } = await newPage({ mobile: true });
  for (const path of ["/", "/company-search", "/linkedin-email-finder", "/email-extractor", "/email-verifier", "/pricing"]) {
    await page.goto(path);
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    assert(overflow <= 1, `${path} scrolls sideways by ${overflow}px at 390px wide`);
  }
  await page.goto("/");
  const toggle = page.getByRole("button", { name: "Open menu" });
  await toggle.click();
  const item = page.locator("header").getByRole("link", { name: "Email Extractor" });
  await expectVisible(item, "mobile menu item");
  await item.click();
  await expectUrl(page, "/email-extractor", "mobile menu navigation");
  assert((await page.getByRole("button", { name: "Close menu" }).count()) === 0, "mobile menu still open after navigating");
  assertNoErrors(errors);
  await context.close();
});

// ---------- Logged-in app ----------

await test("Logged-in marketing CTA opens the app tool", async () => {
  const { page, context, errors } = await newPage({ loggedIn: true });
  await page.goto("/email-verifier");
  await page.getByRole("link", { name: "Verify emails" }).first().click();
  await expectUrl(page, "/verify-emails", "CTA → app verifier");
  assertNoErrors(errors);
  await context.close();
});

await test("Email Finder › LinkedIn: validates the link, finds the email, saves", async () => {
  const { page, context, errors, calls } = await newPage({ loggedIn: true });
  await page.goto("/email-finder");
  assert((await page.getByRole("tab", { name: "LinkedIn profile" }).getAttribute("aria-selected")) === "true", "LinkedIn tab not selected by default");

  const input = page.getByLabel("LinkedIn profile link");
  await input.fill("https://gulfstar.example");
  await page.getByRole("button", { name: "Find email" }).click();
  await expectVisible(page.getByText("Paste a LinkedIn profile link"), "hint for a non-LinkedIn link");
  assert(!calls.some((c) => c.path === "/discover-url"), "API called for an invalid LinkedIn link");

  await input.fill("linkedin.com/in/amira-haddad");
  await page.getByRole("button", { name: "Find email" }).click();
  await expectVisible(page.getByText("a.haddad@gulfstar.example"), "found email");
  const call = calls.find((c) => c.path === "/discover-url");
  assert(call?.body.url === "https://linkedin.com/in/amira-haddad", `URL not normalized with https: ${call?.body.url}`);
  await expectVisible(page.getByText("Procurement Director at Gulfstar Refining"), "title at company");

  await page.getByRole("button", { name: "Save to companies" }).click();
  await expectVisible(page.getByRole("link", { name: "Saved — view company" }), "saved state");

  await input.fill("linkedin.com/in/nobody");
  await page.getByRole("button", { name: "Find email" }).click();
  await expectVisible(page.getByRole("alert").filter({ hasText: "No business email found for Nobody" }), "API error shown");
  assertNoErrors(errors);
  await context.close();
});

await test("Email Finder › tabs update the URL; website, name and bulk lookups", async () => {
  const { page, context, errors } = await newPage({ loggedIn: true });
  await page.goto("/email-finder");

  await page.getByRole("tab", { name: "Company website" }).click();
  await expectUrl(page, "/email-finder?tab=website", "website tab in URL");
  await page.getByRole("textbox", { name: "Company website" }).fill("nordicbunker.example");
  await page.getByRole("button", { name: "Extract contacts" }).click();
  await expectVisible(page.getByText("+47 22 00 00 00"), "extracted phone");
  await expectVisible(page.getByText("sales@nordicbunker.example"), "extracted email");

  await page.getByRole("tab", { name: "Name + company" }).click();
  await expectUrl(page, "/email-finder?tab=name", "name tab in URL");
  await page.getByPlaceholder(/Full name/).fill("Amira Haddad");
  await page.getByPlaceholder(/Company/).fill("Gulfstar Refining");
  await page.getByRole("button", { name: "Find email" }).click();
  await expectVisible(page.getByText("a.haddad@gulfstar.example"), "name+company result");

  await page.goto("/email-finder?tab=bulk");
  assert((await page.getByRole("tab", { name: "Bulk lookup" }).getAttribute("aria-selected")) === "true", "deep link ?tab=bulk not selected");
  await page.getByLabel("People to look up").fill("linkedin.com/in/amira-haddad\nMichael Jones, Falcon Petroleum\nnot a valid line");
  await expectVisible(page.getByText("2 of 25 people · 1 line not recognized"), "bulk line counter");
  await page.getByRole("button", { name: "Look up all" }).click();
  await expectVisible(page.getByText("1 of 2 found"), "bulk summary");
  await expectVisible(page.getByText("No business email found — skipped."), "bulk failure reason");
  assertNoErrors(errors);
  await context.close();
});

await test("Email Verifier: counts, results, limit and copy", async () => {
  const { page, context, errors } = await newPage({ loggedIn: true });
  await page.goto("/verify-emails");
  const textarea = page.getByLabel("Email addresses");
  const button = page.getByRole("button", { name: "Verify emails" });
  assert(await button.isDisabled(), "Verify button enabled with no input");

  await textarea.fill(Array.from({ length: 501 }, (_, i) => `p${i}@gulfstar.example`).join("\n"));
  await expectVisible(page.getByText("remove 1 to continue"), "over-limit message");
  assert(await button.isDisabled(), "Verify button enabled over the limit");

  await textarea.fill("jane@gulfstar.example, bob@dead-domain.example\nnot-an-email");
  await expectVisible(page.getByText("3 of 500 addresses"), "address counter");
  await button.click();
  await expectVisible(page.getByRole("cell", { name: "bob@dead-domain.example" }), "results table");
  await expectVisible(page.getByText("Deliverable", { exact: true }), "deliverable label");
  // Assert the reason, not just the status: two different failures both read
  // "Undeliverable", and the reason is what tells them apart.
  await expectVisible(
    page.getByText("The domain has no mail servers, so mail to it bounces."),
    "no-mail-server reason",
  );
  await expectVisible(
    page.getByText("This isn't a correctly formatted email address."),
    "invalid-format reason",
  );

  await page.getByRole("button", { name: "Copy deliverable addresses" }).click();
  await expectVisible(page.getByText("Copied 1 addresses"), "copy confirmation");
  const clip = await page.evaluate(() => navigator.clipboard.readText());
  assert(clip === "jane@gulfstar.example", `clipboard contained ${JSON.stringify(clip)}`);
  assertNoErrors(errors);
  await context.close();
});

await test("App nav and Company Search callout link to Email Finder", async () => {
  const { page, context, errors } = await newPage({ loggedIn: true });
  await page.goto("/discover");
  await expectVisible(page.getByRole("heading", { level: 1, name: "Company Search" }), "Company Search h1");
  await page.getByRole("link", { name: /Open Email Finder/ }).click();
  await expectUrl(page, "/email-finder", "callout → email finder");
  // The URL updates a tick before React re-renders the nav, so wait for the active state.
  await expectVisible(
    page.locator('nav[aria-label="App"] a[href="/email-finder"][aria-current="page"]'),
    "Email Finder nav link marked active",
  );
  await page.getByRole("navigation", { name: "App" }).getByRole("link", { name: "Email Verifier" }).click();
  await expectUrl(page, "/verify-emails", "nav → verifier");
  assertNoErrors(errors);
  await context.close();
});

await test("Credits badge shows the plan and opens the Plan & credits page", async () => {
  const { page, context, errors, calls } = await newPage({ loggedIn: true });
  await page.goto("/email-finder");
  const badge = page.locator("header").getByRole("link", { name: /Professional.*1,999 credits/ });
  await expectVisible(badge, "credits badge with plan and balance");

  const before = calls.filter((c) => c.path === "/billing/me").length;
  await page.getByLabel("LinkedIn profile link").fill("linkedin.com/in/amira-haddad");
  await page.getByRole("button", { name: "Find email" }).click();
  await expectVisible(page.getByText("a.haddad@gulfstar.example"), "lookup result");
  await page.waitForFunction(() => true);
  assert(calls.filter((c) => c.path === "/billing/me").length > before, "credits not refreshed after a lookup");

  await badge.click();
  await expectUrl(page, "/billing", "badge → billing page");
  await expectVisible(page.getByRole("heading", { level: 1, name: "Plan & credits" }), "billing h1");
  await expectVisible(page.getByText("2,000 email credits every month"), "monthly credits");
  await expectVisible(page.getByText("of 50"), "daily search allowance");
  await expectVisible(page.getByText(/Paid until .*2027/), "paid-until date");
  assertNoErrors(errors);
  await context.close();
});

await test("Pricing → checkout → pay in USDT → I have paid", async () => {
  const { page, context, errors, calls } = await newPage({ loggedIn: true });
  await page.goto("/pricing");
  await page.getByRole("link", { name: "Start with Professional" }).click();
  await expectUrl(page, "/checkout?plan=professional&credits=2000&period=yearly", "pricing CTA → checkout");
  await expectVisible(page.getByText("$348"), "yearly total");

  await page.getByRole("button", { name: "1 month" }).click();
  await expectVisible(page.getByText("$39", { exact: true }), "monthly total after switching period");
  await page.getByLabel("Tether (USDT)").check();
  await page.getByRole("button", { name: "Continue to payment" }).click();
  await expectUrl(page, "/billing/orders/order-1", "order page");
  const created = calls.find((c) => c.path === "/billing/orders" && c.method === "POST");
  assert(created.body.billing_period === "monthly" && created.body.currency === "USDT_TRC20", `wrong order payload ${JSON.stringify(created.body)}`);

  await expectVisible(page.getByText("TExampleUsdtAddress"), "pay-to address");
  await expectVisible(page.getByText("Send on the TRON (TRC-20) network only."), "network warning");
  await expectVisible(page.getByRole("img", { name: /QR code/ }), "QR code");

  await expectVisible(page.getByText("PL-TEST1234").first(), "generated payment reference");
  const markPaid = page.getByRole("button", { name: "I have paid" });
  assert(await markPaid.isEnabled(), "I have paid should work without typing anything");
  await markPaid.click();
  const paidCall = calls.find((c) => c.path.endsWith("/paid"));
  assert(!paidCall.body?.tx_hash, `a transaction ID was sent: ${JSON.stringify(paidCall.body)}`);
  await expectVisible(page.getByText("Thanks — we're checking your payment"), "waiting-for-confirmation view");
  assertNoErrors(errors);
  await context.close();
});

await test("Admin sees pending payments badge and confirms a payment", async () => {
  const { page, context, errors, calls } = await newPage({ loggedIn: true, admin: true });
  await page.goto("/dashboard");
  const paymentsLink = page.getByRole("navigation", { name: "App" }).getByRole("link", { name: /Payments/ });
  // The badge reads "1" visually, with " waiting" for screen readers.
  await expectVisible(paymentsLink.getByText(/^1\s*waiting$/), "pending badge with 1");
  await paymentsLink.click();
  await expectUrl(page, "/admin/payments", "admin payments page");
  await expectVisible(page.getByText("buyer@example.com"), "customer email on pending payment");
  await expectVisible(page.getByRole("link", { name: /Check on tronscan.org/ }), "explorer link");

  await page.getByRole("button", { name: "Confirm payment" }).click();
  await expectVisible(page.getByText("No payments are waiting for confirmation."), "empty pending list after confirming");
  assert(calls.some((c) => c.path.endsWith("/confirm")), "confirm endpoint not called");
  await page.waitForFunction(() => !document.querySelector('nav[aria-label="App"] a[href="/admin/payments"] span'), null, { timeout: 5000 })
    .catch(() => { throw new Error("pending badge still shown after confirming"); });
  assertNoErrors(errors);
  await context.close();
});

await browser.close();
const failed = results.filter(([ok]) => !ok).length;
console.log(`\n${results.length - failed} passed, ${failed} failed`);
process.exit(failed ? 1 : 0);
