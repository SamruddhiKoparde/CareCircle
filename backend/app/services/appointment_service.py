
import json
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy.orm import Session

from backend.app.models import Appointment, AuditLog


def _write_audit_log(
    db: Session,
    patient_id: int,
    actor: dict,
    action: str,
    appointment: Appointment,
    details: dict | None = None,
):
    """Record an appointment action in the audit history."""

    log = AuditLog(
        patient_id=patient_id,
        actor_user_id=actor["user_id"],
        actor_name=actor["name"],
        actor_role=actor["role"],
        action=action,
        entity_type="appointment",
        entity_id=appointment.id,
        details=json.dumps(details or {}),
    )

    db.add(log)


def create_appointment(
    patient_id: int,
    actor: dict,
    doctor_name: str,
    specialty: str | None,
    location: str | None,
    appointment_at: datetime,
    notes: str | None,
    db: Session,
):
    """Create an appointment and record the action."""

    if appointment_at.tzinfo is None or appointment_at.utcoffset() is None:
        raise HTTPException(
            status_code=400,
            detail="Appointment time must include a timezone.",
        )

    appointment = Appointment(
        patient_id=patient_id,
        doctor_name=doctor_name.strip(),
        specialty=specialty.strip() if specialty else None,
        location=location.strip() if location else None,
        appointment_at=appointment_at.astimezone(timezone.utc),
        notes=notes.strip() if notes else None,
        status="scheduled",
    )

    try:
        db.add(appointment)
        db.flush()

        _write_audit_log(
            db=db,
            patient_id=patient_id,
            actor=actor,
            action="appointment_created",
            appointment=appointment,
            details={
                "doctor_name": appointment.doctor_name,
                "appointment_at": appointment.appointment_at.isoformat(),
            },
        )

        db.commit()
        db.refresh(appointment)

        return appointment

    except Exception:
        db.rollback()
        raise


def list_appointments(
    patient_id: int,
    db: Session,
    include_cancelled: bool = False,
):
    """List appointments belonging only to the specified patient."""

    query = db.query(Appointment).filter(
        Appointment.patient_id == patient_id
    )

    if not include_cancelled:
        query = query.filter(Appointment.status != "cancelled")

    return query.order_by(
        Appointment.appointment_at.asc()
    ).all()


def update_appointment(
    patient_id: int,
    appointment_id: int,
    actor: dict,
    updates: dict,
    db: Session,
):
    """Update an appointment and record the changes."""

    appointment = db.query(Appointment).filter(
        Appointment.id == appointment_id,
        Appointment.patient_id == patient_id,
    ).first()

    if not appointment:
        raise HTTPException(
            status_code=404,
            detail="Appointment not found.",
        )

    if appointment.status == "cancelled":
        raise HTTPException(
            status_code=409,
            detail="A cancelled appointment cannot be updated.",
        )

    if "appointment_at" in updates:
        appointment_at = updates["appointment_at"]

        if (
            appointment_at.tzinfo is None
            or appointment_at.utcoffset() is None
        ):
            raise HTTPException(
                status_code=400,
                detail="Appointment time must include a timezone.",
            )

        updates["appointment_at"] = appointment_at.astimezone(
            timezone.utc
        )

    old_values = {}

    for field, value in updates.items():
        old_value = getattr(appointment, field)

        old_values[field] = (
            old_value.isoformat()
            if isinstance(old_value, datetime)
            else old_value
        )

        if isinstance(value, str):
            value = value.strip()

        setattr(appointment, field, value)

    try:
        _write_audit_log(
            db=db,
            patient_id=patient_id,
            actor=actor,
            action="appointment_updated",
            appointment=appointment,
            details={"previous_values": old_values},
        )

        db.commit()
        db.refresh(appointment)

        return appointment

    except Exception:
        db.rollback()
        raise


def cancel_appointment(
    patient_id: int,
    appointment_id: int,
    actor: dict,
    db: Session,
):
    """Cancel an appointment without deleting its history."""

    appointment = db.query(Appointment).filter(
        Appointment.id == appointment_id,
        Appointment.patient_id == patient_id,
    ).first()

    if not appointment:
        raise HTTPException(
            status_code=404,
            detail="Appointment not found.",
        )

    if appointment.status == "cancelled":
        raise HTTPException(
            status_code=409,
            detail="Appointment is already cancelled.",
        )

    previous_status = appointment.status
    appointment.status = "cancelled"

    try:
        _write_audit_log(
            db=db,
            patient_id=patient_id,
            actor=actor,
            action="appointment_cancelled",
            appointment=appointment,
            details={"previous_status": previous_status},
        )

        db.commit()
        db.refresh(appointment)

        return appointment

    except Exception:
        db.rollback()
        raise
