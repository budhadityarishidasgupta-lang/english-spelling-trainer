from shared.db import fetch_all


def get_word_by_text(word):
    sql = """
        SELECT word_id, word, difficulty
        FROM spelling_words
        WHERE LOWER(word) = LOWER(:word)
        LIMIT 1;
    """
    result = fetch_all(sql, {"word": word})
    if isinstance(result, dict):
        return result
    return [dict(r._mapping) for r in result]


def insert_word(word):
    sql = """
        INSERT INTO spelling_words (word)
        VALUES (:word)
        RETURNING word_id;
    """
    result = fetch_all(sql, {"word": word})
    if isinstance(result, dict):
        return result
    return result[0]._mapping["word_id"]


def update_word(word_id, new_word):
    sql = """
        UPDATE spelling_words
        SET word = :new_word
        WHERE word_id = :word_id;
    """
    return fetch_all(sql, {"new_word": new_word, "word_id": word_id})


def delete_word(word_id):
    sql = """
        DELETE FROM spelling_words
        WHERE word_id = :word_id;
    """
    return fetch_all(sql, {"word_id": word_id})


def ensure_lesson_exists(lesson_id):
    sql = """
        INSERT INTO lessons (lesson_id, title, lesson_type)
        VALUES (:id, 'Auto Lesson ' || :id, 'spelling')
        ON CONFLICT (lesson_id) DO NOTHING;
    """
    return fetch_all(sql, {"id": lesson_id})


def map_word_to_lesson(word_id, lesson_id):
    sql = """
        INSERT INTO spelling_lesson_items (lesson_id, word_id)
        VALUES (:lesson_id, :word_id)
        ON CONFLICT DO NOTHING;
    """
    return fetch_all(sql, {"lesson_id": lesson_id, "word_id": word_id})
