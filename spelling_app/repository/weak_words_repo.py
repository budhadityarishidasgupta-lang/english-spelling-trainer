from shared.db import execute, fetch_all, safe_rows


def get_global_weak_words(user_id: int, limit: int = 50):
    """
    Return weak words resolved by WORD TEXT, not stale word_id.
    This avoids orphaned spelling_attempts references.
    """

    sql = """
    SELECT DISTINCT w.word, MAX(a.created_at) AS last_seen
    FROM spelling_attempts a
    JOIN spelling_words w
      ON w.word_id = a.word_id
    WHERE a.user_id = :uid
      AND a.correct = FALSE
    GROUP BY w.word
    ORDER BY last_seen DESC
    LIMIT :limit
    """

    rows = execute(sql, {"uid": user_id, "limit": limit})

    if not rows or isinstance(rows, dict):
        return []

    safe = safe_rows(rows)
    return [r["word"] for r in safe if "word" in r]


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
