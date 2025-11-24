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


def ensure_lesson_exists(lesson_id: int, course_id: int):
    """
    Ensures a spelling lesson exists for the given lesson_id under a specific course.
    If it does not exist, create it.
    """
    sql_check = """
        SELECT lesson_id
        FROM spelling_lessons
        WHERE lesson_id = :lesson_id
          AND course_id = :course_id
        LIMIT 1;
    """
    rows = fetch_all(sql_check, {"lesson_id": lesson_id, "course_id": course_id})
    if rows and isinstance(rows, list):
        return  # already exists

    # Create new lesson
    sql_insert = """
        INSERT INTO spelling_lessons (lesson_id, course_id, title)
        VALUES (:lesson_id, :course_id, :title)
    """
    title = f"Lesson {lesson_id}"
    fetch_all(sql_insert, {
        "lesson_id": lesson_id,
        "course_id": course_id,
        "title": title
    })


def map_word_to_lesson(word_id: int, lesson_id: int, course_id: int):
    """
    Maps a word to a lesson inside a specific spelling course.
    Prevents duplicate mappings.
    """
    sql_check = """
        SELECT id FROM spelling_lesson_items
        WHERE word_id = :word_id
          AND lesson_id = :lesson_id
          AND course_id = :course_id
        LIMIT 1;
    """
    exists = fetch_all(sql_check, {
        "word_id": word_id,
        "lesson_id": lesson_id,
        "course_id": course_id
    })

    if exists and isinstance(exists, list):
        return  # mapping already exists

    sql_insert = """
        INSERT INTO spelling_lesson_items (word_id, lesson_id, course_id)
        VALUES (:word_id, :lesson_id, :course_id);
    """
    fetch_all(sql_insert, {
        "word_id": word_id,
        "lesson_id": lesson_id,
        "course_id": course_id
    })


def get_spelling_lesson(course_id: int, lesson_id: int):
    sql = """
        SELECT *
        FROM spelling_lessons
        WHERE course_id = :course_id
          AND lesson_id = :lesson_id
    """
    rows = fetch_all(sql, {"course_id": course_id, "lesson_id": lesson_id})
    return rows if isinstance(rows, list) else []
