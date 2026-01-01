from sqlalchemy import text


def ensure_pending_registration_payment_status_column(db):
    """
    Safe additive migration (idempotent).
    Adds payment_status if missing so Admin UI can display + gate approvals.
    """
    # NOTE: this is spelling-app scoped table only.
    db.execute(text(
        """
        ALTER TABLE spelling_pending_registrations
        ADD COLUMN IF NOT EXISTS payment_status TEXT DEFAULT 'unverified'
        """
    ))
    db.commit()


def ensure_pending_registration_token_column(db):
    """Add registration_token for deterministic payment matching."""
    db.execute(text(
        """
        ALTER TABLE spelling_pending_registrations
        ADD COLUMN IF NOT EXISTS registration_token TEXT
        """
    ))
    db.execute(text(
        """
        UPDATE spelling_pending_registrations
        SET registration_token = md5(random()::text || clock_timestamp()::text)
        WHERE registration_token IS NULL
        """
    ))
    db.execute(text(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS spelling_pending_registrations_registration_token_uidx
        ON spelling_pending_registrations(registration_token)
        """
    ))
    db.execute(text(
        """
        ALTER TABLE spelling_pending_registrations
        ALTER COLUMN registration_token SET NOT NULL
        """
    ))
    db.commit()


def list_spelling_pending_registrations(db, verified_only: bool = False):
    """
    Returns rows: id, student_name, email, requested_at, payment_status
    """
    base = """
        SELECT id, student_name, email, requested_at,
               COALESCE(payment_status, 'unverified') AS payment_status,
               RIGHT(registration_token, 4) AS token_suffix
        FROM spelling_pending_registrations
    """
    if verified_only:
        base += " WHERE COALESCE(payment_status, 'unverified') = 'verified' "

    base += " ORDER BY requested_at DESC "

    result = db.execute(text(base))
    return [dict(r._mapping) for r in result.fetchall()]


def mark_registration_approved(db, reg_id: int):
    """
    Keeps approval manual (Option B). We do NOT auto-enroll here.
    This function only marks registration as approved in a safe way.
    If the table does not have a status column, we do nothing beyond a no-op.
    """
    # Try to set a status column if present, otherwise leave as-is.
    # (We keep this defensive because schema may vary across environments.)
    try:
        db.execute(text(
            """
            UPDATE spelling_pending_registrations
            SET status = 'approved'
            WHERE id = :id
            """
        ), {"id": reg_id})
        db.commit()
    except Exception:
        db.rollback()
        # If no status column exists, we still allow downstream flows to proceed
        # without crashing admin. Approval can remain in users table flow if used.
        return
