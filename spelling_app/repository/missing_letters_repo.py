# spelling_app/repository/missing_letters_repo.py

from shared.db import fetch_all


def fetch_missing_letter_words(limit: int = 10):
    """
    Returns random words suitable for missing-letter exercises.
    'limit' controls how many items are returned.
    """

    sql = """
        SELECT
            word_id,
            word,
            difficulty
        FROM spelling_words
        ORDER BY RANDOM()
        LIMIT :limit;
    """

    rows = fetch_all(sql, {"limit": limit})

    if isinstance(rows, dict):  # DB error
        return rows

    return [dict(getattr(r, "_mapping", r)) for r in rows]
