
import json
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.models import Medication, DoseRecord, AuditLog, Patient


def _parse_schedule(schedule_times):
    """Validate and normalize a list of daily dose times."""
    if not isinstance(schedule_times, list) or not schedule_times:
        raise ValueError("At least one daily medication time is required.")

    normalized = []

    for value in schedule_times:
        try:
            parsed = time.fromisoformat(value)
        except (TypeError, ValueError):
            raise ValueError(f"Invalid medication time: {value}")

        normalized.append(parsed.strftime("%H:%M"))

    if len(set(normalized)) != len(normalized):
        raise ValueError("Duplicate medication times are not allowed.")

    return sorted(normalized)


def add_medication(
    patient_id: int,
    name: str,
    dosage: str,
    instructions: str,
    frequency: str,
    schedule_times: list,
    start_date: date,
    end_date: date | None,
    grace_period_minutes: int,
    db: Session,
):
    """Create a medication belonging to a patient."""

    if not isinstance(name, str) or not name.strip():
        raise HTTPException(status_code=400, detail="Medication name is required.")

    if not isinstance(dosage, str) or not dosage.strip():
        raise HTTPException(status_code=400, detail="Medication dosage is required.")

    if end_date and end_date < start_date:
        raise HTTPException(
            status_code=400,
            detail="End date cannot be before start date.",
        )

    if (
        not isinstance(grace_period_minutes, int)
        or isinstance(grace_period_minutes, bool)
        or not 0 <= grace_period_minutes <= 1440
    ):
        raise HTTPException(
            status_code=400,
            detail="Grace period must be between 0 and 1440 minutes.",
        )

    try:
        normalized_times = _parse_schedule(schedule_times)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    medication = Medication(
        patient_id=patient_id,
        name=name.strip(),
        dosage=dosage.strip(),
        instructions=instructions.strip() if instructions else "",
        frequency=frequency.strip(),
        times_per_day=len(normalized_times),
        schedule_times=json.dumps(normalized_times),
        start_date=start_date,
        end_date=end_date,
        grace_period_minutes=grace_period_minutes,
        is_active=True,
    )

    db.add(medication)
    db.commit()
    db.refresh(medication)

    return medication


def list_medications(
    patient_id: int,
    db: Session,
    include_inactive: bool = False,
):
    """List medications belonging to a patient."""

    query = db.query(Medication).filter(
        Medication.patient_id == patient_id
    )

    if not include_inactive:
        query = query.filter(Medication.is_active.is_(True))

    return query.order_by(Medication.created_at.desc()).all()


def get_medication(
    patient_id: int,
    medication_id: int,
    db: Session,
):
    """Retrieve one medication without crossing patient boundaries."""

    medication = db.query(Medication).filter(
        Medication.id == medication_id,
        Medication.patient_id == patient_id,
    ).first()

    if not medication:
        raise HTTPException(
            status_code=404,
            detail="Medication not found.",
        )

    return medication


def update_medication(
    patient_id: int,
    medication_id: int,
    updates: dict,
    db: Session,
):
    """Update permitted medication fields."""

    medication = get_medication(patient_id, medication_id, db)

    allowed_fields = {
        "name",
        "dosage",
        "instructions",
        "frequency",
        "schedule_times",
        "start_date",
        "end_date",
        "grace_period_minutes",
    }

    if set(updates) - allowed_fields:
        raise HTTPException(
            status_code=400,
            detail="One or more medication fields cannot be updated.",
        )

    updates = updates.copy()

    if "schedule_times" in updates:
        try:
            normalized = _parse_schedule(updates["schedule_times"])
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

        updates["schedule_times"] = json.dumps(normalized)
        updates["times_per_day"] = len(normalized)

    for field in ("name", "dosage"):
        if field in updates:
            value = updates[field]

            if not isinstance(value, str) or not value.strip():
                raise HTTPException(
                    status_code=400,
                    detail=f"{field.capitalize()} cannot be empty.",
                )

            updates[field] = value.strip()

    if "grace_period_minutes" in updates:
        value = updates["grace_period_minutes"]

        if (
            not isinstance(value, int)
            or isinstance(value, bool)
            or not 0 <= value <= 1440
        ):
            raise HTTPException(
                status_code=400,
                detail="Grace period must be between 0 and 1440 minutes.",
            )

    new_start = updates.get("start_date", medication.start_date)
    new_end = updates.get("end_date", medication.end_date)

    if new_end and new_end < new_start:
        raise HTTPException(
            status_code=400,
            detail="End date cannot be before start date.",
        )

    for field, value in updates.items():
        setattr(medication, field, value)

    db.commit()
    db.refresh(medication)

    return medication


