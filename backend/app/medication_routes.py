
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.app.auth import get_current_user, require_permission
from backend.app.database import get_db
from backend.app.services.medication_service import (
    add_medication,
    list_medications,
    update_medication,
    deactivate_medication,
    generate_daily_doses,
    list_doses,
    confirm_dose,
)

router = APIRouter(
    prefix="/api/medications",
    tags=["Medication Management"],
)


class MedicationCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    dosage: str = Field(min_length=1, max_length=100)
    instructions: str = Field(default="", max_length=1000)
    frequency: str = Field(default="Daily", max_length=50)
    schedule_times: list[str] = Field(min_length=1, max_length=12)
    start_date: date
    end_date: date | None = None
    grace_period_minutes: int = Field(default=30, ge=0, le=1440)


class MedicationUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=150)
    dosage: str | None = Field(default=None, min_length=1, max_length=100)
    instructions: str | None = Field(default=None, max_length=1000)
    frequency: str | None = Field(default=None, max_length=50)
    schedule_times: list[str] | None = Field(default=None, min_length=1, max_length=12)
    start_date: date | None = None
    end_date: date | None = None
    grace_period_minutes: int | None = Field(default=None, ge=0, le=1440)


class DoseConfirmationRequest(BaseModel):
    notes: str = Field(default="", max_length=1000)


def medication_response(medication):
    return {
        "id": medication.id,
        "patient_id": medication.patient_id,
        "name": medication.name,
        "dosage": medication.dosage,
        "instructions": medication.instructions,
        "frequency": medication.frequency,
        "times_per_day": medication.times_per_day,
        "schedule_times": medication.schedule_times,
        "start_date": (
            medication.start_date.isoformat()
            if hasattr(medication.start_date, "isoformat")
            else medication.start_date
        ),
        "end_date": (
            medication.end_date.isoformat()
            if hasattr(medication.end_date, "isoformat")
            else medication.end_date
        ),
        "grace_period_minutes": medication.grace_period_minutes,
        "is_active": medication.is_active,
    }

def dose_response(dose):
    return {
        "id": dose.id,
        "medication_id": dose.medication_id,
        "scheduled_for": dose.scheduled_for.isoformat(),
        "status": dose.status,
        "confirmation_type": dose.confirmation_type,
        "confirmer_id": dose.confirmed_by_user_id,
        "confirmer_name": dose.confirmed_by_name,
        "confirmer_role": dose.confirmed_by_role,
        "confirmed_at": (
            dose.confirmed_at.isoformat()
            if dose.confirmed_at else None
        ),
        "notes": dose.notes,
    }


@router.post("", status_code=status.HTTP_201_CREATED)
def create_medication(
    payload: MedicationCreateRequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_permission("can_manage_medications")),
):
    medication = add_medication(
        patient_id=current_user["patient_id"],
        name=payload.name,
        dosage=payload.dosage,
        instructions=payload.instructions,
        frequency=payload.frequency,
        schedule_times=payload.schedule_times,
        start_date=payload.start_date,
        end_date=payload.end_date,
        grace_period_minutes=payload.grace_period_minutes,
        db=db,
    )

    return {
        "message": "Medication added successfully.",
        "medication": medication_response(medication),
    }


@router.get("")
def get_medications(
    include_inactive: bool = False,
    db: Session = Depends(get_db),
    current_user=Depends(require_permission("can_view_medications")),
):
    medications = list_medications(
        patient_id=current_user["patient_id"],
        db=db,
        include_inactive=include_inactive,
    )

    return {
        "medications": [
            medication_response(item) for item in medications
        ]
    }


@router.put("/{medication_id}")
def edit_medication(
    medication_id: int,
    payload: MedicationUpdateRequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_permission("can_manage_medications")),
):
    updates = payload.model_dump(exclude_unset=True)

    if not updates:
        raise HTTPException(
            status_code=400,
            detail="Provide at least one field to update.",
        )

    medication = update_medication(
        patient_id=current_user["patient_id"],
        medication_id=medication_id,
        updates=updates,
        db=db,
    )

    return {
        "message": "Medication updated successfully.",
        "medication": medication_response(medication),
    }


@router.delete("/{medication_id}")
def remove_medication(
    medication_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_permission("can_manage_medications")),
):
    medication = deactivate_medication(
        patient_id=current_user["patient_id"],
        medication_id=medication_id,
        db=db,
    )

    return {
        "message": "Medication deactivated. Its history has been preserved.",
        "medication_id": medication.id,
    }


@router.post("/doses/generate")
def create_daily_doses(
    target_date: date,
    db: Session = Depends(get_db),
    current_user=Depends(require_permission("can_manage_medications")),
):
    return generate_daily_doses(
        patient_id=current_user["patient_id"],
        target_date=target_date,
        db=db,
    )


@router.get("/doses")
def get_daily_doses(
    target_date: date,
    db: Session = Depends(get_db),
    current_user=Depends(require_permission("can_view_medications")),
):
    doses = list_doses(
        patient_id=current_user["patient_id"],
        target_date=target_date,
        db=db,
    )

    return {
        "doses": [dose_response(item) for item in doses]
    }


@router.post("/doses/{dose_id}/confirm")
def report_dose_taken(
    dose_id: int,
    payload: DoseConfirmationRequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_permission("can_confirm_doses")),
):
    dose = confirm_dose(
        patient_id=current_user["patient_id"],
        dose_id=dose_id,
        actor_id=current_user["user_id"],
        actor_name=current_user["name"],
        actor_role=current_user["role"],
        notes=payload.notes,
        db=db,
    )

    return {
        "message": "Dose confirmation recorded.",
        "dose": dose_response(dose),
        "disclaimer": (
            "This records a user-reported confirmation, "
            "not independent proof of medication ingestion."
        ),
    }
