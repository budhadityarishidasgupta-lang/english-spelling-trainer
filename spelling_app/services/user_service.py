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
    Generic user creator using new execute() return types.
    execute() ALWAYS returns:
      - list (for SELECT / RETURNING)
      - dict {rows_affected: ...}
      - dict {error: ...}
    """

    # 1. Check if user already exists
    existing = fetch_all(
        "SELECT user_id FROM users WHERE email = :email",
        {"email": email},
    )
    if existing:
        row = existing[0]
        if hasattr(row, "_mapping"):
            return row._mapping.get("user_id")
        if isinstance(row, dict):
            return row.get("user_id")
        return row[0] if isinstance(row, (list, tuple)) else None

    # 2. Insert new user
    result = fetch_all(
        """
        INSERT INTO users (name, email, password_hash, role)
        VALUES (:n, :e, :p, :r)
        RETURNING user_id;
        """,
        {"n": name, "e": email, "p": password_hash, "r": role},
    )

    # --- RETURNING always returns a list ---
    if isinstance(result, list) and result:
        row = result[0]
        if hasattr(row, "_mapping"):
            return row._mapping.get("user_id")
        if isinstance(row, dict):
            return row.get("user_id")
        try:
            return row[0]
        except Exception:
            return None

    # --- Error dict ---
    if isinstance(result, dict) and "error" in result:
        return None

    return None
