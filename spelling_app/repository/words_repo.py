# spelling_app/repository/words_repo.py

from shared.db import fetch_all


def get_word_by_text(word: str, course_id: int = None):
    """
    Fetch a word row by exact text match (case-insensitive).
    Optionally filter by course_id.
    """
    if course_id is not None:
        sql = """
            SELECT word_id, word, pattern_code, course_id, pattern
            FROM spelling_words
            WHERE LOWER(word) = LOWER(:word)
              AND course_id = :course_id
            LIMIT 1;
        """
        params = {"word": word, "course_id": course_id}
    else:
        sql = """
            SELECT word_id, word, pattern_code, course_id, pattern
            FROM spelling_words
            WHERE LOWER(word) = LOWER(:word)
            LIMIT 1;
        """
        params = {"word": word}

    rows = fetch_all(sql, params)

    if isinstance(rows, dict):  # DB error
        return rows

    return [dict(getattr(r, "_mapping", r)) for r in rows]


def insert_word(word: str, pattern_code: int = None, pattern: str = None, course_id: int = None):
    """
    Insert a word into spelling_words.
    Matches the actual DB schema:
      word_id (serial PK)
      course_id (int)
      pattern_code (int)
      word (text)
      pattern (text)
    """

    sql = """
        INSERT INTO spelling_words (word, pattern_code, course_id, pattern)
        VALUES (:word, :pattern_code, :course_id, :pattern)
        RETURNING word_id;
    """

    rows = fetch_all(
        sql,
        {
            "word": word,
            "pattern_code": pattern_code,
            "course_id": course_id,
            "pattern": pattern,
        },
    )

    if isinstance(rows, dict):  # DB error
        return rows

    if not rows:
        return None

    row = rows[0]

    # SQLAlchemy row object
    if hasattr(row, "_mapping"):
        return row._mapping.get("word_id")

    # fallback dict mode
    if isinstance(row, dict):
        return row.get("word_id")

    # fallback tuple mode
    try:
        return row[0]
    except Exception:
        return None


def update_word(word_id: int, new_word: str):
    sql = """
        UPDATE spelling_words
        SET word = :new_word
        WHERE word_id = :word_id;
    """
    return fetch_all(sql, {"new_word": new_word, "word_id": word_id})


def delete_word(word_id: int):
    sql = """
        DELETE FROM spelling_words
        WHERE word_id = :word_id;
    """
    return fetch_all(sql, {"word_id": word_id})
