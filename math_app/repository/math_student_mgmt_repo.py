from typing import Any, Dict, List, Optional

from math_app.db import get_db_connection


def _fetchall_dict(cur) -> List[Dict[str, Any]]:
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


# -------------------------
# Pending registrations
# -------------------------

def list_pending_registrations() -> List[Dict[str, Any]]:
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, name, email, status, created_at
                FROM math_pending_registrations
                WHERE status = 'PENDING'
                ORDER BY created_at DESC
                """
            )
            return _fetchall_dict(cur)
    finally:
        if conn:
            conn.close()


def reject_pending_registration(pending_id: int) -> None:
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE math_pending_registrations
                SET status = 'REJECTED'
                WHERE id = %s AND status = 'PENDING'
                """,
                (pending_id,),
            )
            conn.commit()
    finally:
        if conn:
            conn.close()


def approve_pending_registration(pending_id: int) -> bool:
    """
    Approves a pending Maths registration and grants Maths access.
    Uses the shared users table (already present in your platform) but does NOT duplicate users.
    If user does not exist yet, approval fails (registration flow must create the user row first).
    """
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, name, email
                FROM math_pending_registrations
                WHERE id = %s AND status = 'PENDING'
                """,
                (pending_id,),
            )
            row = cur.fetchone()
            if not row:
                return False

            _, _, email = row

            cur.execute("SELECT user_id FROM users WHERE email = %s", (email,))
            urow = cur.fetchone()
            if not urow:
                return False

            user_id = int(urow[0])

            cur.execute(
                """
                INSERT INTO math_student_access (user_id, status)
                VALUES (%s, 'ACTIVE')
                ON CONFLICT (user_id) DO UPDATE SET status = 'ACTIVE'
                """,
                (user_id,),
            )

            cur.execute(
                """
                UPDATE math_pending_registrations
                SET status = 'APPROVED'
                WHERE id = %s
                """,
                (pending_id,),
            )

            conn.commit()
            return True
    finally:
        if conn:
            conn.close()


# -------------------------
# Active Maths students
# -------------------------

def list_active_math_students() -> List[Dict[str, Any]]:
    """
    Only students who have Maths access entitlement.
    """
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT u.user_id, u.name, u.email, u.class_name, a.status
                FROM users u
                JOIN math_student_access a ON a.user_id = u.user_id
                WHERE u.role = 'student'
                ORDER BY u.name
                """
            )
            return _fetchall_dict(cur)
    finally:
        if conn:
            conn.close()


def set_student_class(user_id: int, class_name: Optional[str]) -> None:
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE users
                SET class_name = %s
                WHERE user_id = %s AND role = 'student'
                """,
                (class_name, user_id),
            )
            conn.commit()
    finally:
        if conn:
            conn.close()


# -------------------------
# Classes & defaults
# -------------------------

def create_class(class_name: str) -> None:
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO math_classes (class_name)
                VALUES (%s)
                ON CONFLICT (class_name) DO NOTHING
                """,
                (class_name.strip(),),
            )
            conn.commit()
    finally:
        if conn:
            conn.close()


def list_classes() -> List[Dict[str, Any]]:
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT c.class_id, c.class_name,
                       COALESCE(COUNT(cs.user_id), 0) AS student_count
                FROM math_classes c
                LEFT JOIN math_class_students cs ON cs.class_id = c.class_id
                GROUP BY c.class_id, c.class_name
                ORDER BY c.class_name
                """
            )
            return _fetchall_dict(cur)
    finally:
        if conn:
            conn.close()


def add_students_to_class(class_id: int, user_ids: List[int]) -> None:
    if not user_ids:
        return
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            for uid in user_ids:
                cur.execute(
                    """
                    INSERT INTO math_class_students (class_id, user_id)
                    VALUES (%s, %s)
                    ON CONFLICT DO NOTHING
                    """,
                    (class_id, int(uid)),
                )
            conn.commit()
    finally:
        if conn:
            conn.close()


def set_class_defaults(
    class_id: int,
    default_course_id: Optional[int],
    auto_assign_course: bool,
    auto_assign_tests: bool,
) -> None:
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO math_class_defaults (class_id, default_course_id, auto_assign_course, auto_assign_tests)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (class_id)
                DO UPDATE SET default_course_id = EXCLUDED.default_course_id,
                              auto_assign_course = EXCLUDED.auto_assign_course,
                              auto_assign_tests = EXCLUDED.auto_assign_tests,
                              updated_at = CURRENT_TIMESTAMP
                """,
                (class_id, default_course_id, auto_assign_course, auto_assign_tests),
            )
            conn.commit()
    finally:
        if conn:
            conn.close()


def get_class_defaults(class_id: int) -> Dict[str, Any]:
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT class_id, default_course_id, auto_assign_course, auto_assign_tests
                FROM math_class_defaults
                WHERE class_id = %s
                """,
                (class_id,),
            )
            row = cur.fetchone()
            if not row:
                return {
                    "class_id": class_id,
                    "default_course_id": None,
                    "auto_assign_course": True,
                    "auto_assign_tests": True,
                }
            return {
                "class_id": row[0],
                "default_course_id": row[1],
                "auto_assign_course": row[2],
                "auto_assign_tests": row[3],
            }
    finally:
        if conn:
            conn.close()


# -------------------------
# Course assignment (student or class)
# -------------------------

def enroll_student_in_course(user_id: int, course_id: int) -> None:
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO math_enrollments (user_id, course_id)
                VALUES (%s, %s)
                ON CONFLICT DO NOTHING
                """,
                (user_id, course_id),
            )
            conn.commit()
    finally:
        if conn:
            conn.close()


def auto_assign_course_for_class(class_id: int) -> None:
    """
    If class has default_course_id and auto_assign_course is true,
    enroll all students in that class to the course.
    """
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT default_course_id, auto_assign_course
                FROM math_class_defaults
                WHERE class_id = %s
                """,
                (class_id,),
            )
            d = cur.fetchone()
            if not d or not d[0] or not bool(d[1]):
                return
            default_course_id = int(d[0])

            cur.execute("SELECT user_id FROM math_class_students WHERE class_id = %s", (class_id,))
            uids = [int(r[0]) for r in cur.fetchall()]

            for uid in uids:
                cur.execute(
                    """
                    INSERT INTO math_enrollments (user_id, course_id)
                    VALUES (%s, %s)
                    ON CONFLICT DO NOTHING
                    """,
                    (uid, default_course_id),
                )
            conn.commit()
    finally:
        if conn:
            conn.close()
