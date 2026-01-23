from shared.db import fetch_all, safe_rows


def get_weak_word_ids_for_user(user_id: int, limit: int = 50) -> list[int]:
    """
    Returns DISTINCT word_ids where the user answered incorrectly.
    Ordered by most recent failure.
    """
    rows = fetch_all(
        """
        SELECT DISTINCT ON (word_id)
            word_id,
            created_at
        FROM spelling_attempts
        WHERE user_id = :uid
          AND correct = FALSE
        ORDER BY word_id, created_at DESC
        LIMIT :limit
        """,
        {"uid": user_id, "limit": limit},
    )

    if not rows or isinstance(rows, dict):
        return []

    word_ids = []
    for r in rows:
        m = getattr(r, "_mapping", r)
        if m.get("word_id"):
            word_ids.append(int(m["word_id"]))

    return word_ids


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
        ORDER BY w.word
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
