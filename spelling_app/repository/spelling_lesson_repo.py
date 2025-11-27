from shared.db import fetch_all, execute


def get_lesson_by_name(course_id: int, lesson_name: str):
    """
    Fetch a single spelling lesson row by its course_id and lesson_name.
    """
    rows = fetch_all(
        """
        SELECT lesson_id, course_id, lesson_name, sort_order
        FROM spelling_lessons
        WHERE course_id = :course_id AND lesson_name = :lesson_name
        LIMIT 1;
        """,
        {"course_id": course_id, "lesson_name": lesson_name},
    )

    if isinstance(rows, dict):
        return rows  # DB error

    if not rows:
        return None  # lesson not found

    return dict(rows[0]._mapping)


def create_spelling_lesson(course_id: int, lesson_name: str, sort_order: int):
    """
    Insert a new spelling lesson and return the inserted row (dict).
    """
    # FIX: Use fetch_all for RETURNING clause
    rows = fetch_all(
        """
        INSERT INTO spelling_lessons (course_id, lesson_name, sort_order)
        VALUES (:course_id, :lesson_name, :sort_order)
        ON CONFLICT (course_id, lesson_name) DO UPDATE SET sort_order = EXCLUDED.sort_order
        RETURNING lesson_id, course_id, lesson_name, sort_order;
        """,
        {"course_id": course_id, "lesson_name": lesson_name, "sort_order": sort_order},
    )

    if isinstance(rows, dict):
        return rows  # DB error

    return dict(rows[0]._mapping)


def update_spelling_lesson_sort_order(lesson_id: int, sort_order: int):
    """
    Update the sort_order for an existing spelling lesson.
    """
    return execute(
        """
        UPDATE spelling_lessons
        SET sort_order = :sort_order
        WHERE lesson_id = :lesson_id;
        """,
        {"lesson_id": lesson_id, "sort_order": sort_order},
    )
