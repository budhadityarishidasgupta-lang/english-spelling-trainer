from shared.db import execute

def get_user_weak_words(user_id: int, course_id: int, limit: int = 30):
    """
    Returns weak words for a student based purely on spelling_attempts.
    """

    sql = """
    SELECT
      w.word_id,
      w.word,
      w.pattern,
      w.pattern_code,
      w.level,
      w.example_sentence,
      COUNT(a.attempt_id) AS wrong_attempts
    FROM spelling_attempts a
    JOIN spelling_words w
      ON w.word_id = a.word_id
    WHERE a.user_id = :user_id
      AND a.course_id = :course_id
      AND a.correct = FALSE
    GROUP BY
      w.word_id,
      w.word,
      w.pattern,
      w.pattern_code,
      w.level,
      w.example_sentence
    ORDER BY wrong_attempts DESC
    LIMIT :limit;
    """

    rows = execute(sql, {
        "user_id": user_id,
        "course_id": course_id,
        "limit": limit,
    })

    if not rows or isinstance(rows, dict):
        return []

    # normalize rows safely
    result = []
    for r in rows:
        if isinstance(r, dict):
            result.append(r)
        elif isinstance(r, (list, tuple)):
            result.append({
                "word_id": r[0],
                "word": r[1],
                "pattern": r[2],
                "pattern_code": r[3],
                "level": r[4],
                "example_sentence": r[5],
                "wrong_attempts": r[6],
            })

    return result
