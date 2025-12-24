from typing import Any, Dict, List, Optional

from sqlalchemy import text

from shared.db import execute, fetch_all


def _rows_to_dicts(rows: Any) -> List[Dict[str, Any]]:
    """
    Helper to normalise DB rows into plain dicts.
    Returns [] if rows is None or a dict (error payload).
    """
    if not rows or isinstance(rows, dict):
        return []

    dict_rows: List[Dict[str, Any]] = []
    for row in rows:
        if hasattr(row, "_mapping"):
            dict_rows.append(dict(row._mapping))
        elif isinstance(row, dict):
            dict_rows.append(row)
    return dict_rows


def upsert_weak_word(user_id: int, word_id: int, lesson_id: int) -> None:
    sql = text(
        """
        INSERT INTO weak_words (user_id, word_id, lesson_id, wrong_count, last_wrong_at)
        VALUES (:user_id, :word_id, :lesson_id, 1, NOW())
        ON CONFLICT (user_id, word_id)
        DO UPDATE SET
            wrong_count = weak_words.wrong_count + 1,
            last_wrong_at = NOW(),
            lesson_id = EXCLUDED.lesson_id
        """
    )
    execute(
        sql,
        {
            "user_id": user_id,
            "word_id": word_id,
            "lesson_id": lesson_id,
        },
    )


# ---------------------------------------------------------
# PENDING REGISTRATIONS
# ---------------------------------------------------------
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
    Approve a pending spelling student:
    - read from pending_spelling_registrations
    - insert into users with app_source='spelling'
    - delete from pending table
    """
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

    execute(
        """
        INSERT INTO users (name, email, password_hash, role, status, class_name, app_source)
        VALUES (:name, :email, :phash, 'student', 'ACTIVE', NULL, 'spelling')
        """,
        {
            "name": pending.get("student_name"),
            "email": pending.get("email"),
            "phash": default_password_hash,
        },
    )

    execute(
        """
        DELETE FROM pending_spelling_registrations
        WHERE pending_id = :pid
        """,
        {"pid": pending_id},
    )

    return True


# ---------------------------------------------------------
# REGISTERED SPELLING STUDENTS
# ---------------------------------------------------------
def list_registered_spelling_students() -> List[Dict[str, Any]]:
    """
    Return ONLY spelling students (role=student AND app_source='spelling'),
    with a comma-separated list of registered courses.
    """
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


def update_student_profile(
    user_id: int, class_name: Optional[str], status: str
) -> None:
    """
    Update class_name + status for a spelling student.
    """
    execute(
        """
        UPDATE users
        SET class_name = :cname, status = :status
        WHERE user_id = :uid AND role = 'student' AND app_source = 'spelling'
        """,
        {"cname": class_name, "status": status, "uid": user_id},
    )


# ---------------------------------------------------------
# COURSE ENROLMENTS
# ---------------------------------------------------------
def get_student_courses(user_id: int) -> List[Dict[str, Any]]:
    rows = fetch_all(
        """
        SELECT c.course_id, c.course_name, c.description
        FROM spelling_enrollments e
        JOIN spelling_courses c ON c.course_id = e.course_id
        WHERE e.user_id = :uid
          AND c.is_active = true
        ORDER BY c.course_name
        """,
        {"uid": user_id},
    )
    return _rows_to_dicts(rows)


def assign_courses_to_student(user_id: int, course_ids: List[int]) -> None:
    """
    Assign multiple courses to a student (idempotent).
    """
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
    """
    Remove multiple courses from a student.
    """
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
