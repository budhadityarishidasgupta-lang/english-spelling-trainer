from shared.db import fetch_all


def get_spelling_attempts_summary():
    """
    Returns per-student spelling performance summary.
    Pulls from attempts table where attempt_type='spelling'.
    """
    sql = """
        SELECT
            a.user_id,
            u.name,
            COUNT(*) AS total_attempts,
            AVG(CASE WHEN a.is_correct THEN 1 ELSE 0 END) AS accuracy,
            MAX(a.attempted_at) AS last_attempt
        FROM attempts a
        LEFT JOIN users u ON u.id = a.user_id
        WHERE a.attempt_type = 'spelling'
        GROUP BY a.user_id, u.name
        ORDER BY last_attempt DESC NULLS LAST;
    """

    result = fetch_all(sql)

    if isinstance(result, dict):
        return result

    return [dict(getattr(row, "_mapping", row)) for row in result]
