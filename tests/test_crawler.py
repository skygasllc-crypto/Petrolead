"""The background crawler: queueing sites, seed searches, reading due sites
into the contact directory, robots.txt, and the admin page. No site or
search provider is ever contacted — each is replaced with a fake."""

from __future__ import annotations

from datetime import timedelta

import httpx
from sqlalchemy import select

from app.config import Settings
from app.database.models import ContactRecord, CrawlSeed, CrawlTarget, utcnow
from app.discovery.search import SearchQuotaExceededError, SearchResultItem
from app.discovery.types import DiscoveredCompany
from app.services import company_service, crawler

SETTINGS = Settings(crawler_seed_searches_per_run=2, crawler_batch_size=10)


def _targets(db):
    return {t.domain: t for t in db.execute(select(CrawlTarget)).scalars()}


def _queue(db, domain, *, due=True):
    crawler.enqueue(
        db,
        domain=domain,
        website=f"https://{domain}",
        company_name=None,
        source="seed",
        crawled=not due,
    )
    db.commit()


class _FakeProvider:
    name = "serper"

    def __init__(self, results=None, *, quota_after=None):
        self.results = results or {}
        self.queries = []
        self.quota_after = quota_after

    async def search(self, query, *, limit=10):
        if self.quota_after is not None and len(self.queries) >= self.quota_after:
            raise SearchQuotaExceededError("out of credits")
        self.queries.append(query)
        return self.results.get(query, [])


def _result(url):
    return SearchResultItem(title="A company", url=url, snippet="")


class TestQueueing:
    async def test_search_results_are_queued_for_a_later_visit(self, db_session):
        candidates = [
            DiscoveredCompany(company_name="Gulfstar", website="https://www.gulfstar.example"),
            DiscoveredCompany(company_name="Page", website="https://facebook.com/gulfstar"),
            DiscoveredCompany(company_name="Fake", website="https://fake.example", is_mock=True),
            DiscoveredCompany(company_name="No site"),
        ]
        await company_service._fill_missing_emails(db_session, candidates)

        targets = _targets(db_session)
        assert set(targets) == {"gulfstar.example"}
        # The search just read it, so it isn't due until a full cycle later.
        assert targets["gulfstar.example"].next_crawl_at > utcnow() + timedelta(days=29)

    def test_a_site_is_queued_once(self, db_session):
        _queue(db_session, "gulfstar.example")
        assert not crawler.enqueue(
            db_session,
            domain="gulfstar.example",
            website="https://gulfstar.example",
            company_name=None,
            source="search",
            crawled=True,
        )


class TestSeeding:
    async def test_seed_searches_queue_company_sites_only(self, db_session, monkeypatch):
        first, second = crawler.SEED_QUERIES[:2]
        provider = _FakeProvider(
            {
                first: [
                    _result("https://www.petro-one.example/about"),
                    _result("https://linkedin.com/company/petro-one"),
                ],
                second: [_result("https://petro-two.example")],
            }
        )
        monkeypatch.setattr(crawler, "get_search_provider", lambda settings: provider)

        summary = crawler.CrawlSummary()
        await crawler.run_seed_searches(db_session, SETTINGS, summary)

        assert provider.queries == [first, second]
        assert set(_targets(db_session)) == {"petro-one.example", "petro-two.example"}
        assert summary.seed_searches == 2 and summary.sites_added == 2
        seed = db_session.get(CrawlSeed, first)
        assert seed.last_run_at is not None and seed.sites_found == 1

    async def test_next_run_takes_the_seeds_not_yet_run(self, db_session, monkeypatch):
        provider = _FakeProvider()
        monkeypatch.setattr(crawler, "get_search_provider", lambda settings: provider)
        for _ in range(2):
            await crawler.run_seed_searches(db_session, SETTINGS, crawler.CrawlSummary())
        assert provider.queries == list(crawler.SEED_QUERIES[:4])

    async def test_quota_stops_seeding(self, db_session, monkeypatch):
        provider = _FakeProvider(quota_after=1)
        monkeypatch.setattr(crawler, "get_search_provider", lambda settings: provider)
        summary = crawler.CrawlSummary()
        await crawler.run_seed_searches(db_session, SETTINGS, summary)
        assert summary.seed_searches == 1
        assert any("quota" in note for note in summary.notes)

    async def test_mock_provider_seeds_nothing(self, db_session):
        summary = crawler.CrawlSummary()
        await crawler.run_seed_searches(db_session, SETTINGS, summary)
        assert summary.seed_searches == 0
        assert _targets(db_session) == {}


def _fake_site(monkeypatch, pages, *, blocked=()):
    """`pages`: domain -> emails found there, or None for an unreachable site."""

    async def fake_enrich(company, *, settings=None):
        domain = company.website.split("//", 1)[1]
        emails = pages.get(domain)
        if emails is None:
            return company  # nothing learned — the site couldn't be read
        company.company_name = f"{domain} Ltd"
        company.emails = [{"email": e, "is_valid": True} for e in emails]
        return company

    async def fake_robots(client, website, user_agent):
        return website.split("//", 1)[1] not in blocked

    monkeypatch.setattr(crawler, "enrich_from_website", fake_enrich)
    monkeypatch.setattr(crawler, "_robots_allows", fake_robots)


