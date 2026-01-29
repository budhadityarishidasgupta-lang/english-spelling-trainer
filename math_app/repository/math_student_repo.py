from typing import Dict, List

def get_active_math_students() -> List[Dict[str, str]]:
    """
    Returns ACTIVE Maths students (for admin dropdowns).
    Uses shared 'users' table, scoped to app_source='math'.
    """
    from math_app.db import get_db_connection

    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    user_id AS id,
                    name,
                    email
                FROM users
                WHERE role = 'student'
                  AND app_source = 'math'
                  AND status = 'ACTIVE'
                ORDER BY name
                """
            )
            rows = cur.fetchall()
            return [{"id": r[0], "name": r[1], "email": r[2]} for r in rows]
    finally:
        if conn:
            conn.close()
