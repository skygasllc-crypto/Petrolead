"""Tests for crypto plan payments: orders, "I have paid", admin review, and
paid periods that end.

Live prices are faked and settings are patched with test receiving
addresses, following the same pattern as tests/test_billing.py.
"""

from datetime import timedelta
from decimal import Decimal

import pytest
from dateutil.relativedelta import relativedelta
from sqlalchemy import select

from app.api import auth as auth_module
from app.config import get_settings as real_get_settings
from app.database.models import PaymentOrder, Subscription, utcnow
from app.services import billing_service, notifications, payment_service
from app.services.crypto_rates import RateUnavailableError

PASSWORD = "correct-horse-battery"
ADMIN_EMAIL = "admin@example.com"
BTC_ADDRESS = "bc1qexamplereceivingaddress000000000000"
USDT_ADDRESS = "TExampleUsdtReceivingAddress00000"
TRX_ADDRESS = "TExampleTrxReceivingAddress000000"
TX_A = "a" * 64
TX_B = "b" * 64


def _settings(**overrides):
    return real_get_settings().model_copy(
        update={
            "billing_enforced": True,
            "admin_emails": ADMIN_EMAIL,
            "crypto_btc_address": BTC_ADDRESS,
            "crypto_usdt_trc20_address": USDT_ADDRESS,
            "crypto_trx_address": TRX_ADDRESS,
            "crypto_quote_minutes": 60,
            **overrides,
        }
    )


def _use_settings(monkeypatch, settings):
    for module in (auth_module, billing_service, payment_service, notifications):
        monkeypatch.setattr(module, "get_settings", lambda: settings)


@pytest.fixture(autouse=True)
def configure(monkeypatch):
    _use_settings(monkeypatch, _settings())

    async def fake_usd_price(currency, *, settings):
        return {"BTC": Decimal("60000"), "TRX": Decimal("0.25")}[currency]

    monkeypatch.setattr(payment_service, "usd_price", fake_usd_price)


@pytest.fixture()
def notified(monkeypatch):
    calls = []
    monkeypatch.setattr(
        notifications,
        "notify_payment_submitted",
        lambda order, recipients: calls.append((order, recipients)),
    )
    return calls


def _register(client, email):
    response = client.post("/api/auth/register", json={"email": email, "password": PASSWORD})
    assert response.status_code == 200, response.text
    body = response.json()
    return body["user"]["id"], {"Authorization": f"Bearer {body['access_token']}"}


@pytest.fixture()
def api(unauthenticated_client):
    return unauthenticated_client


@pytest.fixture()
def admin(api):
    return _register(api, ADMIN_EMAIL)[1]


@pytest.fixture()
def customer(api):
    return _register(api, "customer@example.com")


def _order(
    api, headers, plan="professional", credits=2000, period="yearly", currency="USDT_TRC20"
):
    return api.post(
        "/api/billing/orders",
        json={
            "plan": plan,
            "credits_per_month": credits,
            "billing_period": period,
            "currency": currency,
        },
        headers=headers,
    )


def _paid(api, headers, order_id, tx=TX_A):
    return api.post(f"/api/billing/orders/{order_id}/paid", json={"tx_hash": tx}, headers=headers)


def _confirm(api, admin, order_id):
    response = api.post(f"/api/admin/payments/{order_id}/confirm", json={}, headers=admin)
    assert response.status_code == 200, response.text
    return response.json()


def _paid_order(api, headers, tx=TX_A, **order_fields):
    order = _order(api, headers, **order_fields).json()
    assert _paid(api, headers, order["id"], tx).status_code == 200
    return order


def _subscription(db_session, user_id):
    db_session.expire_all()
    return db_session.execute(
        select(Subscription).where(Subscription.user_id == user_id)
    ).scalar_one()


