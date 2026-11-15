
import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy.orm import Session

from backend.app.models import CareMember, Patient
from backend.app.security import hash_passcode, verify_passcode


def _hash_token(token: str) -> str:
    """Store only a SHA-256 hash of an invitation token."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def invite_member(
    patient_id: int,
    full_name: str,
    email: str,
    role: str,
    db: Session,
    permissions: dict | None = None,
):
    """Create a pending invitation controlled by the patient."""

    patient = db.query(Patient).filter(
        Patient.id == patient_id,
        Patient.is_active.is_(True),
    ).first()

    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found.")

    if role not in {"family", "caretaker"}:
        raise HTTPException(
            status_code=400,
            detail="Role must be family or caretaker.",
        )

    email = email.strip().lower()

    existing = db.query(CareMember).filter(
        CareMember.patient_id == patient_id,
        CareMember.email == email,
        CareMember.is_active.is_(True),
    ).first()

    if existing:
        raise HTTPException(
            status_code=409,
            detail="This person already has active access.",
        )

    permissions = permissions or {}

    # Access defaults to minimum necessary permissions.
    member = CareMember(
        patient_id=patient_id,
        full_name=full_name.strip(),
        email=email,
        role=role,
        can_view_profile=bool(permissions.get("can_view_profile", True)),
        can_view_medications=bool(
            permissions.get("can_view_medications", True)
        ),
        can_manage_medications=bool(
            permissions.get("can_manage_medications", False)
        ),
        can_confirm_doses=bool(
            permissions.get("can_confirm_doses", False)
        ),
        can_manage_appointments=bool(
            permissions.get("can_manage_appointments", False)
        ),
        invitation_status="pending",
        is_active=False,
    )

    token = secrets.token_urlsafe(32)

    member.invitation_token_hash = _hash_token(token)
    member.invitation_expires_at = (
        datetime.now(timezone.utc) + timedelta(hours=48)
    )

    db.add(member)
    db.commit()
    db.refresh(member)

    # Return this token only to the patient-facing invitation flow.
    return {
        "member_id": member.id,
        "email": member.email,
        "role": member.role,
        "invitation_token": token,
        "expires_at": member.invitation_expires_at.isoformat(),
        "message": "Invitation created. Share the token securely.",
    }


def accept_invitation(
    invitation_token: str,
    email: str,
    passcode: str,
    db: Session,
):
    """Accept an invitation after verifying its token and invited email."""

    if not invitation_token or not email or not passcode:
        raise HTTPException(
            status_code=400,
            detail="Invitation code, email and passcode are required.",
        )

    member = db.query(CareMember).filter(
        CareMember.invitation_token_hash == _hash_token(invitation_token),
        CareMember.email == email.strip().lower(),
        CareMember.invitation_status == "pending",
        CareMember.is_active.is_(False),
    ).first()

    if not member:
        raise HTTPException(
            status_code=400,
            detail="Invalid invitation code or email address.",
        )

    now = datetime.now(timezone.utc)
    expiry = member.invitation_expires_at

    if expiry is None:
        raise HTTPException(
            status_code=400,
            detail="Invitation has no expiry.",
        )

    if expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=timezone.utc)

    if now >= expiry:
        member.invitation_status = "expired"
        member.invitation_token_hash = None
        db.commit()

        raise HTTPException(
            status_code=400,
            detail="Invitation has expired. Ask the patient for a new one.",
        )

    member.passcode_hash = hash_passcode(passcode)
    member.invitation_status = "accepted"
    member.is_active = True
    member.invitation_token_hash = None
    member.invitation_expires_at = None

    db.commit()

    return {
        "member_id": member.id,
        "patient_id": member.patient_id,
        "name": member.full_name,
        "role": member.role,
        "message": "Invitation accepted successfully.",
    }


def list_members(patient_id: int, db: Session):
    """List members belonging to a patient."""
    return db.query(CareMember).filter(
        CareMember.patient_id == patient_id
    ).order_by(CareMember.created_at.desc()).all()


def update_member_permissions(
    patient_id: int,
    member_id: int,
    permissions: dict,
    db: Session,
):
    """Allow the patient to change an individual member's permissions."""

    member = db.query(CareMember).filter(
        CareMember.id == member_id,
        CareMember.patient_id == patient_id,
        CareMember.is_active.is_(True),
    ).first()

    if not member:
        raise HTTPException(status_code=404, detail="Active member not found.")

    allowed = {
        "can_view_profile",
        "can_view_medications",
        "can_manage_medications",
        "can_confirm_doses",
        "can_manage_appointments",
    }

    for key, value in permissions.items():
        if key not in allowed:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported permission: {key}",
            )

        if not isinstance(value, bool):
            raise HTTPException(
                status_code=400,
                detail=f"{key} must be true or false.",
            )

        setattr(member, key, value)

    db.commit()
    db.refresh(member)

    return member


def revoke_member_access(
    patient_id: int,
    member_id: int,
    db: Session,
):
    """Immediately revoke a member's access."""

    member = db.query(CareMember).filter(
        CareMember.id == member_id,
        CareMember.patient_id == patient_id,
    ).first()

    if not member:
        raise HTTPException(status_code=404, detail="Member not found.")

    member.is_active = False
    member.invitation_status = "revoked"
    member.invitation_token_hash = None
    member.invitation_expires_at = None

    db.commit()

    return {"message": "Member access revoked successfully."}


def authenticate_member(
    email: str,
    passcode: str,
    db: Session,
):
    """Authenticate an accepted member using email and passcode."""

    members = db.query(CareMember).filter(
        CareMember.email == email.strip().lower(),
        CareMember.is_active.is_(True),
        CareMember.invitation_status == "accepted",
    ).all()

    matching_members = [
        member for member in members
        if member.passcode_hash
        and verify_passcode(passcode, member.passcode_hash)
    ]

    if not matching_members:
        raise HTTPException(
            status_code=401,
            detail="Invalid email or passcode.",
        )

    if len(matching_members) > 1:
        raise HTTPException(
            status_code=409,
            detail="Multiple care connections match these credentials. Contact the patient.",
        )

    return matching_members[0]