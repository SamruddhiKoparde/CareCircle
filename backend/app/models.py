
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from backend.app.database import Base


def utc_now():
    return datetime.now(timezone.utc)


class Patient(Base):
    __tablename__ = "patients"

    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String(120), nullable=False)
    email = Column(String(255), unique=True, nullable=False, index=True)
    phone = Column(String(30), nullable=True)
    timezone = Column(String(60), nullable=False, default="Asia/Kolkata")
    passcode_hash = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now)

    members = relationship(
        "CareMember", back_populates="patient", cascade="all, delete-orphan"
    )
    medications = relationship(
        "Medication", back_populates="patient", cascade="all, delete-orphan"
    )
    appointments = relationship(
        "Appointment", back_populates="patient", cascade="all, delete-orphan"
    )


class CareMember(Base):
    __tablename__ = "care_members"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False)
    full_name = Column(String(120), nullable=False)
    email = Column(String(255), nullable=False)
    role = Column(String(30), nullable=False)  # family or caretaker

    can_view_profile = Column(Boolean, default=True, nullable=False)
    can_view_medications = Column(Boolean, default=True, nullable=False)
    can_manage_medications = Column(Boolean, default=False, nullable=False)
    can_confirm_doses = Column(Boolean, default=False, nullable=False)
    can_manage_appointments = Column(Boolean, default=False, nullable=False)

    passcode_hash = Column(String(255), nullable=True)
    invitation_token_hash = Column(String(255), nullable=True)
    invitation_expires_at = Column(DateTime(timezone=True), nullable=True)

    invitation_status = Column(String(30), default="pending", nullable=False)
    is_active = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now)

    patient = relationship("Patient", back_populates="members")


class Medication(Base):
    __tablename__ = "medications"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False)
    name = Column(String(150), nullable=False)
    dosage = Column(String(100), nullable=False)
    instructions = Column(Text, nullable=True)
    frequency = Column(String(50), nullable=False, default="daily")
    times_per_day = Column(Integer, default=1, nullable=False)
    schedule_times = Column(Text, nullable=False)  # JSON list of local times
    start_date = Column(String(10), nullable=False)
    end_date = Column(String(10), nullable=True)
    grace_period_minutes = Column(Integer, default=60, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now)

    patient = relationship("Patient", back_populates="medications")
    doses = relationship(
        "DoseRecord", back_populates="medication", cascade="all, delete-orphan"
    )


class DoseRecord(Base):
    __tablename__ = "dose_records"
    __table_args__ = (
        UniqueConstraint(
            "medication_id",
            "scheduled_for",
            name="uq_medication_scheduled_dose",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    medication_id = Column(Integer, ForeignKey("medications.id"), nullable=False)
    scheduled_for = Column(DateTime(timezone=True), nullable=False)
    status = Column(String(40), nullable=False, default="awaiting_confirmation")
    confirmation_type = Column(String(40), nullable=True)
    confirmed_by_user_id = Column(Integer, nullable=True)
    confirmed_by_name = Column(String(120), nullable=True)
    confirmed_by_role = Column(String(30), nullable=True)
    confirmed_at = Column(DateTime(timezone=True), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)

    medication = relationship("Medication", back_populates="doses")


class Appointment(Base):
    __tablename__ = "appointments"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False)
    doctor_name = Column(String(150), nullable=False)
    specialty = Column(String(120), nullable=True)
    location = Column(String(255), nullable=True)
    appointment_at = Column(DateTime(timezone=True), nullable=False)
    notes = Column(Text, nullable=True)
    status = Column(String(30), default="scheduled", nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now)

    patient = relationship("Patient", back_populates="appointments")


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False)
    recipient_email = Column(String(255), nullable=False)
    notification_type = Column(String(50), nullable=False)
    subject = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    status = Column(String(30), default="pending", nullable=False)
    attempts = Column(Integer, default=0, nullable=False)
    scheduled_at = Column(DateTime(timezone=True), nullable=True)
    sent_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False)
    actor_user_id = Column(Integer, nullable=False)
    actor_name = Column(String(120), nullable=False)
    actor_role = Column(String(30), nullable=False)
    action = Column(String(80), nullable=False)
    entity_type = Column(String(50), nullable=False)
    entity_id = Column(Integer, nullable=False)
    details = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)
