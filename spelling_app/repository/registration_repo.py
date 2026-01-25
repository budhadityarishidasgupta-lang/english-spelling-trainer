import secrets
from datetime import datetime
from typing import Optional

from sqlalchemy import text

from shared.db import execute, fetch_all


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
