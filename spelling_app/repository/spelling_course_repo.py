"""Repository helpers for spelling courses."""

from shared.db import execute


def archive_course(course_id: int):
    """Soft-archive a course by marking it inactive."""
    return execute(
        """
        UPDATE spelling_courses
        SET is_active = false
        WHERE course_id = :course_id
        """,
        {"course_id": course_id},
    )

