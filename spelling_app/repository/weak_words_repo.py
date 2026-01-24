from sqlalchemy import text


def fetch_user_weak_words(conn, user_id: int):
    sql = """
        SELECT DISTINCT
            w.word_id,
            w.word
        FROM spelling_attempts a
        JOIN spelling_words w
          ON w.word_id = a.word_id
        WHERE a.user_id = :user_id
          AND a.correct = FALSE
        ORDER BY w.word;
    """
    rows = conn.execute(text(sql), {"user_id": user_id}).fetchall()
    return [dict(r._mapping) for r in rows]
