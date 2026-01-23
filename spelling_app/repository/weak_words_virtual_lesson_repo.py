from shared.db import fetch_all, safe_rows
from spelling_app.repository.weak_words_repo import load_weak_words_by_ids


def prepare_system_weak_words_lesson_for_user(user_id: int, limit: int = 50) -> dict:
    """
    Creates a virtual Weak Words lesson for a user.
    CONTRACT (DO NOT BREAK):
    - course_id
    - lesson_id
    - word_ids
    - word_count
    - words
    """

    rows = fetch_all(
        """
        SELECT DISTINCT a.word_id
        FROM spelling_attempts a
        WHERE a.user_id = :user_id
          AND a.correct = FALSE
        ORDER BY a.created_at DESC
        LIMIT :limit
        """,
        {
            "user_id": user_id,
            "limit": limit,
        },
    )

    if not rows:
        return {}

    rows = safe_rows(rows)
    word_ids = [row["word_id"] for row in rows if row.get("word_id") is not None]

    if not word_ids:
        return {}

    words_by_id = {word["word_id"]: word for word in load_weak_words_by_ids(word_ids)}
    words = [words_by_id[word_id] for word_id in word_ids if word_id in words_by_id]

    course_rows = fetch_all(
        """
        SELECT course_id
        FROM spelling_words
        WHERE word_id = :word_id
        """,
        {"word_id": word_ids[0]},
    )
    course_rows = safe_rows(course_rows)
    course_id = course_rows[0]["course_id"] if course_rows else None

    # 🔒 VIRTUAL lesson (negative ID, never stored)
    VIRTUAL_WEAK_LESSON_ID = -100

    return {
        "course_id": course_id,
        "lesson_id": VIRTUAL_WEAK_LESSON_ID,
        "word_ids": word_ids,
        "word_count": len(words),
        "words": words,
    }
