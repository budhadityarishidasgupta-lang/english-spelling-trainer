from datetime import date
from passlib.hash import bcrypt

from shared.db import fetch_all, execute


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

def _hash_password(password: str) -> str:
    """Use bcrypt (compatible with the existing login system)."""
    return bcrypt.hash(password)


# ---------------------------------------
# User Management (SPELLING-ONLY)
# ---------------------------------------

def create_student_user(student_name: str, parent_email: str, temp_password: str = "Learn123!") -> int | dict:
    """
    Approve a spelling student registration.

    1. If a user with this email already exists:
         - Reuse its user_id
         - Ensure 'spelling' category exists
         - Delete pending_registrations_spelling row(s)
         - Return user_id
    2. If not:
         - Create a new user (role='student') in an idempotent way
         - Assign 'spelling' category
         - Delete pending_registrations_spelling row(s)
         - Return user_id
    """

    try:
        # 1. Check if user already exists
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
                ON CONFLICT DO NOTHING
                RETURNING user_id;
                """,
                {"uid": user_id},
            )

            # Delete pending row(s) for this email
            execute(
                "DELETE FROM pending_registrations_spelling WHERE parent_email = :email",
                {"email": parent_email},
            )

            return user_id

        # 2. User does not exist → attempt to create (idempotent on email)
        hashed_password = _hash_password(temp_password)

        result = execute(
            """
INSERT INTO users (name, email, password_hash, role)
VALUES (:n, :e, :p, 'student')
ON CONFLICT (email) DO NOTHING
RETURNING user_id;
            """,
            {"n": student_name, "e": parent_email, "p": hashed_password},
        )

        # NEW unified execute() list-based response
        if isinstance(result, list):
            if len(result) == 0:
                return {"error": "No result returned"}
            row = result[0]

            if hasattr(row, "_mapping"):
                result = row._mapping
            elif isinstance(row, dict):
                result = row
            else:
                return {"error": f"Unknown row type: {type(row)}"}

        # Error dict returned from execute()
        if isinstance(result, dict) and "error" in result:
            return result

        if not isinstance(result, (dict,)):
            return {"error": f"Unexpected execute() return type: {type(result)}"}

        user_id = _extract_user_id(result)

        if not user_id:
            # Conflict or no RETURNING row → fetch existing user_id explicitly
            existing_after = fetch_all(
                "SELECT user_id FROM users WHERE email = :email",
                {"email": parent_email},
            )
            if not existing_after:
                return {"error": "Could not insert or locate user by email."}
            user_id = _extract_user_id(existing_after[0])

        if not user_id:
            return {"error": "Could not resolve user_id for created user."}

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

        # Delete pending row(s)
        execute(
            "DELETE FROM pending_registrations_spelling WHERE parent_email = :email",
            {"email": parent_email},
        )

        return user_id

    except Exception as e:
        return {"error": str(e)}


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


def unassign_student_from_class(class_id: int, student_id: int):
    """Unassigns a student from a class."""
    return execute(
        """
        DELETE FROM class_students
        WHERE class_id = :cid AND student_id = :sid
        """,
        {"cid": class_id, "sid": student_id},
    )
