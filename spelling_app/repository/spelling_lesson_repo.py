from shared.db import fetch_all, execute

def _to_dict(row):
    """Converts a SQLAlchemy Row or RowMapping to a standard dict."""
    try:
        return dict(row)
    except Exception:
        return dict(row._mapping)

def get_lesson_by_name(course_id: int, lesson_name: str):
    rows = fetch_all(
        """
        SELECT lesson_id, course_id, lesson_name, sort_order
        FROM spelling_lessons
        WHERE course_id = :course_id AND lesson_name = :lesson_name
        LIMIT 1;
        """,
        {"course_id": course_id, "lesson_name": lesson_name},
    )

    # fetch_all error handling
    if isinstance(rows, dict):
        return rows

    if not rows:
        return None

    # rows is a CursorResult → convert properly
    first = rows[0]
    return _to_dict(first)


def create_spelling_lesson(course_id: int, lesson_name: str, sort_order: int):
    rows = fetch_all(
        """
        INSERT INTO spelling_lessons (course_id, lesson_name, sort_order)
        VALUES (:course_id, :lesson_name, :sort_order)
        ON CONFLICT (course_id, lesson_name)
        DO UPDATE SET sort_order = EXCLUDED.sort_order
        RETURNING lesson_id, course_id, lesson_name, sort_order;
        """,
        {"course_id": course_id, "lesson_name": lesson_name, "sort_order": sort_order},
    )

    if isinstance(rows, dict):
        return rows

    if not rows:
        return {"error": "Database error: failed to insert or update spelling lesson."}

    return _to_dict(rows[0])


def update_spelling_lesson_sort_order(lesson_id: int, sort_order: int):
    return execute(
        """
        UPDATE spelling_lessons
        SET sort_order = :sort_order
        WHERE lesson_id = :lesson_id;
        """,
        {"lesson_id": lesson_id, "sort_order": sort_order},
    )
