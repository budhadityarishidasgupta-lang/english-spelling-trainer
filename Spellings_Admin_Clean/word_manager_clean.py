from typing import List, Dict, Optional

from shared.db import fetch_all
from spelling_app.repository.words_repo import (
    insert_word,
    update_word,
    delete_word,
    get_word_by_text,
)


def get_words_for_course(course_id: int) -> List[Dict]:
    """
    Return all words for a given spelling course.
    Assumes spelling_words has a course_id column.
    """
    sql = """
        SELECT
            word_id,
            word,
            difficulty,
            pattern_code
        FROM spelling_words
        WHERE course_id = :course_id
        ORDER BY word_id ASC;
    """
    rows = fetch_all(sql, {"course_id": course_id})

    if isinstance(rows, dict):
        return []

    return [dict(getattr(r, "_mapping", r)) for r in rows]


def get_lessons_for_course(course_id: int) -> List[Dict]:
    """
    Lightweight helper to list lessons for a course.
    """
    sql = """
        SELECT
            lesson_id,
            lesson_name,
            sort_order
        FROM spelling_lessons
        WHERE course_id = :course_id
        ORDER BY sort_order, lesson_id;
    """
    rows = fetch_all(sql, {"course_id": course_id})

    if isinstance(rows, dict):
        return []

    return [dict(getattr(r, "_mapping", r)) for r in rows]


def get_lesson_words(course_id: int, lesson_id: int) -> List[Dict]:
    """
    Return all words mapped to a specific lesson.
    Relies on spelling_lesson_words(lesson_id, word_id, pattern_code).
    """
    sql = """
        SELECT
            w.word_id,
            w.word,
            w.difficulty,
            lw.pattern_code
        FROM spelling_lesson_words lw
        JOIN spelling_words w ON w.word_id = lw.word_id
        WHERE lw.lesson_id = :lesson_id
        ORDER BY w.word_id;
    """
    rows = fetch_all(sql, {"lesson_id": lesson_id})

    if isinstance(rows, dict):
        return []

    return [dict(getattr(r, "_mapping", r)) for r in rows]


def find_word_by_text(word: str) -> Optional[Dict]:
    """
    Convenience wrapper around get_word_by_text (returns first result or None).
    """
    rows = get_word_by_text(word)
    if isinstance(rows, dict):
        return None
    if not rows:
        return None
    return rows[0]


def create_word_admin(
    word: str,
    course_id: int,
    difficulty=None,
    pattern_code: Optional[str] = None,
) -> Dict:
    """
    Create a word for admin panel.
    """
    word_id = insert_word(
        word=word,
        difficulty=difficulty,
        pattern_code=pattern_code,
        course_id=course_id,
    )
    return {"word_id": word_id}


def update_word_admin(word_id: int, new_word: str):
    """
    Update a word in admin panel.
    """
    return update_word(word_id=word_id, new_word=new_word)


def delete_word_admin(word_id: int):
    """
    Delete a word from admin panel.
    """
    return delete_word(word_id=word_id)
