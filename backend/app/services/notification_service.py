
import logging
import os
import smtplib
from datetime import datetime, timezone
from email.message import EmailMessage

from sqlalchemy.orm import Session

from backend.app.models import Notification

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 3


def _utc_now():
    return datetime.now(timezone.utc)


def _smtp_settings():
    return {
        "host": os.getenv("SMTP_HOST"),
        "port": int(os.getenv("SMTP_PORT", "587")),
        "username": os.getenv("SMTP_USERNAME"),
        "password": os.getenv("SMTP_PASSWORD"),
        "sender": os.getenv("SMTP_FROM_EMAIL"),
        "use_tls": os.getenv("SMTP_USE_TLS", "true").lower() == "true",
    }


def queue_notification(
    patient_id: int,
    recipient_email: str,
    notification_type: str,
    subject: str,
    message: str,
    db: Session,
    scheduled_at: datetime | None = None,
):
    """Save a notification before attempting delivery."""

    notification = Notification(
        patient_id=patient_id,
        recipient_email=recipient_email,
        notification_type=notification_type,
        subject=subject,
        message=message,
        status="pending",
        attempts=0,
        scheduled_at=scheduled_at or _utc_now(),
    )

    db.add(notification)
    db.commit()
    db.refresh(notification)

    return notification


def _record_failure(notification_id: int, db: Session, reason: str):
    """Persist one failed attempt and retain retry eligibility."""

    db.rollback()

    notification = db.query(Notification).filter(
        Notification.id == notification_id
    ).first()

    if notification is None:
        return

    notification.attempts += 1
    notification.status = (
        "failed"
        if notification.attempts >= MAX_ATTEMPTS
        else "pending"
    )

    db.commit()

    logger.warning(
        "Notification %s failed: %s",
        notification_id,
        reason,
    )


def send_notification(notification: Notification, db: Session):
    """Attempt SMTP delivery and persist the delivery result."""

    notification_id = notification.id
    settings = _smtp_settings()

    if not settings["host"] or not settings["sender"]:
        _record_failure(
            notification_id,
            db,
            "SMTP is not configured.",
        )

        return {
            "success": False,
            "status": "failed",
            "reason": "SMTP is not configured.",
        }

    email = EmailMessage()
    email["Subject"] = notification.subject
    email["From"] = settings["sender"]
    email["To"] = notification.recipient_email
    email.set_content(notification.message)

    try:
        with smtplib.SMTP(
            settings["host"],
            settings["port"],
            timeout=15,
        ) as server:

            server.ehlo()

            if settings["use_tls"]:
                server.starttls()
                server.ehlo()

            if settings["username"] and settings["password"]:
                server.login(
                    settings["username"],
                    settings["password"],
                )

            server.send_message(email)

        notification.status = "sent"
        notification.attempts += 1
        notification.sent_at = _utc_now()
        db.commit()

        logger.info(
            "Notification %s sent successfully.",
            notification_id,
        )

        return {
            "success": True,
            "status": "sent",
            "notification_id": notification_id,
        }

    except Exception:
        logger.exception(
            "Email delivery failed for notification %s.",
            notification_id,
        )

        _record_failure(
            notification_id,
            db,
            "Email delivery failed.",
        )

        return {
            "success": False,
            "status": "failed",
            "reason": "Email delivery failed.",
        }


def process_pending_notifications(
    db: Session,
    max_attempts: int = MAX_ATTEMPTS,
):
    """Process due notifications that still have retry attempts."""

    now = _utc_now()

    pending = (
        db.query(Notification)
        .filter(
            Notification.status == "pending",
            Notification.attempts < max_attempts,
            Notification.scheduled_at <= now,
        )
        .order_by(Notification.scheduled_at.asc())
        .limit(50)
        .all()
    )

    results = {
        "processed": 0,
        "sent": 0,
        "failed": 0,
    }

    for notification in pending:
        result = send_notification(notification, db)

        results["processed"] += 1

        if result["success"]:
            results["sent"] += 1
        else:
            results["failed"] += 1

    return results
