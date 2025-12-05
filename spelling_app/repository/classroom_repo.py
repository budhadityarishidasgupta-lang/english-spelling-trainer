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
    rows = fetch_all(
        """
        INSERT INTO spelling_classrooms (class_name)
        VALUES (:cname)
        RETURNING class_id, class_name, created_at;
        """,
        {"cname": class_name},
    )

    rows = _rows_to_dicts(rows)
    return rows[0] if rows else None


# ---------------------------------------------------------
# LIST CLASSROOMS
# ---------------------------------------------------------
def list_classrooms() -> List[Dict[str, Any]]:
    rows = fetch_all(
        """
        SELECT class_id, class_name, created_at
        FROM spelling_classrooms
        ORDER BY created_at DESC;
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
