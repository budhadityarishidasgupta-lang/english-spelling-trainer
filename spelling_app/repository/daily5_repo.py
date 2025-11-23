from shared.db import fetch_all


def fetch_daily5_words():
    """
    Returns 5 adaptive words.
    For now: picks 5 random spelling_words.
    Final logic will be implemented later.
    """
    sql = """
        SELECT
            word_id,
            word,
            difficulty
        FROM spelling_words
        ORDER BY RANDOM()
        LIMIT 5;
    """

    result = fetch_all(sql)

    if isinstance(result, dict):
        return result

    return [dict(getattr(r, "_mapping", r)) for r in result]
