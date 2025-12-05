from shared.db import fetch_all, execute

def create_classroom(class_name: str):
    rows = fetch_all(
        """
        INSERT INTO spelling_classrooms (class_name)
        VALUES (:name)
        RETURNING class_id, class_name, created_at;
        """,
        {"name": class_name},
    )
    if not rows or isinstance(rows, dict):
        return None
    row = rows[0]._mapping
    return dict(row)


def list_classrooms():
    rows = fetch_all(
        """
        SELECT class_id, class_name, created_at
        FROM spelling_classrooms
        ORDER BY created_at DESC;
        """
    )
    if not rows or isinstance(rows, dict):
        return []
    return [dict(r._mapping) for r in rows]


def get_students_in_class(class_name: str):
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
    if not rows or isinstance(rows, dict):
        return []
    return [dict(r._mapping) for r in rows]


def assign_students_to_class(student_ids, class_name: str):
    for sid in student_ids:
        execute(
            """
            UPDATE users
            SET class_name = :cname
            WHERE user_id = :uid
              AND app_source = 'spelling';
            """,
            {"uid": sid, "cname": class_name},
        )
