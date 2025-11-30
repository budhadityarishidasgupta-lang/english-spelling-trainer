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
    # 1. Check if user already exists
    existing = fetch_all(
        "SELECT user_id FROM users WHERE email = :email",
        {"email": email}
    )

    if existing:
        row = existing[0]
        user_id = row.get("user_id") if isinstance(row, dict) else row._mapping["user_id"]

        # Remove pending registration if exists
        execute("DELETE FROM pending_registrations WHERE email = :email", {"email": email})

        # Ensure student is categorized under spelling
        execute(
            """
            INSERT INTO user_categories (user_id, category)
            VALUES (:uid, 'spelling')
            ON CONFLICT DO NOTHING;
            """,
            {"uid": user_id}
        )

        return user_id

    # 2. Create new user
    result = execute(
        """
        INSERT INTO users (name, email, password_hash, role)
        VALUES (:n, :e, :p, :r)
        RETURNING user_id;
        """,
        {"n": name, "e": email, "p": password_hash, "r": role}
    )

    # Normalize return format
    if isinstance(result, dict):
        user_id = result.get("user_id")
    else:
        row = result.fetchone()
        if hasattr(row, "_mapping"):
            user_id = row._mapping.get("user_id")
        else:
            user_id = row.get("user_id")

    # 3. Add spelling category for newly created user
    execute(
        """
        INSERT INTO user_categories (user_id, category)
        VALUES (:uid, 'spelling')
        ON CONFLICT DO NOTHING;
        """,
        {"uid": user_id}
    )

    return user_id
