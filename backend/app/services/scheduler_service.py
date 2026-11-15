
import logging
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from backend.app.database import SessionLocal
from backend.app.models import Patient
from backend.app.services.medication_service import (
    generate_daily_doses,
    update_dose_statuses,
)
from backend.app.services.notification_service import (
    process_pending_notifications,
)

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler(timezone="UTC")


def process_all_patients():
    """Generate today's doses and refresh statuses for active patients."""

    db = SessionLocal()

    try:
        patients = (
            db.query(Patient)
            .filter(Patient.is_active.is_(True))
            .all()
        )

        for patient in patients:
            try:
                patient_timezone = ZoneInfo(patient.timezone)
                local_date = datetime.now(
                    patient_timezone
                ).date()

                generate_daily_doses(
                    patient_id=patient.id,
                    target_date=local_date,
                    db=db,
                )

                update_dose_statuses(
                    patient_id=patient.id,
                    db=db,
                )

                logger.info(
                    "Processed medication schedule for patient %s",
                    patient.id,
                )

            except Exception:
                db.rollback()
                logger.exception(
                    "Could not process patient %s",
                    patient.id,
                )

    finally:
        db.close()


def process_notifications():
    """Process due email notifications."""

    db = SessionLocal()

    try:
        results = process_pending_notifications(db)

        if results["processed"]:
            logger.info(
                "Notification processing: %s",
                results,
            )

    except Exception:
        db.rollback()
        logger.exception(
            "Notification processing job failed."
        )

    finally:
        db.close()


def start_scheduler():
    """Start the background scheduler once."""

    if scheduler.running:
        return

    scheduler.add_job(
        process_all_patients,
        trigger=IntervalTrigger(minutes=1),
        id="carecircle_medication_processor",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        next_run_time=datetime.now(timezone.utc),
    )

    scheduler.add_job(
        process_notifications,
        trigger=IntervalTrigger(minutes=1),
        id="carecircle_notification_processor",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        next_run_time=datetime.now(timezone.utc),
    )

    scheduler.start()

    logger.info(
        "CareCircle scheduler started with medication "
        "and notification processing."
    )


def stop_scheduler():
    """Stop the scheduler safely."""

    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("CareCircle scheduler stopped.")
