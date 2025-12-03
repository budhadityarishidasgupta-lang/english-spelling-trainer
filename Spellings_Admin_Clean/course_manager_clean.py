from typing import List, Dict, Optional

from spelling_app.repository.course_repo import (
    get_all_spelling_courses,
    get_spelling_course_by_id,
    create_spelling_course,
    update_spelling_course,
)


def list_courses() -> List[Dict]:
    """
    Return all spelling courses as a list of dicts.
    """
    rows = get_all_spelling_courses()
    if isinstance(rows, dict):
        # DB error, bubble up
        return []
    return rows


def get_course(course_id: int) -> Optional[Dict]:
    """
    Return a single spelling course by ID, or None.
    """
    row = get_spelling_course_by_id(course_id)
    if isinstance(row, dict) and row.get("error"):
        return None
    return row


def create_course_admin(title: str, description: Optional[str] = None):
    """
    Create a new spelling course and return its course_id.
    """
    return create_spelling_course(title=title, description=description)


def update_course_admin(course_id: int, title: Optional[str], description: Optional[str]):
    """
    Update title/description of a spelling course.
    """
    return update_spelling_course(course_id=course_id, title=title, description=description)