class TestPaymentMethods:
    def test_lists_every_coin_with_an_address(self, api, customer):
        methods = api.get("/api/billing/payment-methods", headers=customer[1]).json()
        assert {m["currency"]: m["address"] for m in methods} == {
            "BTC": BTC_ADDRESS,
            "USDT_TRC20": USDT_ADDRESS,
            "TRX": TRX_ADDRESS,
        }

    def test_a_coin_without_an_address_is_not_offered(self, api, customer, monkeypatch):
        _use_settings(monkeypatch, _settings(crypto_trx_address=None))
        methods = api.get("/api/billing/payment-methods", headers=customer[1]).json()
        assert "TRX" not in {m["currency"] for m in methods}
        assert _order(api, customer[1], currency="TRX").status_code == 422


class TestCreatingOrders:
    def test_usdt_is_priced_one_to_one_with_the_dollar(self, api, customer):
        response = _order(api, customer[1], plan="professional", credits=2000, period="yearly")
        assert response.status_code == 200, response.text
        order = response.json()
        # $39/month, 25% off = $29/month, billed for 12 months.
        assert order["amount_usd"] == "348.00"
        assert order["amount_crypto"] == "348.00"
        assert order["pay_address"] == USDT_ADDRESS
        assert order["network"] == "TRON (TRC-20)"
        assert order["status"] == "awaiting_payment"

    def test_btc_amount_uses_the_live_price_and_rounds_up(self, api, customer):
        order = _order(api, customer[1], "basic", 1000, "monthly", currency="BTC")
        body = order.json()
        # $20 / $60,000 = 0.000333333… BTC, rounded up to 8 decimals.
        assert body["amount_crypto"] == "0.00033334"
        assert body["usd_rate"] == "60000"
        assert body["pay_address"] == BTC_ADDRESS

    def test_trx_amount(self, api, customer):
        order = _order(api, customer[1], "basic", 1000, "monthly", currency="TRX")
        assert order.json()["amount_crypto"] == "80.000000"

    @pytest.mark.parametrize(("plan", "credits"), [("professional", 1000), ("gold", 1000)])
    def test_rejects_plans_and_tiers_that_dont_exist(self, api, customer, plan, credits):
        assert _order(api, customer[1], plan=plan, credits=credits).status_code == 422

    def test_price_unavailable(self, api, customer, monkeypatch):
        async def failing_price(currency, *, settings):
            raise RateUnavailableError(currency)

        monkeypatch.setattr(payment_service, "usd_price", failing_price)
        response = _order(api, customer[1], currency="BTC")
        assert response.status_code == 503
        assert "pay with USDT" in response.json()["detail"]

    def test_needs_login(self, api):
        assert _order(api, {}).status_code == 401


class TestMarkingPaid:
    def test_i_have_paid_records_the_transaction_and_notifies_admins(
        self, api, admin, customer, notified
    ):
        order = _order(api, customer[1]).json()
        response = _paid(api, customer[1], order["id"], TX_A.upper())
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["status"] == "submitted"
        assert body["tx_hash"] == TX_A
        assert body["explorer_url"] == f"https://tronscan.org/#/transaction/{TX_A}"

        assert len(notified) == 1
        summary, recipients = notified[0]
        assert summary["customer_email"] == "customer@example.com"
        assert ADMIN_EMAIL in recipients

    def test_rejects_something_that_isnt_a_transaction_id(self, api, customer):
        order = _order(api, customer[1]).json()
        response = _paid(api, customer[1], order["id"], "not-a-tx")
        assert response.status_code == 422
        assert "64-character" in response.json()["detail"]

    def test_a_transaction_id_can_only_be_used_once(self, api, customer):
        _paid_order(api, customer[1])
        second = _order(api, customer[1]).json()
        response = _paid(api, customer[1], second["id"], TX_A)
        assert response.status_code == 409

    def test_cant_mark_paid_twice(self, api, customer):
        order = _paid_order(api, customer[1])
        assert _paid(api, customer[1], order["id"], TX_B).status_code == 409

    def test_cant_touch_another_customers_order(self, api, customer):
        order = _order(api, customer[1]).json()
        _, other = _register(api, "someone-else@example.com")
        assert api.get(f"/api/billing/orders/{order['id']}", headers=other).status_code == 404
        assert _paid(api, other, order["id"]).status_code == 404

    def test_an_expired_quote_can_still_be_marked_paid(self, api, admin, customer, db_session):
        order = _order(api, customer[1], currency="BTC").json()
        stored = db_session.get(PaymentOrder, order["id"])
        stored.expires_at = utcnow() - timedelta(minutes=1)
        db_session.commit()

        assert api.get(f"/api/billing/orders/{order['id']}", headers=customer[1]).json()[
            "status"
        ] == "expired"
        assert _paid(api, customer[1], order["id"]).json()["status"] == "submitted"

        pending = api.get("/api/admin/payments?status=submitted", headers=admin).json()
        assert pending[0]["paid_after_quote_expired"] is True

    def test_cancel(self, api, customer):
        order = _order(api, customer[1]).json()
        response = api.post(f"/api/billing/orders/{order['id']}/cancel", headers=customer[1])
        assert response.json()["status"] == "cancelled"
        assert _paid(api, customer[1], order["id"]).status_code == 409