def deactivate_medication(
    patient_id: int,
    medication_id: int,
    db: Session,
):
    """Deactivate medication without deleting its history."""

    medication = get_medication(patient_id, medication_id, db)
    medication.is_active = False

    db.commit()
    db.refresh(medication)

    return medication


def generate_daily_doses(
    patient_id: int,
    target_date: date,
    db: Session,
):
    """Generate doses using patient-local time and store timestamps in UTC."""

    patient = db.query(Patient).filter(
        Patient.id == patient_id
    ).first()

    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found.")

    try:
        patient_timezone = ZoneInfo(patient.timezone)
    except (ZoneInfoNotFoundError, TypeError):
        raise HTTPException(status_code=400, detail="Patient timezone is invalid.")

    medications = db.query(Medication).filter(
        Medication.patient_id == patient_id,
        Medication.is_active.is_(True),
        Medication.start_date <= target_date,
    ).all()

    created = 0
    current_utc = datetime.now(timezone.utc)

    for medication in medications:
        if medication.end_date and medication.end_date < target_date:
            continue

        try:
            schedule = json.loads(medication.schedule_times)
        except (TypeError, json.JSONDecodeError):
            continue

        for scheduled_time in schedule:
            parsed_time = time.fromisoformat(scheduled_time)

            local_scheduled = datetime.combine(
                target_date,
                parsed_time,
                tzinfo=patient_timezone,
            )

            scheduled_for = local_scheduled.astimezone(timezone.utc)

            existing = db.query(DoseRecord).filter(
                DoseRecord.medication_id == medication.id,
                DoseRecord.scheduled_for == scheduled_for,
            ).first()

            if existing:
                continue

            initial_status = (
                "upcoming"
                if scheduled_for > current_utc
                else "awaiting_confirmation"
            )

            dose = DoseRecord(
                medication_id=medication.id,
                scheduled_for=scheduled_for,
                status=initial_status,
            )

            db.add(dose)
            created += 1

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="A dose record already exists for this schedule.",
        )

    return {
        "created": created,
        "date": target_date.isoformat(),
        "timezone": patient.timezone,
    }


def list_doses(
    patient_id: int,
    target_date: date,
    db: Session,
):
    """List doses falling within the patient's local calendar day."""

    patient = db.query(Patient).filter(
        Patient.id == patient_id
    ).first()

    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found.")

    try:
        patient_timezone = ZoneInfo(patient.timezone)
    except (ZoneInfoNotFoundError, TypeError):
        raise HTTPException(status_code=400, detail="Patient timezone is invalid.")

    local_start = datetime.combine(
        target_date,
        time.min,
        tzinfo=patient_timezone,
    )

    local_end = local_start + timedelta(days=1)

    utc_start = local_start.astimezone(timezone.utc)
    utc_end = local_end.astimezone(timezone.utc)

    return (
        db.query(DoseRecord)
        .join(Medication)
        .filter(
            Medication.patient_id == patient_id,
            DoseRecord.scheduled_for >= utc_start,
            DoseRecord.scheduled_for < utc_end,
        )
        .order_by(DoseRecord.scheduled_for.asc())
        .all()
    )


