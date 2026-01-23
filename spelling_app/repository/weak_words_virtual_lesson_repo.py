from spelling_app.repository.weak_words_repo import get_weak_word_ids_for_user
from shared.db import fetch_all


def prepare_system_weak_words_lesson_for_user(
    user_id: int, limit: int = 50
) -> dict:
    """
    Prepares a virtual 'Weak Words' lesson.
    CONTRACT (DO NOT BREAK):
    {
        word_ids: list[int],
        course_id: int,
        lesson_id: int,
        word_count: int
    }
    """
    word_ids = get_weak_word_ids_for_user(user_id, limit=limit)

    if not word_ids:
        return {
            "word_ids": [],
            "course_id": None,
            "lesson_id": None,
            "word_count": 0,
        }

    rows = fetch_all(
        """
        SELECT DISTINCT course_id
        FROM spelling_words
        WHERE word_id = ANY(:word_ids)
        LIMIT 1
        """,
        {"word_ids": word_ids},
    )

    course_id = None
    if rows and not isinstance(rows, dict):
        m = getattr(rows[0], "_mapping", rows[0])
        course_id = m.get("course_id")

    return {
        "word_ids": word_ids,
        "course_id": course_id,
        "lesson_id": -1,
        "word_count": len(word_ids),
    }
