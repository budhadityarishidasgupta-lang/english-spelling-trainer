from typing import Any, Dict, List, Optional
from shared.db import fetch_all, execute


def _rows_to_dicts(rows: Any) -> List[Dict[str, Any]]:
    if not rows or isinstance(rows, dict):
        return []
    out = []
    for r in rows:
        if hasattr(r, "_mapping"):
            out.append(dict(r._mapping))
        elif isinstance(r, dict):
            out.append(r)
    return out


# ---------------------------------------------------------
# CREATE CLASSROOM
# ---------------------------------------------------------
def create_classroom(class_name: str) -> Optional[Dict[str, Any]]:
    try:
        rows = fetch_all(
            """
            INSERT INTO spelling_classrooms (classroom_name)
            VALUES (:cname)
            RETURNING classroom_id, classroom_name, created_at;
            """,
            {"cname": class_name},
        )
    except Exception:
        return {"error": "Classroom already exists."}

    rows = _rows_to_dicts(rows)
    return rows[0] if rows else None


# ---------------------------------------------------------
# LIST CLASSROOMS
# ---------------------------------------------------------
def list_classrooms() -> List[Dict[str, Any]]:
    rows = fetch_all(
        """
        SELECT classroom_id, classroom_name, created_at, is_active
        FROM spelling_classrooms
        ORDER BY created_at DESC;
        """
    )
    return _rows_to_dicts(rows)


def list_active_classrooms() -> List[Dict[str, Any]]:
    rows = fetch_all(
        """
        SELECT classroom_id, classroom_name, created_at
        FROM spelling_classrooms
        WHERE is_active = TRUE
        ORDER BY classroom_name;
        """
    )
    return _rows_to_dicts(rows)


# ---------------------------------------------------------
# ASSIGN STUDENTS TO CLASSROOM
# ---------------------------------------------------------
def assign_students_to_class(student_ids: List[int], class_name: str) -> None:
    if not student_ids:
        return

    for student_id in student_ids:
        execute(
            """
            UPDATE users
            SET class_name = :cname
            WHERE user_id = :uid
              AND app_source = 'spelling';
            """,
            {"cname": class_name, "uid": student_id},
        )


def assign_student_to_classroom(
    student_id: int,
    classroom_id: int,
) -> Optional[Dict[str, Any]]:
    try:
        execute(
            """
            INSERT INTO spelling_classroom_students (classroom_id, student_id)
            VALUES (:cid, :sid)
            ON CONFLICT DO NOTHING;
            """,
            {"cid": classroom_id, "sid": student_id},
        )
    except Exception:
        return {"error": "Failed to assign student to classroom."}
    return None


# ---------------------------------------------------------
# GET STUDENTS IN CLASSROOM
# ---------------------------------------------------------
def get_students_in_class(class_name: str) -> List[Dict[str, Any]]:
    rows = fetch_all(
        """
        SELECT user_id, name, email, status
        FROM users
        WHERE class_name = :cname
          AND app_source = 'spelling'
        ORDER BY name;
        """,
        {"cname": class_name},
    )
    return _rows_to_dicts(rows)


def get_students_in_classroom(classroom_id: int) -> List[Dict[str, Any]]:
    rows = fetch_all(
        """
        SELECT u.user_id, u.name, u.email
        FROM spelling_classroom_students scs
        JOIN users u ON u.user_id = scs.student_id
        WHERE scs.classroom_id = :cid
        ORDER BY u.name;
        """,
        {"cid": classroom_id},
    )
    return _rows_to_dicts(rows)


def get_student_classroom(student_id: int) -> Optional[Dict[str, Any]]:
    rows = fetch_all(
        """
        SELECT sc.classroom_id, sc.classroom_name
        FROM spelling_classroom_students scs
        JOIN spelling_classrooms sc ON sc.classroom_id = scs.classroom_id
        WHERE scs.student_id = :sid
        ORDER BY sc.created_at DESC
        LIMIT 1;
        """,
        {"sid": student_id},
    )
    rows = _rows_to_dicts(rows)
    return rows[0] if rows else None


def archive_classroom(classroom_id: int) -> Optional[Dict[str, Any]]:
    try:
        execute(
            """
            UPDATE spelling_classrooms
            SET is_active = FALSE
            WHERE classroom_id = :cid;
            """,
            {"cid": classroom_id},
        )
    except Exception:
        return {"error": "Failed to archive classroom."}
    return None
