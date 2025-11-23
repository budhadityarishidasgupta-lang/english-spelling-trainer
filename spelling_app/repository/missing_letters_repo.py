from shared.db import fetch_all


def fetch_missing_letter_words():
    """
    For now, return 10 random words suitable for missing-letter exercises.
    Later, implement actual letter-hiding logic at service/UI layer.
    """
    sql = """
        SELECT
            word_id,
            word,
            difficulty
        FROM spelling_words
        ORDER BY RANDOM()
        LIMIT 10;
    """

    result = fetch_all(sql)

    if isinstance(result, dict):
        return result

    return [dict(getattr(r, "_mapping", r)) for r in result]
