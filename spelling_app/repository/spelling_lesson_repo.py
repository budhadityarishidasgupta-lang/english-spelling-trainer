# spelling_app/repository/spelling_lesson_repo.py

from shared.db import fetch_all, execute


def _to_dict(row):
    """Convert SQLAlchemy row or mapping to dict safely."""
    if row is None:
        return None
    if isinstance(row, dict):
        return row
    if hasattr(row, "_mapping"):
        return dict(row._mapping)
    try:
        return dict(row)
    except Exception:
        return None


def _to_list(rows):
    """Normalize fetch_all results into a list."""
    if rows is None:
        return []
    if isinstance(rows, list):
        return rows
    if hasattr(rows, "all"):  # CursorResult
        try:
            return rows.all()
        except Exception:
            return []
    return []


def get_lesson_by_name(course_id: int, lesson_name: str):
    """
    Return a single lesson row (dict) or None.
    """
    rows = fetch_all(
        """
        SELECT
            lesson_id,
            course_id,
            lesson_name,
            sort_order
        FROM spelling_lessons
        WHERE course_id = :course_id
          AND lesson_name = :lesson_name
        """,
        {"course_id": course_id, "lesson_name": lesson_name},
    )

    if isinstance(rows, dict):
        return rows

    rows = _to_list(rows)
    if not rows:
        return None

    return _to_dict(rows[0])


def create_spelling_lesson(course_id: int, lesson_name: str, sort_order: int):
    """
    Create or update a spelling lesson safely using RETURNING.
    Ensures a lesson always exists for a name under a course.
    """

    rows = fetch_all(
        """
        INSERT INTO spelling_lessons (course_id, lesson_name, sort_order)
        VALUES (:course_id, :lesson_name, :sort_order)
        ON CONFLICT (course_id, lesson_name)
        DO UPDATE SET sort_order = EXCLUDED.sort_order
        RETURNING
            lesson_id,
            course_id,
            lesson_name,
            sort_order;
        """,
        {"course_id": course_id, "lesson_name": lesson_name, "sort_order": sort_order},
    )

    if isinstance(rows, dict):
        return rows

    rows = _to_list(rows)
    if not rows:
        return {"error": "Error: lesson creation returned no rows."}

    return _to_dict(rows[0])


def update_spelling_lesson_sort_order(lesson_id: int, sort_order: int):
    """
    Update sort order of a spelling lesson.
    """
    return execute(
        """
        UPDATE spelling_lessons
        SET sort_order = :sort_order
        WHERE lesson_id = :lesson_id;
        """,
        {"lesson_id": lesson_id, "sort_order": sort_order},
    )