def update_dose_statuses(
    patient_id: int,
    db: Session,
    now: datetime | None = None,
):
    """
    Update dose statuses based on scheduled time and grace period.

    This function never overwrites patient or caregiver confirmations.
    Unconfirmed means no report has been recorded; it does not prove
    that medication was not physically taken.
    """

    now = now or datetime.now(timezone.utc)

    if now.tzinfo is None:
        raise ValueError("The current time must be timezone-aware.")

    now = now.astimezone(timezone.utc)

    doses = (
        db.query(DoseRecord)
        .join(Medication)
        .filter(
            Medication.patient_id == patient_id,
            Medication.is_active.is_(True),
        )
        .all()
    )

    updated = {
        "upcoming": 0,
        "awaiting_confirmation": 0,
        "unconfirmed": 0,
        "missed": 0,
    }

    confirmed_statuses = {"taken", "caregiver_confirmed"}

    try:
        for dose in doses:
            if dose.status in confirmed_statuses:
                continue

            medication = dose.medication

            scheduled_for = dose.scheduled_for

            # SQLite may return naive datetime values despite
            # timezone=True. Stored values are UTC.
            if scheduled_for.tzinfo is None:
                scheduled_for = scheduled_for.replace(tzinfo=timezone.utc)
            else:
                scheduled_for = scheduled_for.astimezone(timezone.utc)

            grace_deadline = scheduled_for + timedelta(
                minutes=medication.grace_period_minutes
            )

            if now < scheduled_for:
                new_status = "upcoming"
            elif now <= grace_deadline:
                new_status = "awaiting_confirmation"
            else:
                new_status = "missed"

            if dose.status != new_status:
                dose.status = new_status
                updated[new_status] += 1

        db.commit()

    except Exception:
        db.rollback()
        raise

    return {
        "updated": updated,
        "checked": len(doses),
        "checked_at": now.isoformat(),
    }


def confirm_dose(
    patient_id: int,
    dose_id: int,
    actor_id: int,
    actor_name: str,
    actor_role: str,
    db: Session,
    notes: str = "",
):
    """
    Record who reported a dose as taken.
    This records a report, not independent proof of ingestion.
    """

    dose = (
        db.query(DoseRecord)
        .join(Medication)
        .filter(
            DoseRecord.id == dose_id,
            Medication.patient_id == patient_id,
            Medication.is_active.is_(True),
        )
        .first()
    )

    if not dose:
        raise HTTPException(
            status_code=404,
            detail="Dose record not found.",
        )

    if dose.status in ("taken", "caregiver_confirmed"):
        raise HTTPException(
            status_code=409,
            detail="This dose has already been confirmed.",
        )

    if actor_role not in ("patient", "family", "caretaker"):
        raise HTTPException(
            status_code=403,
            detail="This account cannot confirm medication doses.",
        )

    if actor_role == "patient":
        dose.status = "taken"
        dose.confirmation_type = "patient_self_reported"
    else:
        dose.status = "caregiver_confirmed"
        dose.confirmation_type = "caregiver_reported"

    dose.confirmed_by_user_id = actor_id
    dose.confirmed_by_name = actor_name
    dose.confirmed_by_role = actor_role
    dose.confirmed_at = datetime.now(timezone.utc)
    dose.notes = notes.strip() if notes else ""

    audit_entry = AuditLog(
        patient_id=patient_id,
        actor_user_id=actor_id,
        actor_name=actor_name,
        actor_role=actor_role,
        action="dose.confirmed",
        entity_type="dose_record",
        entity_id=dose.id,
        details=json.dumps({
            "medication_id": dose.medication_id,
            "status": dose.status,
            "confirmation_type": dose.confirmation_type,
            "scheduled_for": dose.scheduled_for.isoformat(),
            "confirmed_at": dose.confirmed_at.isoformat(),
            "notes": dose.notes,
        }),
    )

    db.add(audit_entry)
    db.commit()
    db.refresh(dose)

    return dose
