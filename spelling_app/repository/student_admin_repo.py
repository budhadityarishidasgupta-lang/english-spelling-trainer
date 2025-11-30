from datetime import date
from passlib.hash import bcrypt

from shared.db import fetch_all, execute


# ---------------------------------------
# Utility: Password hashing
# ---------------------------------------

def _hash_password(password: str) -> str:
    """Use bcrypt (compatible with the existing login system)."""
    return bcrypt.hash(password)


# ---------------------------------------
# User Management
# ---------------------------------------

def create_student_user(name: str, email: str, temp_password: str = "Learn123!") -> int | dict:
    """
    Creates a new student user and assigns them to the 'spelling' category.
    Returns the new user_id or an error dict.
    """
    hashed_password = _hash_password(temp_password)

    # Execute insert
    result = execute(
        """
        INSERT INTO users (name, email, password_hash, role)
        VALUES (:n, :e, :p, 'student')
        RETURNING id
        """,
        {
            "n": name,
            "e": email,
            "p": hashed_password,
        },
    )

    # Handle error dicts
    if isinstance(result, dict) and "error" in result:
        return result

    # Handle SQLAlchemy CursorResult
    if hasattr(result, "fetchone"):
        row = result.fetchone()
        if row and "id" in row._mapping:
            new_user_id = row._mapping["id"]
        else:
            return {"error": "Failed to extract user ID from cursor result."}

    # Handle list return (older execute() behavior)
    elif isinstance(result, list) and result:
        row = result[0]
        if isinstance(row, dict):
            new_user_id = row.get("id")
        elif hasattr(row, "_mapping"):
            new_user_id = row._mapping.get("id")
        else:
            return {"error": "Unknown row format (list case)."}

    else:
        return {"error": "Unexpected execute() return type."}

    # 2) Tag as a spelling student in user_categories
    cat_result = execute(
        """
        INSERT INTO user_categories (user_id, category)
        VALUES (:uid, 'spelling')
        """,
        {"uid": new_user_id},
    )

    if isinstance(cat_result, dict) and "error" in cat_result:
        return cat_result

    return new_user_id


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
