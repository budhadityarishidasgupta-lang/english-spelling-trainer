from shared.db import fetch_all

def get_weak_words_summary():
    """
    Returns aggregated statistics of spelling words where students
    frequently make mistakes.
    """
    sql = """
        SELECT
            w.word,
            COUNT(*) AS attempts,
            SUM(CASE WHEN a.is_correct = false THEN 1 ELSE 0 END) AS mistakes,
            ROUND(
                (SUM(CASE WHEN a.is_correct = false THEN 1 ELSE 0 END)::decimal 
                 / COUNT(*)) * 100, 2
            ) AS mistake_rate
        FROM attempts a
        LEFT JOIN spelling_words w ON w.word_id = a.word_id
        WHERE a.attempt_type = 'spelling'
        GROUP BY w.word
        HAVING COUNT(*) > 3
        ORDER BY mistake_rate DESC, attempts DESC;
    """

    result = fetch_all(sql)

    if isinstance(result, dict):
        return result

    return [dict(getattr(row, "_mapping", row)) for row in result]
