from typing import Dict, List

from math_app.db import get_db_connection


def get_active_math_students() -> List[Dict[str, str]]:
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, name, email
                FROM students
                WHERE is_active = TRUE
                AND id IN (
                    SELECT student_id
                    FROM math_enrollments
                    WHERE is_active = TRUE
                )
                ORDER BY name
                """
            )
            rows = cur.fetchall()
            return [
                {"id": r[0], "name": r[1], "email": r[2]}
                for r in rows
            ]
    finally:
        if conn:
            conn.close()
