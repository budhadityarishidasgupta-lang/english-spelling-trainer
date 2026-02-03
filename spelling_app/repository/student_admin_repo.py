from datetime import date
from passlib.hash import bcrypt

from shared.db import execute, fetch_all
from spelling_app.services.user_service import hash_password


# ---------------------------------------
# Utility: User ID extraction
# ---------------------------------------

def _extract_user_id(row):
    """
    Safely extract user_id from different row types.
    """
    if row is None:
        return None

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
# Utility: Password hashing
# ---------------------------------------

def hash_password(password: str) -> str:
    """Use bcrypt (compatible with the existing login system)."""
    return bcrypt.hash(password)


# ---------------------------------------
# User Management (SPELLING-ONLY)
# ---------------------------------------

def create_student_user(name: str, email: str):
    """
    Creates a spelling student user using the new execute() return format.
    """

    sql = """
        INSERT INTO users (name, email, password_hash, role)
        VALUES (:n, :e, :p, 'student')
        RETURNING user_id;
    """

    params = {
        "n": name,
        "e": email,
        "p": hash_password("Learn123!")
    }

    result = execute(sql, params)

    # DB error
    if isinstance(result, dict) and "error" in result:
        return {"error": result["error"]}

    # Normal RETURNING → list
    if isinstance(result, list):
        if not result:
            return {"error": "Insert returned empty list"}

        row = result[0]

        if hasattr(row, "_mapping"):
            return row._mapping.get("user_id")

        if isinstance(row, dict):
            return row.get("user_id")

        try:
            return row[0]
        except Exception:
            return {"error": f"Unknown row structure: {row}"}

    return {"error": f"Unexpected execute() return type: {type(result)} -> {result}"}


# ---------------------------------------
# Spelling Students Overview
# ---------------------------------------

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
    result = fetch_all(
        """
        INSERT INTO classes (name, start_date)
        VALUES (:n, :sd)
        RETURNING class_id;
        """,
        {"n": name, "sd": start_date},
    )
    # fetch_all returns a list; guard against unexpected return types
    row = result[0] if isinstance(result, list) and result else None

    if not row:
        return {"error": "Failed to create classroom"}

    if hasattr(row, "_mapping"):
        return row._mapping["class_id"]
    if isinstance(row, dict):
        return row["class_id"]
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


def add_student_to_class(*, class_id: int, student_id: int):
    """Assigns a student to a class."""
    return assign_student_to_class(class_id, student_id)


def unassign_student_from_class(class_id: int, student_id: int):
    """Unassigns a student from a class."""
    return execute(
        """
        DELETE FROM class_students
        WHERE class_id = :cid AND student_id = :sid
        """,
        {"cid": class_id, "sid": student_id},
    )
