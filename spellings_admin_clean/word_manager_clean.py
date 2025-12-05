from spelling_app.repository.words_repo import (
    get_word_by_text,
    insert_word,
)

from spelling_app.repository.spelling_lesson_repo import (
    get_lesson_by_name_and_course,
    create_lesson,
    map_word_to_lesson,
)


def get_or_create_word(word: str, pattern_code: int, course_id: int):
    """
    Always returns an integer word_id.
    """
    existing_rows = get_word_by_text(word, course_id=course_id)

    # If existing_rows is a list of dict rows
    if existing_rows and isinstance(existing_rows, list):
        row = existing_rows[0]
        if isinstance(row, dict) and "word_id" in row:
            return row["word_id"]

    # Create new word
    new_id = insert_word(
        word=word,
        pattern_code=pattern_code,
        pattern=None,   # CSV has no pattern text
        course_id=course_id,
    )

    return new_id


def get_or_create_lesson(lesson_name: str, course_id: int):
    """
    Always returns a dict: {lesson_id, course_id, lesson_name}
    """
    existing = get_lesson_by_name_and_course(
        lesson_name=lesson_name,
        course_id=course_id
    )

    # Existing lesson found in DB
    if existing and isinstance(existing, dict):
        return {
            "lesson_id": existing["lesson_id"],
            "course_id": existing["course_id"],
            "lesson_name": existing["lesson_name"],
        }

    # Create new lesson
    new_row = create_lesson(
        lesson_name=lesson_name,
        course_id=course_id
    )

    # new_row may be dict OR a raw SQL row
    if isinstance(new_row, dict) and "lesson_id" in new_row:
        return {
            "lesson_id": new_row["lesson_id"],
            "course_id": new_row["course_id"],
            "lesson_name": new_row["lesson_name"],
        }

    # If new_row is tuple or SQLAlchemy Row
    if hasattr(new_row, "_mapping"):
        m = new_row._mapping
        return {
            "lesson_id": m.get("lesson_id"),
            "course_id": m.get("course_id"),
            "lesson_name": m.get("lesson_name"),
        }

    # Fallback (should not happen)
    return {"lesson_id": new_row, "course_id": course_id, "lesson_name": lesson_name}


def link_word_to_lesson(word_id: int, lesson_id: int):
    """
    Maps a word to a lesson. Ignores duplicates.
    """
    return map_word_to_lesson(word_id=word_id, lesson_id=lesson_id)
