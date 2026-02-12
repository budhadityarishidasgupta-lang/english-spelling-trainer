from typing import Any, Dict, List, Optional

from shared.db import execute, fetch_all, fetch_one


def _rows_to_dicts(rows: Any) -> List[Dict[str, Any]]:
    if not rows or isinstance(rows, dict):
        return []

    dict_rows: List[Dict[str, Any]] = []
    for row in rows:
        if hasattr(row, "_mapping"):
            dict_rows.append(dict(row._mapping))
        elif isinstance(row, dict):
            dict_rows.append(row)
    return dict_rows


def get_pending_spelling_students() -> List[Dict[str, Any]]:
    rows = fetch_all(
        """
        SELECT pending_id, student_name, email, created_at
        FROM pending_spelling_registrations
        ORDER BY created_at DESC
        """
    )
    return _rows_to_dicts(rows)


def approve_spelling_student(pending_id: int, default_password_hash: str) -> bool:
    """
    Approve a pending spelling student safely.

    Handles:
    - Existing user (from general/synonym)
    - New user creation
    - Forces spelling access
    - Auto-assigns default courses
    """

    # 1️⃣ Fetch pending record
    pending_rows = fetch_all(
        """
        SELECT pending_id, student_name, email
        FROM pending_spelling_registrations
        WHERE pending_id = :pid
        """,
        {"pid": pending_id},
    )

    pending_list = _rows_to_dicts(pending_rows)
    if not pending_list:
        return False

    pending = pending_list[0]
    email = pending.get("email")

    # 2️⃣ Check if user already exists
    existing_user = fetch_one(
        """
        SELECT user_id
        FROM users
        WHERE LOWER(email) = LOWER(:email)
        """,
        {"email": email},
    )

    if existing_user:
        user_id = existing_user[0] if isinstance(existing_user, tuple) else existing_user["user_id"]

        # Update user safely
        execute(
            """
            UPDATE users
            SET
                
                role = 'student',
                status = 'ACTIVE',
                is_active = TRUE
                app_source = 'spelling'
            WHERE user_id = :uid
            """,
            {"uid": user_id},
        )

    else:
        # 3️⃣ Create new user
        execute(
            """
            INSERT INTO users (name, email, password_hash, role, status, class_name, app_source, is_active)
            VALUES (:name, :email, :phash, 'student', 'ACTIVE', NULL, 'spelling', TRUE)
            """,
            {
                "name": pending.get("student_name"),
                "email": email,
                "phash": default_password_hash,
            },
        )

        user_row = fetch_one(
            "SELECT user_id FROM users WHERE LOWER(email)=LOWER(:email)",
            {"email": email},
        )
        user_id = user_row[0] if isinstance(user_row, tuple) else user_row["user_id"]

    # 4️⃣ Auto-assign default courses
    DEFAULT_COURSES = [1, 9]  # Word Mastery + Pattern Words

    for course_id in DEFAULT_COURSES:
        execute(
            """
            INSERT INTO spelling_enrollments (user_id, course_id)
            VALUES (:uid, :cid)
            ON CONFLICT DO NOTHING
            """,
            {"uid": user_id, "cid": course_id},
        )

    # 5️⃣ Remove from pending
    execute(
        """
        DELETE FROM pending_spelling_registrations
        WHERE pending_id = :pid
        """,
        {"pid": pending_id},
    )

    return True


def list_registered_spelling_students() -> List[Dict[str, Any]]:
    rows = fetch_all(
        """
        SELECT
            u.user_id,
            u.name,
            u.email,
            u.class_name,
            u.status,
            COALESCE(string_agg(c.course_name, ', ' ORDER BY c.course_name), '') AS registered_courses
        FROM users u
        LEFT JOIN spelling_enrollments e ON e.user_id = u.user_id
        LEFT JOIN spelling_courses c ON c.course_id = e.course_id
        WHERE u.role = 'student' AND u.app_source = 'spelling'
        GROUP BY u.user_id, u.name, u.email, u.class_name, u.status
        ORDER BY u.name
        """
    )

    return _rows_to_dicts(rows)


def update_student_profile(user_id: int, class_name: Optional[str], status: str) -> None:
    execute(
        """
        UPDATE users
        SET class_name = :cname, status = :status
        WHERE user_id = :uid AND role = 'student' AND app_source = 'spelling'
        """,
        {"cname": class_name, "status": status, "uid": user_id},
    )


def get_student_courses(user_id: int) -> List[Dict[str, Any]]:
    rows = fetch_all(
        """
        SELECT c.course_id, c.course_name, c.description
        FROM spelling_enrollments e
        JOIN spelling_courses c ON c.course_id = e.course_id
        WHERE e.user_id = :uid
        ORDER BY c.course_name
        """,
        {"uid": user_id},
    )
    return _rows_to_dicts(rows)


def assign_courses_to_student(user_id: int, course_ids: List[int]) -> None:
    if not course_ids:
        return

    for course_id in course_ids:
        execute(
            """
            INSERT INTO spelling_enrollments (user_id, course_id)
            VALUES (:uid, :cid)
            ON CONFLICT DO NOTHING
            """,
            {"uid": user_id, "cid": course_id},
        )


def remove_courses_from_student(user_id: int, course_ids: List[int]) -> None:
    if not course_ids:
        return

    for course_id in course_ids:
        execute(
            """
            DELETE FROM spelling_enrollments
            WHERE user_id = :uid AND course_id = :cid
            """,
            {"uid": user_id, "cid": course_id},
        )
