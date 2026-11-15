
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from backend.app.models import (
    Patient,
    Medication,
    DoseRecord,
    Appointment,
    Notification,
    AuditLog,
)


def _as_utc(value):
    """Normalize database timestamps to UTC."""

    if value is None:
        return None

    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=timezone.utc)

    return value.astimezone(timezone.utc)


def _iso(value):
    return value.isoformat() if value else None


def get_dashboard_data(
    patient_id: int,
    db: Session,
    now: datetime | None = None,
):
    """Build a patient-specific dashboard from stored records."""

    patient = db.query(Patient).filter(
        Patient.id == patient_id,
        Patient.is_active.is_(True),
    ).first()

    if patient is None:
        return None

    patient_timezone = ZoneInfo(patient.timezone)

    current_time = _as_utc(now) if now else datetime.now(timezone.utc)
    local_now = current_time.astimezone(patient_timezone)
    today = local_now.date()

    # Active medications
    medications = (
        db.query(Medication)
        .filter(
            Medication.patient_id == patient_id,
            Medication.is_active.is_(True),
        )
        .order_by(Medication.id.asc())
        .all()
    )

    medication_map = {
        medication.id: medication
        for medication in medications
    }

    # Patient's dose records
    dose_records = (
        db.query(DoseRecord)
        .join(
            Medication,
            DoseRecord.medication_id == Medication.id,
        )
        .filter(Medication.patient_id == patient_id)
        .all()
    )

    today_doses = []

    for dose in dose_records:
        scheduled_utc = _as_utc(dose.scheduled_for)

        if scheduled_utc.astimezone(patient_timezone).date() != today:
            continue

        medication = medication_map.get(dose.medication_id)

        if medication is None:
            medication = db.query(Medication).filter(
                Medication.id == dose.medication_id
            ).first()

        if medication is None:
            continue

        today_doses.append({
            "id": dose.id,
            "medication_id": dose.medication_id,
            "medication_name": medication.name,
            "dosage": medication.dosage,
            "scheduled_for": _iso(scheduled_utc),
            "status": dose.status,
            "confirmation_type": dose.confirmation_type,
            "confirmed_by_name": dose.confirmed_by_name,
            "confirmed_by_role": dose.confirmed_by_role,
            "confirmed_at": _iso(_as_utc(dose.confirmed_at)),
            "notes": dose.notes,
        })

    today_doses.sort(
        key=lambda item: item["scheduled_for"]
    )

    # Medication adherence counts
    taken_count = sum(
        dose["status"] == "taken"
        for dose in today_doses
    )

    caregiver_confirmed_count = sum(
        dose["status"] == "caregiver_confirmed"
        for dose in today_doses
    )

    awaiting_count = sum(
        dose["status"] == "awaiting_confirmation"
        for dose in today_doses
    )

    missed_count = sum(
        dose["status"] == "missed"
        for dose in today_doses
    )

    upcoming_dose_count = sum(
        dose["status"] == "upcoming"
        for dose in today_doses
    )

    # Upcoming appointments
    appointments = (
        db.query(Appointment)
        .filter(
            Appointment.patient_id == patient_id,
            Appointment.status == "scheduled",
        )
        .order_by(Appointment.appointment_at.asc())
        .all()
    )

    upcoming_appointments = []

    for appointment in appointments:
        appointment_time = _as_utc(
            appointment.appointment_at
        )

        if appointment_time < current_time:
            continue

        upcoming_appointments.append({
            "id": appointment.id,
            "doctor_name": appointment.doctor_name,
            "specialty": appointment.specialty,
            "location": appointment.location,
            "appointment_at": _iso(appointment_time),
            "notes": appointment.notes,
            "status": appointment.status,
        })

    upcoming_appointments = upcoming_appointments[:10]

    # Recent audit activity
    recent_logs = (
        db.query(AuditLog)
        .filter(AuditLog.patient_id == patient_id)
        .order_by(AuditLog.created_at.desc())
        .limit(10)
        .all()
    )

    recent_activity = [
        {
            "id": log.id,
            "actor_name": log.actor_name,
            "actor_role": log.actor_role,
            "action": log.action,
            "entity_type": log.entity_type,
            "entity_id": log.entity_id,
            "details": log.details,
            "created_at": _iso(_as_utc(log.created_at)),
        }
        for log in recent_logs
    ]

    # Notification delivery summary
    notifications = (
        db.query(Notification)
        .filter(Notification.patient_id == patient_id)
        .all()
    )

    notification_summary = {
        "total": len(notifications),
        "pending": sum(
            item.status == "pending"
            for item in notifications
        ),
        "sent": sum(
            item.status == "sent"
            for item in notifications
        ),
        "failed": sum(
            item.status == "failed"
            for item in notifications
        ),
    }

    return {
        "patient": {
            "id": patient.id,
            "full_name": patient.full_name,
            "email": patient.email,
            "timezone": patient.timezone,
        },
        "generated_at": _iso(current_time),
        "local_date": today.isoformat(),
        "metrics": {
            "active_medications": len(medications),
            "doses_today": len(today_doses),
            "patient_confirmed": taken_count,
            "caregiver_confirmed": caregiver_confirmed_count,
            "awaiting_confirmation": awaiting_count,
            "missed": missed_count,
            "upcoming_doses": upcoming_dose_count,
            "upcoming_appointments": len(upcoming_appointments),
        },
        "today_doses": today_doses,
        "upcoming_appointments": upcoming_appointments,
        "recent_activity": recent_activity,
        "notifications": notification_summary,
    }
