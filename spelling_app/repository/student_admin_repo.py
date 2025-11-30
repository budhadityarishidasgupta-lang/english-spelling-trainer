from datetime import date

from shared.db import fetch_all, execute
from spelling_app.services.user_service import create_user


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


# ---------------------------------------
# User Management
# ---------------------------------------

def create_student_user(student_name: str, parent_email: str):
    """
    Approve a spelling registration for this parent_email:
    - Create or reuse a user row in `users` with role='student'
    - Tag the user in `user_categories` as 'spelling'
    - Return the user_id, or {"error": "..."} on failure
    """

    try:
        # 1. Create or reuse core user account
        #    (empty password_hash; login not used for spelling right now)
        user_id = create_user(
            name=student_name,
            email=parent_email,
            password_hash="",
            role="student",
        )

        if not user_id:
            return {"error": "Could not resolve or create user_id."}

        # 2. Ensure spelling category exists for this user
        execute(
            """
            INSERT INTO user_categories (user_id, category)
            VALUES (:uid, 'spelling')
            ON CONFLICT DO NOTHING;
            """,
            {"uid": user_id},
        )

        return user_id

    except Exception as e:
        return {"error": str(e)}


def get_spelling_students():
    """
    Retrieves all students in the 'spelling' category with their class name and last active date.
    """
    rows = fetch_all(
        """
        SELECT
            u.user_id AS id,
            u.name,
            u.email,
            u.is_active,
            (
                SELECT cl.name
                FROM class_students cs
                JOIN classes cl ON cl.class_id = cs.class_id
                WHERE cs.student_id = u.user_id
                LIMIT 1
            ) AS class_name,
            (
                SELECT MAX(a.created_at)
                FROM attempts a
                WHERE a.user_id = u.user_id
            ) AS last_active
        FROM users u
        JOIN user_categories c ON c.user_id = u.user_id
        WHERE c.category = 'spelling'
        ORDER BY u.name;
        """
    )
    return rows


# ---------------------------------------
# Classroom Management
# ---------------------------------------

def get_all_classes():
    """Retrieves all classrooms."""
    rows = fetch_all(
        """
        SELECT class_id, name, start_date, is_archived, archived_at
        FROM classes
        ORDER BY is_archived ASC, start_date DESC
        """
    )
    return rows


def create_classroom(name: str, start_date: date) -> int | dict:
    """Creates a new classroom."""
    rows = fetch_all(
        """
        INSERT INTO classes (name, start_date)
        VALUES (:n, :sd)
        RETURNING class_id
        """,
        {"n": name, "sd": start_date},
    )
    if not rows:
        return {"error": "Failed to create classroom"}

    row = rows[0]
    if hasattr(row, "_mapping"):
        return row._mapping["class_id"]
    elif isinstance(row, dict):
        return row["class_id"]
    else:
        return row[0]


def archive_classroom(class_id: int):
    """Archives a classroom (does not delete students)."""
    return execute(
        """
        UPDATE classes
        SET is_archived = TRUE, archived_at = NOW()
        WHERE class_id = :id
        """,
        {"id": class_id},
    )


def get_class_roster(class_id: int):
    """Retrieves the roster for a specific class."""
    rows = fetch_all(
        """
        SELECT
            u.user_id AS id,
            u.name,
            u.email
        FROM users u
        JOIN class_students cs ON cs.student_id = u.user_id
        WHERE cs.class_id = :cid
        ORDER BY u.name
        """,
        {"cid": class_id},
    )
    return rows


def assign_student_to_class(class_id: int, student_id: int):
    """Assigns a student to a class."""
    return execute(
        """
        INSERT INTO class_students (class_id, student_id)
        VALUES (:cid, :sid)
        ON CONFLICT (class_id, student_id) DO NOTHING
        """,
        {"cid": class_id, "sid": student_id},
    )


def unassign_student_from_class(class_id: int, student_id: int):
    """Unassigns a student from a class."""
    return execute(
        """
        DELETE FROM class_students
        WHERE class_id = :cid AND student_id = :sid
        """,
        {"cid": class_id, "sid": student_id},
    )
