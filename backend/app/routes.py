
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from backend.app.auth import (
    get_current_user,
    login_member,
    login_patient,
    logout_user,
    register_patient,
    require_patient,
    require_permission,
)
from backend.app.users import (
    accept_invitation,
    invite_member,
    list_members,
    update_member_permissions,
    revoke_member_access,
)
from backend.app.config import APP_ENV
from backend.app.database import get_db



router = APIRouter(prefix="/api/auth", tags=["Authentication"])


class PatientRegisterRequest(BaseModel):
    full_name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    passcode: str = Field(min_length=8, max_length=72)


class PatientLoginRequest(BaseModel):
    email: EmailStr
    passcode: str = Field(min_length=8, max_length=72)


class MemberLoginRequest(BaseModel):
    email: EmailStr
    passcode: str = Field(min_length=8, max_length=72)

@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(
    payload: PatientRegisterRequest,
    db: Session = Depends(get_db),
):
    patient = register_patient(
        full_name=payload.full_name,
        email=str(payload.email),
        passcode=payload.passcode,
        db=db,
    )

    return {
        "message": "Patient account created successfully.",
        "patient": {
            "id": patient.id,
            "full_name": patient.full_name,
            "email": patient.email,
        },
    }

@router.post("/login")
def patient_login(
    payload: PatientLoginRequest,
    response: Response,
    db: Session = Depends(get_db),
):
    token = login_patient(
        email=str(payload.email),
        passcode=payload.passcode,
        db=db,
    )

    response.set_cookie(
        key="carecircle_session",
        value=token,
        httponly=True,
        secure=APP_ENV == "production",
        samesite="lax",
        max_age=3600,
    )

    return {"message": "Login successful."}

@router.post("/member-login")
@router.post("/member-login")
def member_login(
    payload: MemberLoginRequest,
    response: Response,
    db: Session = Depends(get_db),
):
    token = login_member(
        email=str(payload.email),
        passcode=payload.passcode,
        db=db,
    )

    response.set_cookie(
        key="carecircle_session",
        value=token,
        httponly=True,
        secure=APP_ENV == "production",
        samesite="lax",
        max_age=3600,
    )

    return {"message": "Member login successful."}

@router.post("/logout")
def logout(response: Response, request: Request):
    result = logout_user(request)
    response.delete_cookie(
        key="carecircle_session",
        httponly=True,
        secure=APP_ENV == "production",
        samesite="lax",
    )
    return result

@router.get("/me")
def get_me(current_user=Depends(get_current_user)):
    return {
        "authenticated": True,
        "user": {
            "id": current_user["user_id"],
            "patient_id": current_user["patient_id"],
            "name": current_user["name"],
            "role": current_user["role"],
        },
    }

class InviteMemberRequest(BaseModel):
    full_name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    role: str = Field(pattern="^(family|caretaker)$")
    permissions: dict[str, bool] | None = None

@router.post("/members/invite", status_code=status.HTTP_201_CREATED)
def create_member_invitation(
    payload: InviteMemberRequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_patient),
):
    invitation = invite_member(
        patient_id=current_user["patient_id"],
        full_name=payload.full_name,
        email=str(payload.email),
        role=payload.role,
        db=db,
        permissions=payload.permissions,
    )

    return {
        "message": invitation["message"],
        "member_id": invitation["member_id"],
        "email": invitation["email"],
        "role": invitation["role"],
        "invitation_token": invitation["invitation_token"],
        "expires_at": invitation["expires_at"],
    }


class AcceptInvitationRequest(BaseModel):
    invitation_token: str = Field(min_length=20, max_length=200)
    email: EmailStr
    passcode: str = Field(min_length=8, max_length=72)

@router.post("/members/accept-invitation")
def accept_member_invitation(
    payload: AcceptInvitationRequest,
    db: Session = Depends(get_db),
):
    result = accept_invitation(
        invitation_token=payload.invitation_token,
        email=str(payload.email),
        passcode=payload.passcode,
        db=db,
    )

    return result
    
@router.get("/members")
def get_members(
    db: Session = Depends(get_db),
    current_user=Depends(require_patient),
):
    members = list_members(
        patient_id=current_user["patient_id"],
        db=db,
    )

    return {
        "members": [
            {
                "id": member.id,
                "full_name": member.full_name,
                "email": member.email,
                "role": member.role,
                "invitation_status": member.invitation_status,
                "is_active": member.is_active,
                "can_view_profile": member.can_view_profile,
                "can_view_medications": member.can_view_medications,
                "can_manage_medications": member.can_manage_medications,
                "can_confirm_doses": member.can_confirm_doses,
                "can_manage_appointments": member.can_manage_appointments,
            }
            for member in members
        ]
    }

class UpdatePermissionsRequest(BaseModel):
    permissions: dict[str, bool]

@router.put("/members/{member_id}/permissions")
def change_member_permissions(
    member_id: int,
    payload: UpdatePermissionsRequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_patient),
):
    member = update_member_permissions(
        patient_id=current_user["patient_id"],
        member_id=member_id,
        permissions=payload.permissions,
        db=db,
    )

    return {
        "message": "Member permissions updated successfully.",
        "member_id": member.id,
        "permissions": {
            "can_view_profile": member.can_view_profile,
            "can_view_medications": member.can_view_medications,
            "can_manage_medications": member.can_manage_medications,
            "can_confirm_doses": member.can_confirm_doses,
            "can_manage_appointments": member.can_manage_appointments,
        },
    }

@router.delete("/members/{member_id}")
def remove_member_access(
    member_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_patient),
):
    revoke_member_access(
        patient_id=current_user["patient_id"],
        member_id=member_id,
        db=db,
    )

    return {
        "message": "Member access revoked successfully.",
        "member_id": member_id,
    }
