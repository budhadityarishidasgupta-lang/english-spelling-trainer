import secrets
from datetime import datetime
from typing import Optional

from sqlalchemy import text
from passlib.hash import bcrypt

from shared.db import execute, fetch_all, get_engine

engine = get_engine()

# Default Spelling courses (LOCKED)
DEFAULT_SPELLING_COURSE_IDS = (1, 9)


def generate_registration_token() -> str:
    """Generate a non-guessable registration token for PayPal matching."""
    return secrets.token_urlsafe(32)


def _ensure_payment_status_column():
    """Add payment_status column if missing to keep verification idempotent."""
    execute(
        """
        ALTER TABLE spelling_pending_registrations
        ADD COLUMN IF NOT EXISTS payment_status TEXT DEFAULT 'unverified'
        """
    )


def _ensure_registration_token_column():
    """Ensure registration_token exists and is populated/unique."""
    execute(
        """
        ALTER TABLE spelling_pending_registrations
        ADD COLUMN IF NOT EXISTS registration_token TEXT
        """
    )

    # Backfill any missing tokens for existing rows
    execute(
        """
        UPDATE spelling_pending_registrations
        SET registration_token = md5(random()::text || clock_timestamp()::text)
        WHERE registration_token IS NULL
        """
    )

    execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS spelling_pending_registrations_registration_token_uidx
        ON spelling_pending_registrations(registration_token)
        """
    )

    execute(
        """
        ALTER TABLE spelling_pending_registrations
        ALTER COLUMN registration_token SET NOT NULL
        """
    )


def create_pending_registration(student_name: str, email: str, token: str):
    """Insert a pending registration with a deterministic token."""
    _ensure_registration_token_column()
    _ensure_payment_status_column()

    return execute(
        """
        INSERT INTO spelling_pending_registrations (student_name, email, registration_token)
        VALUES (:student_name, :email, :token)
        ON CONFLICT (registration_token) DO NOTHING
        RETURNING id
        """,
        {"student_name": student_name, "email": email, "token": token},
    )


def _fetch_registration_status_by_token(token: str) -> Optional[str]:
    rows = fetch_all(
        """
        SELECT payment_status
        FROM spelling_pending_registrations
        WHERE registration_token = :token
        LIMIT 1
        """,
        {"token": token},
    )

    if not rows:
        return None

    row = rows[0]
    if hasattr(row, "_mapping"):
        return row._mapping.get("payment_status")
    if isinstance(row, dict):
        return row.get("payment_status")
    try:
        return row[0]
    except Exception:
        return None


def mark_registration_verified_by_token(token: str) -> bool:
    """Mark the matching registration as payment verified using its token."""
    if not token:
        return False

    _ensure_registration_token_column()
    _ensure_payment_status_column()

    current_status = _fetch_registration_status_by_token(token)
    if current_status is None:
        return False

    if str(current_status).lower() == "verified":
        return True

    execute(
        """
        UPDATE spelling_pending_registrations
        SET payment_status = 'verified'
        WHERE registration_token = :token
        """,
        {"token": token},
    )

    return True


# -------------------------------------------------------------------
# CANONICAL USER IDENTITY HELPER (LOCKED BEHAVIOUR)
# -------------------------------------------------------------------

def get_or_create_user_by_email(
    *,
    name: str,
    email: str,
    default_password: str = "Learn123!",
):
    """
    Canonical helper to enforce ONE user per email across all apps.

    Rules (LOCKED):
    - Reuse existing users row if email exists
    - Create a new user ONLY if email does not exist
    - Never reset or override password for existing users
    """
    existing_rows = execute(
        """
        SELECT user_id
        FROM users
        WHERE LOWER(email) = LOWER(:email)
        LIMIT 1
        """,
        {"email": email},
    )

    if isinstance(existing_rows, dict) and "error" in existing_rows:
        return existing_rows

    if existing_rows:
        row = existing_rows[0]
        if hasattr(row, "_mapping"):
            return row._mapping.get("user_id")
        if isinstance(row, dict):
            return row.get("user_id")
        try:
            return row[0]
        except Exception:
            return None

    hashed_password = bcrypt.hash(default_password)

    created_rows = execute(
        """
        INSERT INTO users (
            name,
            email,
            password_hash,
            role,
            status,
            is_active,
            app_source
        )
        VALUES (
            :name,
            :email,
            :password_hash,
            'student',
            'ACTIVE',
            TRUE,
            'spelling'
        )
        RETURNING user_id
        """,
        {
            "name": name,
            "email": email,
            "password_hash": hashed_password,
        },
    )

    if isinstance(created_rows, dict) and "error" in created_rows:
        return created_rows

    if not created_rows:
        return None

    row = created_rows[0]
    if hasattr(row, "_mapping"):
        return row._mapping.get("user_id")
    if isinstance(row, dict):
        return row.get("user_id")
    try:
        return row[0]
    except Exception:
        return None


def auto_enroll_user_into_default_spelling_courses(user_id: int):
    """
    Auto-enroll a user into default Spelling courses.

    Rules (LOCKED):
    - Only touches spelling_enrollments
    - Uses unique constraint (user_id, course_id) for idempotency
    - Safe to call multiple times
    """
    with engine.begin() as conn:
        for course_id in DEFAULT_SPELLING_COURSE_IDS:
            conn.execute(
                text(
                    """
                    INSERT INTO spelling_enrollments (user_id, course_id)
                    VALUES (:user_id, :course_id)
                    ON CONFLICT (user_id, course_id) DO NOTHING
                    """
                ),
                {
                    "user_id": user_id,
                    "course_id": course_id,
                },
            )


def manually_add_spelling_student(
    *,
    name: str,
    email: str,
):
    """
    Admin-only manual add of a Spelling student.

    Behaviour (LOCKED):
    - Reuse existing user by email OR create new user
    - Default password only for new users
    - Auto-enroll into default spelling courses (1 & 9)
    """
    user_id = get_or_create_user_by_email(
        name=name,
        email=email,
    )

    auto_enroll_user_into_default_spelling_courses(user_id)

    return user_id


def get_pending_registrations():
    return fetch_all(
        """
        SELECT id, student_name, email, created_at
        FROM pending_registrations
        WHERE status = 'PENDING'
        ORDER BY created_at ASC
        """
    )


def approve_registration(reg_id: int):
    execute(
        """
        UPDATE pending_registrations
        SET status = 'APPROVED', reviewed_at = :now
        WHERE id = :id
        """,
        {"id": reg_id, "now": datetime.utcnow()},
    )


def reject_registration(reg_id: int):
    execute(
        """
        UPDATE pending_registrations
        SET status = 'REJECTED', reviewed_at = :now
        WHERE id = :id
        """,
        {"id": reg_id, "now": datetime.utcnow()},
    )
