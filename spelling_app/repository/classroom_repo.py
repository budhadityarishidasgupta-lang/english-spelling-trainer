from typing import Any, Dict, List, Optional

from shared.db import execute, fetch_all


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


def create_classroom(class_name: str) -> Optional[Dict[str, Any]]:
    rows = fetch_all(
        """
        INSERT INTO spelling_classrooms (class_name)
        VALUES (:name)
        RETURNING class_id, class_name, created_at
        """,
        {"name": class_name},
    )

    created = _rows_to_dicts(rows)
    if not created:
        return None

    return created[0]


def list_classrooms() -> List[Dict[str, Any]]:
    rows = fetch_all(
        """
        SELECT class_id, class_name, created_at
        FROM spelling_classrooms
        ORDER BY created_at DESC
        """,
    )
    return _rows_to_dicts(rows)


def assign_students_to_class(student_ids, class_name: str) -> None:
    for sid in student_ids:
        execute(
            """
            UPDATE users
            SET class_name = :cname
            WHERE user_id = :uid
              AND app_source = 'spelling'
            """,
            {"uid": sid, "cname": class_name},
        )


def get_students_in_class(class_name: str) -> List[Dict[str, Any]]:
    rows = fetch_all(
        """
        SELECT user_id, name, email, status
        FROM users
        WHERE class_name = :cname
          AND app_source = 'spelling'
        ORDER BY name
        """,
        {"cname": class_name},
    )
    return _rows_to_dicts(rows)
