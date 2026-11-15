
from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.database import Base
from backend.app.models import Patient, Medication, DoseRecord
from backend.app.services.medication_service import update_dose_statuses


def test_dose_status_transitions():
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

    try:
        patient = Patient(
            full_name="Test Patient",
            email="status.test@example.com",
            timezone="Asia/Kolkata",
            passcode_hash="test-hash",
            is_active=True,
        )

        db.add(patient)
        db.flush()

        now = datetime(
            2026, 11, 15, 13, 0, tzinfo=timezone.utc
        )

        test_cases = [
            {
                "name": "Future Dose",
                "scheduled": datetime(
                    2026, 11, 15, 13, 1, tzinfo=timezone.utc
                ),
                "expected": "upcoming",
            },
            {
                "name": "Grace Period Dose",
                "scheduled": datetime(
                    2026, 11, 15, 12, 45, tzinfo=timezone.utc
                ),
                "expected": "awaiting_confirmation",
            },
            {
                "name": "Expired Grace Period Dose",
                "scheduled": datetime(
                    2026, 11, 15, 12, 29, tzinfo=timezone.utc
                ),
                "expected": "missed",
            },
            {
                "name": "Patient Confirmed Dose",
                "scheduled": datetime(
                    2026, 11, 15, 12, 0, tzinfo=timezone.utc
                ),
                "expected": "taken",
                "initial_status": "taken",
            },
            {
                "name": "Caregiver Confirmed Dose",
                "scheduled": datetime(
                    2026, 11, 15, 12, 0, tzinfo=timezone.utc
                ),
                "expected": "caregiver_confirmed",
                "initial_status": "caregiver_confirmed",
            },
        ]

        doses = []

        for case in test_cases:
            medication = Medication(
                patient_id=patient.id,
                name=case["name"],
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

            dose = DoseRecord(
                medication_id=medication.id,
                scheduled_for=case["scheduled"],
                status=case.get(
                    "initial_status",
                    "awaiting_confirmation",
                ),
            )

            db.add(dose)
            doses.append((dose, case["expected"]))

        db.commit()

        result = update_dose_statuses(
            patient_id=patient.id,
            db=db,
            now=now,
        )

        for dose, expected in doses:
            db.refresh(dose)

            assert dose.status == expected, (
                f"{dose.medication.name}: "
                f"expected {expected}, got {dose.status}"
            )

        assert result["checked"] == 5

        print("\nDOSE STATUS TRANSITION TEST: PASSED")

        for dose, expected in doses:
            print(
                dose.medication.name,
                "->",
                dose.status,
                "| Expected:",
                expected,
            )

    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()