class TestAdminReview:
    def test_pending_payments_are_listed_and_counted(self, api, admin, customer):
        _order(api, customer[1])  # not marked paid, so not pending
        order = _paid_order(api, customer[1], tx=TX_B)

        assert api.get("/api/admin/payments/pending-count", headers=admin).json() == {"count": 1}
        pending = api.get("/api/admin/payments?status=submitted", headers=admin).json()
        assert [p["id"] for p in pending] == [order["id"]]

    def test_only_admins_can_review(self, api, customer):
        order = _paid_order(api, customer[1])
        assert api.get("/api/admin/payments", headers=customer[1]).status_code == 403
        path = f"/api/admin/payments/{order['id']}/confirm"
        assert api.post(path, json={}, headers=customer[1]).status_code == 403

    def test_confirming_a_yearly_payment_starts_the_plan(self, api, admin, customer, db_session):
        order = _paid_order(api, customer[1], plan="professional", credits=2000, period="yearly")

        body = _confirm(api, admin, order["id"])
        assert body["status"] == "confirmed"

        subscription = _subscription(db_session, customer[0])
        assert subscription.plan == "professional"
        assert subscription.credits_balance == 2000
        paid_for = subscription.paid_until - utcnow()
        assert timedelta(days=360) < paid_for < timedelta(days=370)
        assert api.get("/api/admin/payments/pending-count", headers=admin).json() == {"count": 0}

        billing = api.get("/api/billing/me", headers=customer[1]).json()
        assert billing["plan"] == "professional"
        assert billing["expired"] is False

    def test_paying_again_for_the_same_plan_extends_it(self, api, admin, customer, db_session):
        first = _paid_order(api, customer[1], period="monthly")
        _confirm(api, admin, first["id"])
        ends = _subscription(db_session, customer[0]).paid_until

        second = _paid_order(api, customer[1], period="monthly", tx=TX_B)
        _confirm(api, admin, second["id"])

        subscription = _subscription(db_session, customer[0])
        assert subscription.paid_until == ends + relativedelta(months=1)
        assert subscription.credits_balance == 2000  # no extra month of credits up front

    def test_paying_for_a_different_plan_switches_it(self, api, admin, customer, db_session):
        basic = _paid_order(api, customer[1], plan="basic", credits=1000, period="monthly")
        _confirm(api, admin, basic["id"])

        pro = _paid_order(
            api, customer[1], TX_B, plan="professional", credits=5000, period="monthly"
        )
        _confirm(api, admin, pro["id"])

        subscription = _subscription(db_session, customer[0])
        assert subscription.plan == "professional"
        assert subscription.credits_per_month == 5000
        assert subscription.credits_balance == 6000

    def test_only_payments_marked_paid_can_be_confirmed(self, api, admin, customer):
        order = _order(api, customer[1]).json()
        response = api.post(f"/api/admin/payments/{order['id']}/confirm", json={}, headers=admin)
        assert response.status_code == 409

    def test_rejecting_needs_a_note_the_customer_sees(self, api, admin, customer):
        order = _paid_order(api, customer[1])
        path = f"/api/admin/payments/{order['id']}/reject"
        assert api.post(path, json={"note": "   "}, headers=admin).status_code == 422

        note = "No payment arrived at our address."
        response = api.post(path, json={"note": note}, headers=admin)
        assert response.json()["status"] == "rejected"

        seen = api.get(f"/api/billing/orders/{order['id']}", headers=customer[1]).json()
        assert seen["admin_note"] == "No payment arrived at our address."
        assert api.get("/api/billing/me", headers=customer[1]).json()["plan"] is None


