from shared.db import fetch_all, safe_rows


def get_global_weak_word_ids(user_id: int, limit: int = 50) -> list[int]:
    """
    Returns word_ids the user has answered incorrectly.
    Weak words are ATTEMPT-driven, not lesson-driven.
    """
    rows = fetch_all(
        """
        SELECT DISTINCT a.word_id
        FROM spelling_attempts a
        WHERE a.user_id = :uid
          AND a.correct = FALSE
        ORDER BY a.attempted_on DESC
        LIMIT :limit
        """,
        {"uid": user_id, "limit": limit},
    )

    if not rows or isinstance(rows, dict):
        return []

    return [
        r._mapping["word_id"]
        for r in rows
        if r._mapping.get("word_id") is not None
    ]
