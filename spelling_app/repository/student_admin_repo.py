from shared.db import fetch_all, execute
from spelling_app.services.user_service import _extract_user_id, _hash_password


def create_student_user(student_name: str, parent_email: str, temp_password: str = "Learn123!") -> int | dict:
    """
    Approve a spelling student registration.
    Steps:
    1. Check if user already exists (correct column user_id).
    2. If exists:
         - Ensure spelling category exists.
         - Delete pending registration.
         - Return existing user_id.
    3. If not exists:
         - Create new user (using fetch_all for RETURNING).
         - Assign spelling category.
         - Delete pending registration.
         - Return new user_id.
    """

    try:
        # -----------------------
        # 1. Check existing user
        # -----------------------
        existing = fetch_all(
            "SELECT user_id FROM users WHERE email = :email",
            {"email": parent_email},
        )

        if existing:
            # User already exists → REUSE user_id
            user_id = _extract_user_id(existing[0])

            # Assign spelling category
            fetch_all(
                """
                INSERT INTO user_categories (user_id, category)
                VALUES (:uid, 'spelling')
                ON CONFLICT DO NOTHING
                RETURNING user_id;
                """,
                {"uid": user_id},
            )

            # Delete pending entry
            execute(
                "DELETE FROM pending_registrations_spelling WHERE parent_email = :email",
                {"email": parent_email},
            )

            return user_id

        # -----------------------
        # 2. Create NEW user
        # -----------------------
        hashed_password = _hash_password(temp_password)

        user_insert = fetch_all(
            """
            INSERT INTO users (name, email, password_hash, role)
            VALUES (:n, :e, :p, 'student')
            RETURNING user_id;
            """,
            {"n": student_name, "e": parent_email, "p": hashed_password},
        )

        if not user_insert:
            return {"error": "Could not insert user."}

        user_id = _extract_user_id(user_insert[0])

        if not user_id:
            return {"error": "Could not extract user_id."}

        # Assign spelling category
        fetch_all(
            """
            INSERT INTO user_categories (user_id, category)
            VALUES (:uid, 'spelling')
            ON CONFLICT DO NOTHING
            RETURNING user_id;
            """,
            {"uid": user_id},
        )

        # Delete pending
        execute(
            "DELETE FROM pending_registrations_spelling WHERE parent_email = :email",
            {"email": parent_email},
        )

        return user_id

    except Exception as e:
        return {"error": str(e)}
