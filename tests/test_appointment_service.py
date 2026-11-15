
from datetime import datetime, timezone

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.database import Base
from backend.app.models import Patient, Appointment, AuditLog
from backend.app.services.appointment_service import (
    create_appointment,
    list_appointments,
    update_appointment,
    cancel_appointment,
)


def test_appointment_lifecycle_and_audit():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    Base.metadata.create_all(bind=engine)

    TestSession = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine,
    )

    db = TestSession()

    actor = {
        "user_id": 1,
        "name": "Test Patient",
        "role": "patient",
    }

    try:
        patient = Patient(
            full_name="Test Patient",
            email="appointment.test@example.com",
            timezone="Asia/Kolkata",
            passcode_hash="test-hash",
            is_active=True,
        )

        db.add(patient)
        db.flush()

        other_patient = Patient(
            full_name="Other Patient",
            email="other.appointment.test@example.com",
            timezone="Asia/Kolkata",
            passcode_hash="test-hash",
            is_active=True,
        )

        db.add(other_patient)
        db.commit()

        appointment_time = datetime(
            2026, 11, 20, 10, 0,
            tzinfo=timezone.utc,
        )

        appointment = create_appointment(
            patient_id=patient.id,
            actor=actor,
            doctor_name="Dr. Test",
            specialty="General Medicine",
            location="City Hospital",
            appointment_at=appointment_time,
            notes="Initial appointment",
            db=db,
        )

        assert appointment.id is not None
        assert appointment.status == "scheduled"
        assert appointment.doctor_name == "Dr. Test"

        logs = db.query(AuditLog).filter(
            AuditLog.entity_type == "appointment",
            AuditLog.entity_id == appointment.id,
        ).all()

        assert len(logs) == 1
        assert logs[0].action == "appointment_created"

        appointments = list_appointments(
            patient_id=patient.id,
            db=db,
        )

        assert len(appointments) == 1

        assert list_appointments(
            patient_id=other_patient.id,
            db=db,
        ) == []

        with pytest.raises(HTTPException) as error:
            update_appointment(
                patient_id=other_patient.id,
                appointment_id=appointment.id,
                actor=actor,
                updates={"doctor_name": "Unauthorized Change"},
                db=db,
            )

        assert error.value.status_code == 404

        updated = update_appointment(
            patient_id=patient.id,
            appointment_id=appointment.id,
            actor=actor,
            updates={
                "doctor_name": "Dr. Updated",
                "notes": "Updated appointment notes",
            },
            db=db,
        )

        assert updated.doctor_name == "Dr. Updated"
        assert updated.notes == "Updated appointment notes"

        cancelled = cancel_appointment(
            patient_id=patient.id,
            appointment_id=appointment.id,
            actor=actor,
            db=db,
        )

        assert cancelled.status == "cancelled"

        visible_appointments = list_appointments(
            patient_id=patient.id,
            db=db,
        )

        assert len(visible_appointments) == 0

        all_appointments = list_appointments(
            patient_id=patient.id,
            db=db,
            include_cancelled=True,
        )

        assert len(all_appointments) == 1

        logs = db.query(AuditLog).filter(
            AuditLog.entity_type == "appointment",
            AuditLog.entity_id == appointment.id,
        ).order_by(AuditLog.id).all()

        actions = [log.action for log in logs]

        assert actions == [
            "appointment_created",
            "appointment_updated",
            "appointment_cancelled",
        ]

        print("\nAPPOINTMENT SERVICE TEST: PASSED")
        print("Creation: PASSED")
        print("Patient data isolation: PASSED")
        print("Update: PASSED")
        print("Cancellation: PASSED")
        print("Audit history: PASSED")

    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()