class TestPaidPeriods:
    def test_tools_stop_when_the_paid_period_ends(self, api, admin, customer, db_session):
        order = _paid_order(api, customer[1], period="monthly")
        _confirm(api, admin, order["id"])
        subscription = _subscription(db_session, customer[0])
        subscription.paid_until = utcnow() - timedelta(minutes=1)
        db_session.commit()

        response = api.post("/api/emails/verify", json={"emails": ["a@b.co"]}, headers=customer[1])
        assert response.status_code == 402
        assert "plan ended on" in response.json()["detail"]
        assert api.get("/api/billing/me", headers=customer[1]).json()["expired"] is True

    def test_no_monthly_credits_after_the_paid_period(self, api, admin, customer, db_session):
        order = _paid_order(api, customer[1], period="monthly")
        _confirm(api, admin, order["id"])
        subscription = _subscription(db_session, customer[0])
        subscription.credits_balance = 100
        # The next monthly grant was due exactly when the paid period ended.
        ended = utcnow() - timedelta(days=1)
        subscription.renews_at = ended
        subscription.paid_until = ended
        db_session.commit()

        assert api.get("/api/billing/me", headers=customer[1]).json()["credits_balance"] == 100

    def test_renewing_an_expired_plan_starts_it_again_and_keeps_credits(
        self, api, admin, customer, db_session
    ):
        first = _paid_order(api, customer[1], period="monthly")
        _confirm(api, admin, first["id"])
        subscription = _subscription(db_session, customer[0])
        subscription.credits_balance = 150
        subscription.paid_until = utcnow() - timedelta(days=3)
        db_session.commit()

        renewal = _paid_order(api, customer[1], period="monthly", tx=TX_B)
        _confirm(api, admin, renewal["id"])

        subscription = _subscription(db_session, customer[0])
        assert subscription.credits_balance == 2150
        assert subscription.paid_until > utcnow() + timedelta(days=27)


ORDER_SUMMARY = {
    "id": "order-1",
    "plan_name": "Professional",
    "billing_period": "yearly",
    "credits_per_month": 2000,
    "amount_crypto": "348.00",
    "amount_usd": "348.00",
    "coin_symbol": "USDT",
    "network": "TRON (TRC-20)",
    "pay_address": USDT_ADDRESS,
    "tx_hash": TX_A,
    "explorer_url": f"https://tronscan.org/#/transaction/{TX_A}",
    "customer_email": "customer@example.com",
    "paid_after_quote_expired": False,
}


class TestAdminEmail:
    def test_emails_admins_when_smtp_is_configured(self, monkeypatch):
        settings = _settings(smtp_host="smtp.example.com", smtp_from="billing@petrolead.example")
        monkeypatch.setattr(notifications, "get_settings", lambda: settings)
        sent = []

        class FakeSMTP:
            def __init__(self, host, port, timeout):
                assert (host, port) == ("smtp.example.com", 587)

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

            def starttls(self):
                pass

            def send_message(self, message):
                sent.append(message)

        monkeypatch.setattr(notifications.smtplib, "SMTP", FakeSMTP)
        notifications.notify_payment_submitted(ORDER_SUMMARY, [ADMIN_EMAIL])

        assert len(sent) == 1
        assert sent[0]["To"] == ADMIN_EMAIL
        assert sent[0]["Subject"].startswith("Payment to confirm: Professional")
        assert TX_A in sent[0].get_content()

    def test_without_smtp_nothing_is_sent(self, monkeypatch):
        def fail(*args, **kwargs):
            raise AssertionError("no email without SMTP settings")

        monkeypatch.setattr(notifications.smtplib, "SMTP", fail)
        notifications.notify_payment_submitted(ORDER_SUMMARY, [ADMIN_EMAIL])
