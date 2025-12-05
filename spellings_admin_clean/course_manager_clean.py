from typing import List, Dict, Optional

from spelling_app.repository.course_repo import (
    get_all_spelling_courses,
    get_spelling_course_by_id,
    create_spelling_course,
    update_spelling_course,
)


def list_courses() -> List[Dict]:
    rows = get_all_spelling_courses()
    if isinstance(rows, dict):
        return []
    return rows


def get_course(course_id: int) -> Optional[Dict]:
    row = get_spelling_course_by_id(course_id)
    return row


def create_course_admin(title: str, description: Optional[str] = None):
    return create_spelling_course(course_name=title, description=description)


def update_course_admin(course_id: int, title: Optional[str], description: Optional[str]):
    return update_spelling_course(course_id=course_id, course_name=title, description=description)
