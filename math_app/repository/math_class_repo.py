from typing import List, Optional, Tuple

from math_app.db import get_db_connection


def _column_exists(cur, table_name: str, column_name: str) -> bool:
    cur.execute(
        """
        SELECT 1
        FROM information_schema.columns
        WHERE table_name = %s AND column_name = %s
        """,
        (table_name, column_name),
    )
    return cur.fetchone() is not None


def get_class_defaults(class_name: str) -> Tuple[Optional[int], List[int]]:
    """
    Returns default course_id and test_ids for a class.
    Safe: returns (None, []) if not configured.
    """
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT class_id
                FROM math_classes
                WHERE class_name = %s
                """,
                (class_name,),
            )
            row = cur.fetchone()
            if not row:
                return None, []

            class_id = int(row[0])
            course_id = None
            auto_assign_course = True
            auto_assign_tests = True

            cur.execute(
                """
                SELECT default_course_id, auto_assign_course, auto_assign_tests
                FROM math_class_defaults
                WHERE class_id = %s
                """,
                (class_id,),
            )
            defaults = cur.fetchone()
            if defaults:
                course_id = defaults[0]
                auto_assign_course = bool(defaults[1])
                auto_assign_tests = bool(defaults[2])

            if course_id is None and _column_exists(cur, "math_classes", "default_course_id"):
                cur.execute(
                    """
                    SELECT default_course_id
                    FROM math_classes
                    WHERE class_id = %s
                    """,
                    (class_id,),
                )
                row = cur.fetchone()
                if row:
                    course_id = row[0]

            if not auto_assign_course:
                course_id = None

            test_ids = []
            if auto_assign_tests and _column_exists(cur, "math_classes", "default_test_ids"):
                cur.execute(
                    """
                    SELECT default_test_ids
                    FROM math_classes
                    WHERE class_id = %s
                    """,
                    (class_id,),
                )
                row = cur.fetchone()
                if row and row[0]:
                    test_ids = row[0]

            return course_id, test_ids or []
    finally:
        if conn:
            conn.close()
