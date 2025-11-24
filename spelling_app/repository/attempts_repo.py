from shared.db import fetch_all


def get_spelling_attempts_summary():
    """
    Returns per-student spelling performance summary.
    Pulls from spelling_attempts table keyed by item_id.
    """
    sql = """
        SELECT
            a.student_id AS user_id,
            u.name,
            COUNT(*) AS total_attempts,
            AVG(CASE WHEN a.is_correct THEN 1 ELSE 0 END) AS accuracy,
            MAX(a.attempted_at) AS last_attempt
        FROM spelling_attempts a
        LEFT JOIN users u ON u.id = a.student_id
        GROUP BY a.student_id, u.name
        ORDER BY last_attempt DESC NULLS LAST;
    """

    result = fetch_all(sql)

    if isinstance(result, dict):
        return result

    return [dict(getattr(row, "_mapping", row)) for row in result]
