from shared.db import execute, fetch_all

# ==================================================
# Spelling Class Persistence (LOCKED)
# ==================================================
# Classes are organisational only.
# Enrollment controls access.
# Do NOT infer permissions from classes.
# ==================================================


def get_students_in_class(class_id: int):
    """
    Returns all students assigned to a spelling class.
    """
    return fetch_all(
        """
        SELECT
            u.user_id,
            u.name,
            u.email
        FROM spelling_class_students scs
        JOIN users u
            ON u.user_id = scs.user_id
        WHERE scs.class_id = :class_id
        ORDER BY u.name
        """,
        {"class_id": class_id},
    )


def add_student_to_class(class_id: int, user_id: int):
    """
    Assign a student to a class (idempotent).
    """
    execute(
        """
        INSERT INTO spelling_class_students (class_id, user_id)
        VALUES (:class_id, :user_id)
        ON CONFLICT (class_id, user_id) DO NOTHING
        """,
        {"class_id": class_id, "user_id": user_id},
    )


def remove_student_from_class(class_id: int, user_id: int):
    """
    Remove a student from a class.
    """
    execute(
        """
        DELETE FROM spelling_class_students
        WHERE class_id = :class_id
          AND user_id = :user_id
        """,
        {"class_id": class_id, "user_id": user_id},
    )