class TestCrawling:
    async def test_due_sites_are_read_into_the_directory(self, db_session, monkeypatch):
        _queue(db_session, "gulfstar.example")
        _queue(db_session, "later.example", due=False)
        _fake_site(monkeypatch, {"gulfstar.example": ["jane.doe@gulfstar.example"]})

        summary = crawler.CrawlSummary()
        await crawler.crawl_due_sites(db_session, SETTINGS, summary)

        assert summary.sites_crawled == 1 and summary.emails_found == 1
        record = db_session.execute(select(ContactRecord)).scalars().one()
        assert record.email == "jane.doe@gulfstar.example"
        assert record.source == "crawler"
        target = _targets(db_session)["gulfstar.example"]
        assert target.company_name == "gulfstar.example Ltd"
        assert target.emails_found == 1
        assert target.next_crawl_at > utcnow() + timedelta(days=29)

    async def test_a_failing_site_backs_off(self, db_session, monkeypatch):
        _queue(db_session, "down.example")
        _fake_site(monkeypatch, {})
        for expected_days in (2, 4):
            target = _targets(db_session)["down.example"]
            target.next_crawl_at = utcnow()
            db_session.commit()
            await crawler.crawl_due_sites(db_session, SETTINGS, crawler.CrawlSummary())
            target = _targets(db_session)["down.example"]
            wait = target.next_crawl_at - utcnow()
            assert timedelta(days=expected_days - 1) < wait <= timedelta(days=expected_days)

    async def test_robots_txt_is_respected(self, db_session, monkeypatch):
        _queue(db_session, "private.example")
        _fake_site(
            monkeypatch, {"private.example": ["x@private.example"]}, blocked={"private.example"}
        )
        summary = crawler.CrawlSummary()
        await crawler.crawl_due_sites(db_session, SETTINGS, summary)
        assert summary.sites_skipped_by_robots == 1
        assert db_session.execute(select(ContactRecord)).first() is None

    async def test_turned_off_does_nothing(self, db_session, monkeypatch):
        _queue(db_session, "gulfstar.example")
        _fake_site(monkeypatch, {"gulfstar.example": ["info@gulfstar.example"]})
        summary = await crawler.run_crawler(
            db_session, SETTINGS.model_copy(update={"crawler_enabled": False})
        )
        assert summary.sites_crawled == 0
        assert db_session.execute(select(ContactRecord)).first() is None


class TestRobotsParsing:
    async def _allows(self, monkeypatch, status, body):
        async def fake_get(self, url, **kwargs):
            return httpx.Response(status, text=body, request=httpx.Request("GET", url))

        monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
        async with httpx.AsyncClient() as client:
            return await crawler._robots_allows(
                client, "https://gulfstar.example", "PetroLeadBot/1.0 (+https://petrolead.org/bot)"
            )

    async def test_a_disallow_for_everyone_is_obeyed(self, monkeypatch):
        assert not await self._allows(monkeypatch, 200, "User-agent: *\nDisallow: /\n")

    async def test_a_disallow_for_another_bot_is_not_ours(self, monkeypatch):
        assert await self._allows(monkeypatch, 200, "User-agent: OtherBot\nDisallow: /\n")

    async def test_no_robots_file_means_no_objection(self, monkeypatch):
        assert await self._allows(monkeypatch, 404, "")


ADMIN_EMAIL = "admin@example.com"


def _admin(client, monkeypatch):
    from app.api import auth as auth_module
    from app.config import get_settings as real_get_settings

    settings = real_get_settings().model_copy(update={"admin_emails": ADMIN_EMAIL})
    monkeypatch.setattr(auth_module, "get_settings", lambda: settings)
    response = client.post(
        "/api/auth/register", json={"email": ADMIN_EMAIL, "password": "correct-horse-battery"}
    )
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


class TestAdminPage:
    def test_admin_sees_directory_stats(self, unauthenticated_client, db_session, monkeypatch):
        _queue(db_session, "gulfstar.example")
        headers = _admin(unauthenticated_client, monkeypatch)
        response = unauthenticated_client.get("/api/admin/directory", headers=headers)
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["sites_queued"] == 1 and body["sites_due"] == 1
        assert body["seed_searches_total"] == len(crawler.SEED_QUERIES)

    def test_admin_can_start_a_crawl(self, unauthenticated_client, monkeypatch):
        from app.api import admin as admin_module

        started = []

        async def fake_crawl():
            started.append(True)

        monkeypatch.setattr(admin_module, "_crawl_in_background", fake_crawl)
        headers = _admin(unauthenticated_client, monkeypatch)
        response = unauthenticated_client.post("/api/admin/directory/crawl", headers=headers)
        assert response.status_code == 202
        assert started == [True]

    def test_customers_cannot_see_or_start_it(self, client):
        assert client.get("/api/admin/directory").status_code == 403
        assert client.post("/api/admin/directory/crawl").status_code == 403
