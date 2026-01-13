from typing import Dict, List, Optional

from math_app.db import get_db_connection


def get_lessons_for_course(course_id: int) -> List[Dict]:
    """
    Returns lessons for admin UI.
    lesson_name = canonical identity (read-only)
    display_name = admin-editable label
    """
    sql = """
        SELECT
            id AS lesson_id,
            lesson_name,
            display_name
        FROM math_lessons
        WHERE course_id = %s
        ORDER BY lesson_name
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, (course_id,))
            rows = cur.fetchall()
    finally:
        conn.close()

    return [
        {
            "lesson_id": row[0],
            "lesson_name": row[1],
            "display_name": row[2],
        }
        for row in rows
    ]


def update_lesson_display_name(
    lesson_id: int,
    display_name: Optional[str],
) -> None:
    """
    Updates display_name only.
    Must never change lesson_name.
    """
    sql = """
        UPDATE math_lessons
        SET display_name = %s
        WHERE id = %s
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, (display_name, lesson_id))
        conn.commit()
    finally:
        conn.close()
