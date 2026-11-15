
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.app.auth import require_permission
from backend.app.database import get_db
from backend.app.services.appointment_service import (
    create_appointment,
    list_appointments,
    update_appointment,
    cancel_appointment,
)


router = APIRouter(
    prefix="/api/appointments",
    tags=["Appointment Management"],
)


class AppointmentCreateRequest(BaseModel):
    doctor_name: str = Field(min_length=2, max_length=150)
    specialty: str | None = Field(default=None, max_length=120)
    location: str | None = Field(default=None, max_length=255)
    appointment_at: datetime
    notes: str | None = Field(default=None, max_length=2000)


class AppointmentUpdateRequest(BaseModel):
    doctor_name: str | None = Field(default=None, min_length=2, max_length=150)
    specialty: str | None = Field(default=None, max_length=120)
    location: str | None = Field(default=None, max_length=255)
    appointment_at: datetime | None = None
    notes: str | None = Field(default=None, max_length=2000)


def appointment_response(appointment):
    return {
        "id": appointment.id,
        "patient_id": appointment.patient_id,
        "doctor_name": appointment.doctor_name,
        "specialty": appointment.specialty,
        "location": appointment.location,
        "appointment_at": appointment.appointment_at.isoformat(),
        "notes": appointment.notes,
        "status": appointment.status,
        "created_at": (
            appointment.created_at.isoformat()
            if appointment.created_at else None
        ),
    }


@router.post("", status_code=status.HTTP_201_CREATED)
def add_appointment(
    payload: AppointmentCreateRequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_permission("can_manage_appointments")),
):
    appointment = create_appointment(
        patient_id=current_user["patient_id"],
        actor=current_user,
        doctor_name=payload.doctor_name,
        specialty=payload.specialty,
        location=payload.location,
        appointment_at=payload.appointment_at,
        notes=payload.notes,
        db=db,
    )

    return {
        "message": "Appointment created successfully.",
        "appointment": appointment_response(appointment),
    }


@router.get("")
def get_appointments(
    include_cancelled: bool = False,
    db: Session = Depends(get_db),
    current_user=Depends(require_permission("can_manage_appointments")),
):
    appointments = list_appointments(
        patient_id=current_user["patient_id"],
        db=db,
        include_cancelled=include_cancelled,
    )

    return {
        "appointments": [
            appointment_response(item) for item in appointments
        ]
    }


@router.put("/{appointment_id}")
def edit_appointment(
    appointment_id: int,
    payload: AppointmentUpdateRequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_permission("can_manage_appointments")),
):
    updates = payload.model_dump(exclude_unset=True)

    if not updates:
        raise HTTPException(
            status_code=400,
            detail="Provide at least one field to update.",
        )

    appointment = update_appointment(
        patient_id=current_user["patient_id"],
        appointment_id=appointment_id,
        actor=current_user,
        updates=updates,
        db=db,
    )

    return {
        "message": "Appointment updated successfully.",
        "appointment": appointment_response(appointment),
    }


@router.delete("/{appointment_id}")
def remove_appointment(
    appointment_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_permission("can_manage_appointments")),
):
    appointment = cancel_appointment(
        patient_id=current_user["patient_id"],
        appointment_id=appointment_id,
        actor=current_user,
        db=db,
    )

    return {
        "message": "Appointment cancelled successfully.",
        "appointment": appointment_response(appointment),
    }
