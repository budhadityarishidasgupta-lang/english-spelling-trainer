from shared.db import execute, fetch_all


def _extract_user_id(row):
    """
    Robust helper to pull user_id from different row types:
    - SQLAlchemy Row with _mapping
    - dict
    - plain tuple/list
    """
    if row is None:
        return None

    # SQLAlchemy Row
    if hasattr(row, "_mapping"):
        m = row._mapping
        return m.get("user_id") or m.get("id")

    # Dict
    if isinstance(row, dict):
        return row.get("user_id") or row.get("id")

    # Sequence with user_id in first position
    try:
        return row["user_id"]
    except Exception:
        try:
            return row[0]
        except Exception:
            return None


def create_user(name: str, email: str, password_hash: str, role: str):
    """
    Generic user creator (for non-spelling flows):

    - If a user with this email already exists, returns its user_id.
    - Otherwise inserts a new user and returns the new user_id.

    NO spelling-specific logic here:
    - does NOT delete pending registrations
    - does NOT touch user_categories

    Spelling approvals must use create_student_user in student_admin_repo.
    """

    # Check if user already exists
    existing = fetch_all(
        "SELECT user_id FROM users WHERE email = :email",
        {"email": email},
    )

    if existing:
        return _extract_user_id(existing[0])

    # Create new user
    rows = fetch_all(
        """
        INSERT INTO users (name, email, password_hash, role)
        VALUES (:n, :e, :p, :r)
        RETURNING user_id;
        """,
        {"n": name, "e": email, "p": password_hash, "r": role},
    )

    if not rows:
        raise RuntimeError("Failed to create user – no user_id returned.")

    return _extract_user_id(rows[0])
