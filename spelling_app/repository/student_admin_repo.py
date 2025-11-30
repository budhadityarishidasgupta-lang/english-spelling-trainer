from shared.db import fetch_all, execute
from spelling_app.services.user_service import _hash_password, _extract_user_id


def create_student_user(student_name: str, parent_email: str, temp_password: str = "Learn123!") -> int | dict:
    """
    Approves a spelling student registration:
    - Reuses existing user if email already exists
    - Otherwise creates new student
    - Adds spelling category
    - Removes pending registration
    """

    try:
        # 1. CHECK IF USER ALREADY EXISTS (correct column name!)
        existing = fetch_all(
            "SELECT user_id FROM users WHERE email = :email",
            {"email": parent_email},
        )

        if existing:
            user_id = _extract_user_id(existing[0])

            # Ensure spelling category exists
            fetch_all(
                """
                INSERT INTO user_categories (user_id, category)
                VALUES (:uid, 'spelling')
                ON CONFLICT DO NOTHING;
                """,
                {"uid": user_id},
            )

            # Remove pending
            execute(
                "DELETE FROM pending_registrations_spelling WHERE parent_email = :email",
                {"email": parent_email},
            )

            return user_id

        # 2. USER DOES NOT EXIST → CREATE NEW USER
        hashed_password = _hash_password(temp_password)

        result = fetch_all(
            """
            INSERT INTO users (name, email, password_hash, role)
            VALUES (:n, :e, :p, 'student')
            RETURNING user_id;
            """,
            {"n": student_name, "e": parent_email, "p": hashed_password},
        )

        if not result:
            return {"error": "Failed to insert user"}

        user_id = _extract_user_id(result[0])

        # 3. ASSIGN SPELLING CATEGORY
        fetch_all(
            """
            INSERT INTO user_categories (user_id, category)
            VALUES (:uid, 'spelling')
            ON CONFLICT DO NOTHING;
            """,
            {"uid": user_id},
        )

        # 4. DELETE FROM SPELLING PENDING TABLE
        execute(
            "DELETE FROM pending_registrations_spelling WHERE parent_email = :email",
            {"email": parent_email},
        )

        return user_id

    except Exception as e:
        return {"error": str(e)}
