from shared.db import fetch_all, safe_rows


def get_global_weak_word_ids(user_id: int, limit: int = 50):
    rows = fetch_all(
        """
        SELECT DISTINCT a.word_id
        FROM spelling_attempts a
        WHERE a.user_id = :user_id
          AND a.correct = FALSE
        ORDER BY a.created_at DESC
        LIMIT :limit
        """,
        {"user_id": user_id, "limit": limit},
    )

    if not rows or isinstance(rows, dict):
        return []

    safe = safe_rows(rows)
    return [r["word_id"] for r in safe if r.get("word_id")]


def load_weak_words_by_ids(word_ids: list[int]) -> list[dict]:
    if not word_ids:
        return []

    rows = fetch_all(
        """
        SELECT
            w.word_id,
            w.word,
            COALESCE(o.hint_text, w.hint) AS hint,
            w.example_sentence
        FROM spelling_words w
        LEFT JOIN spelling_hint_overrides o
          ON o.word_id = w.word_id
        WHERE w.word_id = ANY(:ids)
        ORDER BY w.word_id
        """,
        {"ids": word_ids},
    )

    if not rows or isinstance(rows, dict):
        return []

    safe = safe_rows(rows)
    return [
        {
            "word_id": r["word_id"],
            "word": r["word"],
            "hint": r.get("hint"),
            "example_sentence": r.get("example_sentence"),
        }
        for r in safe
    ]
