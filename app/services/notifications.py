"""Outgoing email: admin notifications and password-reset links.

Email only goes out when SMTP is configured (`SMTP_HOST`, `SMTP_FROM`);
without it, the pending-payments badge in the app is the notification, and
an admin hands out reset links from the Users page instead.
"""

from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database.models import User

logger = logging.getLogger("petrolead.services.notifications")


def admin_recipients(db: Session) -> list[str]:
    """Every active admin account's email, plus any address in ADMIN_EMAILS."""
    emails = set(
        db.execute(
            select(User.email).where(User.is_admin.is_(True), User.is_active.is_(True))
        ).scalars()
    )
    emails.update(get_settings().admin_emails_list)
    return sorted(emails)


def notify_payment_submitted(order: dict, recipients: list[str]) -> None:
    """Email admins that a customer marked a payment as paid.

    Runs as a background task after the response is sent, so it's handed
    plain data (a serialized order) rather than a database session."""
    settings = get_settings()
    if not settings.smtp_host or not settings.smtp_from or not recipients:
        logger.info(
            "Payment %s is waiting for confirmation (admin email isn't configured)", order["id"]
        )
        return

    message = EmailMessage()
    message["Subject"] = (
        f"Payment to confirm {order['reference']}: {order['plan_name']} "
        f"({order['billing_period']}) — {order['amount_crypto']} {order['coin_symbol']}"
    )
    message["From"] = settings.smtp_from
    message["To"] = ", ".join(recipients)
    lines = [
        "A customer has marked a crypto payment as paid. Check the receiving address on the "
        "block explorer, then confirm or reject it:",
        f"{settings.app_base_url.rstrip('/')}/admin/payments",
        "",
        f"Reference: {order['reference']}",
        f"Customer: {order['customer_email']}",
        f"Plan: {order['plan_name']}, {order['credits_per_month']:,} credits/month, "
        f"billed {order['billing_period']}",
        f"Amount due: {order['amount_crypto']} {order['coin_symbol']} on {order['network']} "
        f"(${order['amount_usd']})",
        f"Receiving address: {order['pay_address']}",
    ]
    if order.get("tx_hash"):
        lines += [f"Transaction ID: {order['tx_hash']}", f"Explorer: {order['explorer_url']}"]
    else:
        lines.append("No transaction ID given — match the payment by amount and time.")
    if order.get("paid_after_quote_expired"):
        lines += [
            "",
            "Note: the price quote had expired before this was marked paid — check that the "
            "full amount arrived.",
        ]
    message.set_content("\n".join(lines))

    try:
        _send(message)
    except Exception:
        logger.exception("Couldn't email admins about payment %s", order["id"])


def email_configured() -> bool:
    settings = get_settings()
    return bool(settings.smtp_host and settings.smtp_from)


def send_password_reset(email: str, reset_url: str, expires_in_minutes: int) -> None:
    """Email a reset link. Runs as a background task, so whether the address
    has an account never shows in how long the request took. The link is
    never logged: anyone reading the logs could use it."""
    settings = get_settings()
    if not email_configured():
        logger.warning(
            "A password reset was requested but email isn't configured (SMTP_HOST, "
            "SMTP_FROM) — an admin can issue a reset link from the Users page instead"
        )
        return

    message = EmailMessage()
    message["Subject"] = f"Reset your {settings.app_name} password"
    message["From"] = settings.smtp_from
    message["To"] = email
    message.set_content(
        "\n".join(
            [
                f"Someone asked to reset the password for your {settings.app_name} account.",
                "",
                "To choose a new password, open this link:",
                reset_url,
                "",
                f"The link works once and expires in {expires_in_minutes} minutes.",
                "If you didn't ask for this, ignore this email — your password stays as it is.",
            ]
        )
    )
    try:
        _send(message)
    except Exception:
        logger.exception("Couldn't send a password reset email")


def _send(message: EmailMessage) -> None:
    settings = get_settings()
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as smtp:
        if settings.smtp_use_tls:
            smtp.starttls()
        if settings.smtp_username:
            smtp.login(settings.smtp_username, settings.smtp_password or "")
        smtp.send_message(message)
