from shared.db import execute


def get_global_weak_word_ids(user_id: int, limit: int = 50):
    rows = execute(
        """
        SELECT DISTINCT a.word_id
        FROM spelling_attempts a
        WHERE a.user_id = :uid
          AND a.correct IS NOT TRUE
        ORDER BY a.word_id
        LIMIT :limit
        """,
        {"uid": user_id, "limit": limit},
    )

    if not rows or isinstance(rows, dict):
        return []

    return [r["word_id"] for r in rows if r.get("word_id")]
