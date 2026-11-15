
import secrets
from datetime import datetime, timedelta, timezone

from passlib.context import CryptContext

# bcrypt securely hashes passcodes instead of storing plain text.
pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
)


def hash_passcode(passcode: str) -> str:
    """Create a secure hash of a user's passcode."""
    if not passcode or len(passcode) < 8:
        raise ValueError("Passcode must contain at least 8 characters.")

    if len(passcode.encode("utf-8")) > 72:
        raise ValueError("Passcode is too long.")

    return pwd_context.hash(passcode)


def verify_passcode(passcode: str, hashed_passcode: str) -> bool:
    """Check a passcode against its stored hash."""
    if not passcode or not hashed_passcode:
        return False

    try:
        return pwd_context.verify(passcode, hashed_passcode)
    except (ValueError, TypeError):
        return False


def generate_session_token() -> str:
    """Generate a cryptographically secure random session token."""
    return secrets.token_urlsafe(32)


def get_session_expiry(minutes: int = 60) -> datetime:
    """Return the UTC expiry time for a session."""
    if minutes <= 0:
        raise ValueError("Session duration must be positive.")

    return datetime.now(timezone.utc) + timedelta(minutes=minutes)
