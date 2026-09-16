"""Admin notifications.

Email only goes out when SMTP is configured (`SMTP_HOST`, `SMTP_FROM`);
without it, the pending-payments badge in the app is the notification.
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
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as smtp:
            if settings.smtp_use_tls:
                smtp.starttls()
            if settings.smtp_username:
                smtp.login(settings.smtp_username, settings.smtp_password or "")
            smtp.send_message(message)
    except Exception:
        logger.exception("Couldn't email admins about payment %s", order["id"])
