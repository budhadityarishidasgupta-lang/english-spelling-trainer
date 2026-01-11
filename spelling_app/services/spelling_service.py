from typing import List, Dict, Any

from spelling_app.repository import student_repo


def load_items(lesson_id: int, course_id: int) -> List[Dict[str, Any]]:
    """
    Fetch lesson words for legacy practice screens.

    Returns list of dicts containing at least: word_id/id, word/base_word, pattern.
    """
    rows = student_repo.get_words_for_lesson(lesson_id, course_id)
    items: List[Dict[str, Any]] = []
    for row in rows:
        items.append(
            {
                "id": row.get("word_id"),
                "word": row.get("word"),
                "base_word": row.get("word"),
                "pattern_code": row.get("pattern_code"),
                "display_form": row.get("word"),
                "sp_item_id": row.get("word_id"),
            }
        )
    return items


def load_lessons_for_course(course_id: int):
    return student_repo.get_lessons_for_course(course_id)


def get_lesson_progress(user_id: int, lesson_id: int) -> int:
    """
    Basic lesson progress placeholder.
    Returns mastery percentage if available; otherwise defaults to 0.
    """
    return 0


def record_attempt(
    user_id: int,
    course_id: int,
    lesson_id: int,
    item_id: int,
    typed_answer: str,
    correct: bool,
    response_ms: int,
):
    """
    Lightweight bridge to the spelling attempts table.
    """
    student_repo.record_attempt(
        user_id=user_id,
        word_id=item_id,
        correct=correct,
        time_taken=response_ms,
    )


def get_daily_five_words(user_id: int) -> List[int]:
    """Return the deterministic Daily-5 word ids for a user."""
    return student_repo.get_daily_five_word_ids(user_id)


def get_weak_words(user_id: int) -> List[Dict[str, Any]]:
    """Fetch weak words for a user sourced from the authoritative weak_words table."""
    return student_repo.get_weak_words(user_id)
