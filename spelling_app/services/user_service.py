from shared.db import execute, fetch_all


def _extract_user_id(row):
    if hasattr(row, "_mapping"):
        return row._mapping.get("user_id") or row._mapping.get("id")
    if isinstance(row, dict):
        return row.get("user_id") or row.get("id")
    try:
        return row["user_id"]
    except Exception:
        try:
            return row[0]
        except Exception:
            return None


def create_user(name, email, password_hash, role):
    # Step 1 — check if user already exists
    existing = fetch_all(
        "SELECT user_id FROM users WHERE email = :email",
        {"email": email}
    )
    existing_rows = list(existing) if existing else []
    if existing_rows:
        user_id = _extract_user_id(existing_rows[0])

        # Remove the pending entry if it exists
        execute("DELETE FROM pending_registrations WHERE email = :email", {"email": email})

        return user_id

    result = execute(
        """
        INSERT INTO users (name, email, password_hash, role)
        VALUES (:n, :e, :p, :r)
        RETURNING id;
        """,
        {"n": name, "e": email, "p": password_hash, "r": role}
    )

    # NEW: safe, type-agnostic extraction
    if isinstance(result, dict):
        return result.get("id")

    # Handle list responses from execute()
    if isinstance(result, list) and result:
        return _extract_user_id(result[0])

    # Fallback for CursorResult or Row
    try:
        row = result.fetchone()
        if row:
            return _extract_user_id(row)
    except Exception:
        pass

    return None
