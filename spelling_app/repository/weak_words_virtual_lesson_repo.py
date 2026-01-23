from shared.db import fetch_all, safe_rows


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
        SELECT DISTINCT
            w.word_id,
            w.course_id,
            w.word,
            COALESCE(o.hint_text, w.hint) AS hint,
            w.example_sentence
        FROM spelling_attempts a
        JOIN spelling_words w ON w.word_id = a.word_id
        LEFT JOIN spelling_hint_overrides o ON o.word_id = w.word_id
        WHERE a.user_id = :uid
          AND a.correct = FALSE
        ORDER BY a.created_at DESC
        LIMIT :limit
        """,
        {"uid": user_id, "limit": limit},
    )

    if not rows:
        return {}

    rows = safe_rows(rows)

    # 🔑 Pick course deterministically (first weak word)
    first = rows[0]
    course_id = first["course_id"]

    words = [
        {
            "word_id": r["word_id"],
            "word": r.get("word"),
            "hint": r.get("hint"),
            "example_sentence": r.get("example_sentence"),
        }
        for r in rows
    ]
    word_ids = [w["word_id"] for w in words]

    # 🔒 VIRTUAL lesson (negative ID, never stored)
    VIRTUAL_WEAK_LESSON_ID = -100

    return {
        "course_id": course_id,
        "lesson_id": VIRTUAL_WEAK_LESSON_ID,
        "word_ids": word_ids,
        "word_count": len(words),
        "words": words,
    }
