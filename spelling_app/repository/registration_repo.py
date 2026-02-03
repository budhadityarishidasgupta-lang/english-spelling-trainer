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
    """
    Return all pending spelling registrations from the spelling-specific table.
    """
    return fetch_all(
        """
        SELECT id, student_name, parent_email, created_at
        FROM pending_registrations_spelling
        ORDER BY created_at DESC;
        """,
        {},
    )


def delete_pending_registration(reg_id: int):
    """
    Delete a single spelling registration by id.
    """
    return execute(
        "DELETE FROM pending_registrations_spelling WHERE id = :rid",
        {"rid": reg_id},
    )


def manually_add_spelling_student(name, email):
    user_id = get_or_create_user_by_email(
        name=name,
        email=email,
        default_password="Learn123!",
    )

    # 🔒 REQUIRED: make student visible to Spelling app + Admin UI
    execute(
        """
        INSERT INTO spelling_enrollments (user_id, course_id)
        VALUES
            (:uid, 1),  -- Word Mastery
            (:uid, 9)   -- Pattern Words
        ON CONFLICT DO NOTHING;
        """,
        {"uid": user_id},
    )

    return user_id
