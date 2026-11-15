
from datetime import datetime, timezone

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from backend.app.config import SESSION_EXPIRE_MINUTES
from backend.app.database import get_db
from backend.app.models import CareMember, Patient
from backend.app.security import (
    generate_session_token,
    get_session_expiry,
    hash_passcode,
    verify_passcode,
)

# Temporary in-memory session storage for the MVP.
SESSIONS = {}


def register_patient(
    full_name: str,
    email: str,
    passcode: str,
    db: Session,
):
    """Register a patient and store only their passcode hash."""
    existing = db.query(Patient).filter(
        Patient.email == email.lower().strip()
    ).first()

    if existing:
        raise HTTPException(
            status_code=409,
            detail="An account with this email already exists.",
        )

    patient = Patient(
        full_name=full_name.strip(),
        email=email.lower().strip(),
        passcode_hash=hash_passcode(passcode),
    )

    db.add(patient)
    db.commit()
    db.refresh(patient)

    return patient


def login_patient(email: str, passcode: str, db: Session):
    """Authenticate a patient and create a session."""
    patient = db.query(Patient).filter(
        Patient.email == email.lower().strip(),
        Patient.is_active.is_(True),
    ).first()

    if not patient or not verify_passcode(passcode, patient.passcode_hash):
        raise HTTPException(
            status_code=401,
            detail="Invalid email or passcode.",
        )

    token = generate_session_token()

    SESSIONS[token] = {
        "user_id": patient.id,
        "patient_id": patient.id,
        "name": patient.full_name,
        "role": "patient",
        "expires_at": get_session_expiry(SESSION_EXPIRE_MINUTES),
    }

    return token


def login_member(
    email: str,
    passcode: str,
    db: Session,
):
    """Authenticate an authorized family member or caretaker."""
    from backend.app.users import authenticate_member

    member = authenticate_member(
        email=email,
        passcode=passcode,
        db=db,
    )

    token = generate_session_token()

    SESSIONS[token] = {
        "user_id": member.id,
        "patient_id": member.patient_id,
        "name": member.full_name,
        "role": member.role,
        "expires_at": get_session_expiry(SESSION_EXPIRE_MINUTES),
    }

    return token


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
):
    """Validate the session and recheck current account authorization."""
    token = request.cookies.get("carecircle_session")

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Please log in first.",
        )

    session = SESSIONS.get(token)

    if not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session.",
        )

    if datetime.now(timezone.utc) >= session["expires_at"]:
        SESSIONS.pop(token, None)

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Your session has expired. Please log in again.",
        )

    # Verify the patient account is still active.
    if session["role"] == "patient":
        patient = db.query(Patient).filter(
            Patient.id == session["patient_id"],
            Patient.is_active.is_(True),
        ).first()

        if not patient:
            SESSIONS.pop(token, None)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="This patient account is no longer active.",
            )

    # Verify family/caretaker access against the latest database record.
    elif session["role"] in ("family", "caretaker"):
        member = db.query(CareMember).filter(
            CareMember.id == session["user_id"],
            CareMember.patient_id == session["patient_id"],
            CareMember.is_active.is_(True),
            CareMember.invitation_status == "accepted",
        ).first()

        if not member:
            SESSIONS.pop(token, None)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Your access has been revoked or is no longer active.",
            )

    else:
        SESSIONS.pop(token, None)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid account role.",
        )

    return session


def require_patient(
    current_user: dict = Depends(get_current_user),
):
    """Allow only the patient account to perform patient-only actions."""
    if current_user["role"] != "patient":
        raise HTTPException(
            status_code=403,
            detail="Only the patient can perform this action.",
        )

    return current_user


def logout_user(request: Request):
    """Invalidate the current in-memory session."""
    token = request.cookies.get("carecircle_session")

    if token:
        SESSIONS.pop(token, None)

    return {"message": "Logged out successfully."}
def require_permission(permission: str):
    """Check a family member's latest database permissions."""

    allowed_permissions = {
        "can_view_profile",
        "can_view_medications",
        "can_manage_medications",
        "can_confirm_doses",
        "can_manage_appointments",
    }

    if permission not in allowed_permissions:
        raise ValueError("Unknown permission.")

    def permission_checker(
        current_user: dict = Depends(get_current_user),
        db: Session = Depends(get_db),
    ):
        # The patient owns their profile and has full access.
        if current_user["role"] == "patient":
            return current_user

        member = db.query(CareMember).filter(
            CareMember.id == current_user["user_id"],
            CareMember.patient_id == current_user["patient_id"],
            CareMember.is_active.is_(True),
            CareMember.invitation_status == "accepted",
        ).first()

        if not member:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Your access is no longer active.",
            )

        if not getattr(member, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to perform this action.",
            )

        return current_user

    return permission_checker