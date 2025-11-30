from shared.db import execute


def create_user(name, email, password_hash, role):
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
        row = result[0]
        if hasattr(row, "_mapping"):
            return row._mapping.get("id")
        if isinstance(row, dict):
            return row.get("id")
        try:
            return row["id"]
        except Exception:
            try:
                return row[0]
            except Exception:
                return None

    # Fallback for CursorResult or Row
    try:
        row = result.fetchone()
        if row:
            if hasattr(row, "_mapping"):
                return row._mapping.get("id")
            return row.get("id")
    except Exception:
        pass

    return None
