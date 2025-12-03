# spelling_app/repository/weak_words_repo.py

from shared.db import fetch_all

def get_weak_words_summary(min_attempts: int = 4):
    """
    Returns aggregated statistics of spelling words where students frequently make mistakes.

    Uses:
      - spelling_attempts (student_id, item_id, is_correct, attempted_at)
      - spelling_words (word_id, word)
    """

    sql = f"""
        SELECT
            w.word,
            COUNT(*) AS attempts,
            SUM(CASE WHEN a.is_correct = FALSE THEN 1 ELSE 0 END) AS mistakes,
            ROUND(
                (SUM(CASE WHEN a.is_correct = FALSE THEN 1 ELSE 0 END)::decimal
                 / COUNT(*)) * 100, 2
            ) AS mistake_rate
        FROM spelling_attempts a
        JOIN spelling_words w ON w.word_id = a.item_id
        GROUP BY w.word
        HAVING COUNT(*) >= :min_attempts
        ORDER BY mistake_rate DESC, attempts DESC;
    """

    rows = fetch_all(sql, {"min_attempts": min_attempts})

    if isinstance(rows, dict):  # DB error bubble-up
        return rows

    return [dict(getattr(r, "_mapping", r)) for r in rows]
