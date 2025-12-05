# spelling_app/repository/student_repo.py

from typing import List, Dict
from shared.db import fetch_all


def _to_dict(row):
    if row is None:
        return None
    if isinstance(row, dict):
        return row
    if hasattr(row, "_mapping"):
        return dict(row._mapping)
    try:
        return dict(row)
    except Exception:
        return None


def _to_list(rows):
    if rows is None:
        return []
    if isinstance(rows, list):
        return rows
    if hasattr(rows, "all"):
        try:
            return rows.all()
        except Exception:
            return []
    return []


# ---------------------------------------------------------
# FETCH ALL REGISTERED STUDENTS
# ---------------------------------------------------------
def list_registered_students() -> List[Dict]:
    rows = fetch_all(
        """
        SELECT user_id, name, email, status, class_name
        FROM users
        WHERE role = 'student'
        ORDER BY name ASC;
        """
    )

    if isinstance(rows, dict):
        return []

    return [_to_dict(r) for r in _to_list(rows)]


# ---------------------------------------------------------
# GET COURSES A STUDENT IS ENROLLED IN
# ---------------------------------------------------------
def get_student_courses(student_id: int) -> List[Dict]:
    rows = fetch_all(
        """
        SELECT c.course_id, c.course_name
        FROM spelling_enrollments e
        JOIN spelling_courses c ON c.course_id = e.course_id
        WHERE e.user_id = :uid
        ORDER BY c.course_name;
        """,
        {"uid": student_id},
    )

    if isinstance(rows, dict):
        return []

    return [_to_dict(r) for r in _to_list(rows)]


# ---------------------------------------------------------
# ASSIGN COURSE TO STUDENT
# ---------------------------------------------------------
def assign_course_to_student(student_id: int, course_id: int):
    return fetch_all(
        """
        INSERT INTO spelling_enrollments (user_id, course_id)
        VALUES (:uid, :cid)
        ON CONFLICT DO NOTHING;
        """,
        {"uid": student_id, "cid": course_id},
    )


# ---------------------------------------------------------
# REMOVE COURSE FROM STUDENT
# ---------------------------------------------------------
def remove_course_from_student(student_id: int, course_id: int):
    return fetch_all(
        """
        DELETE FROM spelling_enrollments
        WHERE user_id = :uid AND course_id = :cid;
        """,
        {"uid": student_id, "cid": course_id},
    )


# ---------------------------------------------------------
# UPDATE STUDENT STATUS (ACTIVE / ARCHIVED)
# ---------------------------------------------------------
def update_student_status(student_id: int, new_status: str):
    return fetch_all(
        """
        UPDATE users
        SET status = :sts
        WHERE user_id = :uid;
        """,
        {"uid": student_id, "sts": new_status},
    )


# ---------------------------------------------------------
# UPDATE STUDENT CLASS NAME
# ---------------------------------------------------------
def update_student_class_name(student_id: int, class_name: str):
    return fetch_all(
        """
        UPDATE users
        SET class_name = :cls
        WHERE user_id = :uid;
        """,
        {"uid": student_id, "cls": class_name},
    )
