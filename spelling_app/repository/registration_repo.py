from shared.db import fetch_all, execute


def create_pending_registration(name: str, email: str):
    return execute(
        """
        INSERT INTO pending_registrations_spelling (student_name, parent_email)
        VALUES (:n, :e)
        """,
        {"n": name, "e": email},
    )


def get_pending_registrations():
    rows = fetch_all(
        """
        SELECT id, student_name, parent_email, created_at
        FROM pending_registrations_spelling
        ORDER BY created_at DESC
        """
    )
    rows_list = list(rows) if rows else []

    # Filter out registrations where the user already exists
    cleaned = []
    for row in rows_list:
        email = None
        if hasattr(row, "_mapping"):
            email = row._mapping.get("parent_email")
        elif isinstance(row, dict):
            email = row.get("parent_email")
        else:
            try:
                email = row["parent_email"]
            except Exception:
                try:
                    email = row[1]
                except Exception:
                    email = None

        if email is None:
            cleaned.append(row)
            continue

        existing = fetch_all(
            "SELECT user_id FROM users WHERE email = :email",
            {"email": email},
        )
        existing_rows = list(existing) if existing else []
        if not existing_rows:
            cleaned.append(row)

    return cleaned


def delete_pending_registration(req_id: int):
    return execute(
        """
        DELETE FROM pending_registrations_spelling
        WHERE id = :i
        """,
        {"i": req_id},
    )
