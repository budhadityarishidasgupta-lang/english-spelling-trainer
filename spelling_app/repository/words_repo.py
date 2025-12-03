# spelling_app/repository/words_repo.py

from shared.db import fetch_all


def get_word_by_text(word: str):
    """
    Fetch a word row by exact text match (case-insensitive).
    Returns a list of matching rows or an error dict.
    """
    sql = """
        SELECT
            word_id,
            word,
            difficulty
        FROM spelling_words
        WHERE LOWER(word) = LOWER(:word)
        LIMIT 1;
    """
    rows = fetch_all(sql, {"word": word})

    if isinstance(rows, dict):  # DB error
        return rows

    return [dict(getattr(r, "_mapping", r)) for r in rows]


def insert_word(word: str, difficulty=None, pattern_code=None, course_id=None):
    """
    Insert a word into spelling_words.
    Accepts optional difficulty, pattern_code, course_id depending on schema.
    """

    sql = """
        INSERT INTO spelling_words (word, difficulty, pattern_code, course_id)
        VALUES (:word, :difficulty, :pattern_code, :course_id)
        RETURNING word_id;
    """

    rows = fetch_all(
        sql,
        {
            "word": word,
            "difficulty": difficulty,
            "pattern_code": pattern_code,
            "course_id": course_id,
        },
    )

    if isinstance(rows, dict):  # DB error
        return rows

    row = rows[0]
    if hasattr(row, "_mapping"):
        return row._mapping.get("word_id")
    if isinstance(row, dict):
        return row.get("word_id")
    try:
        return row[0]
    except Exception:
        return None


def update_word(word_id: int, new_word: str):
    """
    Update a word's text value.
    """
    sql = """
        UPDATE spelling_words
        SET word = :new_word
        WHERE word_id = :word_id;
    """
    return fetch_all(sql, {"new_word": new_word, "word_id": word_id})


def delete_word(word_id: int):
    """
    Delete a word row from spelling_words.
    """
    sql = """
        DELETE FROM spelling_words
        WHERE word_id = :word_id;
    """
    return fetch_all(sql, {"word_id": word_id})
