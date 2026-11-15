
from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.database import Base
from backend.app.models import (
    Patient,
    Medication,
    DoseRecord,
    Appointment,
    Notification,
    AuditLog,
)
from backend.app.services.dashboard_service import get_dashboard_data


def test_dashboard_data():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    Base.metadata.create_all(bind=engine)
    TestSession = sessionmaker(bind=engine)
    db = TestSession()

    try:
        patient = Patient(
            full_name="Dashboard Test Patient",
            email="dashboard.test@example.com",
            timezone="Asia/Kolkata",
            passcode_hash="test-hash",
            is_active=True,
        )

        db.add(patient)
        db.flush()

        medication = Medication(
            patient_id=patient.id,
            name="Test Medication",
            dosage="1 tablet",
            frequency="daily",
            times_per_day=1,
            schedule_times='["18:00"]',
            start_date="2026-11-15",
            grace_period_minutes=30,
            is_active=True,
        )

        db.add(medication)
        db.flush()

        now = datetime(
            2026, 11, 15, 12, 0,
            tzinfo=timezone.utc,
        )

        doses = [
            DoseRecord(
                medication_id=medication.id,
                scheduled_for=datetime(
                    2026, 11, 15, 11, 0,
                    tzinfo=timezone.utc,
                ),
                status="taken",
                confirmation_type="patient",
                confirmed_by_name="Dashboard Test Patient",
                confirmed_by_role="patient",
                confirmed_at=now,
            ),
            DoseRecord(
                medication_id=medication.id,
                scheduled_for=datetime(
                    2026, 11, 15, 12, 30,
                    tzinfo=timezone.utc,
                ),
                status="caregiver_confirmed",
                confirmation_type="caregiver",
                confirmed_by_name="Test Caregiver",
                confirmed_by_role="family",
                confirmed_at=now,
            ),
            DoseRecord(
                medication_id=medication.id,
                scheduled_for=datetime(
                    2026, 11, 15, 13, 0,
                    tzinfo=timezone.utc,
                ),
                status="upcoming",
            ),
        ]

        db.add_all(doses)

        appointment = Appointment(
            patient_id=patient.id,
            doctor_name="Dr. Dashboard",
            specialty="General Medicine",
            location="Test Hospital",
            appointment_at=datetime(
                2026, 11, 20, 10, 0,
                tzinfo=timezone.utc,
            ),
            notes="Routine checkup",
            status="scheduled",
        )

        notification = Notification(
            patient_id=patient.id,
            recipient_email=patient.email,
            notification_type="medication_reminder",
            subject="Test reminder",
            message="Test notification",
            status="pending",
            attempts=0,
            scheduled_at=now,
        )

        audit = AuditLog(
            patient_id=patient.id,
            actor_user_id=patient.id,
            actor_name=patient.full_name,
            actor_role="patient",
            action="medication_confirmed",
            entity_type="dose",
            entity_id=1,
            details="Test audit event",
        )

        db.add_all([appointment, notification, audit])
        db.commit()

        dashboard = get_dashboard_data(
            patient_id=patient.id,
            db=db,
            now=now,
        )

        assert dashboard is not None
        assert dashboard["patient"]["full_name"] == patient.full_name

        metrics = dashboard["metrics"]

        assert metrics["active_medications"] == 1
        assert metrics["doses_today"] == 3
        assert metrics["patient_confirmed"] == 1
        assert metrics["caregiver_confirmed"] == 1
        assert metrics["upcoming_doses"] == 1
        assert metrics["upcoming_appointments"] == 1

        assert len(dashboard["today_doses"]) == 3
        assert dashboard["today_doses"][0]["status"] == "taken"

        assert dashboard["today_doses"][1]["status"] == (
            "caregiver_confirmed"
        )

        assert dashboard["upcoming_appointments"][0]["doctor_name"] == (
            "Dr. Dashboard"
        )

        assert dashboard["notifications"]["pending"] == 1
        assert len(dashboard["recent_activity"]) == 1

        assert get_dashboard_data(
            patient_id=9999,
            db=db,
            now=now,
        ) is None

        print("\nDASHBOARD SERVICE TEST: PASSED")
        print("Patient profile: PASSED")
        print("Medication metrics: PASSED")
        print("Patient/caregiver confirmation distinction: PASSED")
        print("Upcoming appointments: PASSED")
        print("Notification summary: PASSED")
        print("Recent activity: PASSED")
        print("Patient data isolation: PASSED")

    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()
