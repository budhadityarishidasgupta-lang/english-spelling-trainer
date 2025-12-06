from spelling_app.repository.words_repo import get_word_by_text, insert_word

from spelling_app.repository.spelling_lesson_repo import (
    get_lesson_by_name_and_course,
    get_or_create_lesson as repo_get_or_create_lesson,
    map_word_to_lesson,
)


def get_or_create_word(
    *,
    word: str,
    pattern: str | None,
    pattern_code: int | None,
    level: int | None,
    lesson_name: str | None,
    example_sentence: str | None,
    course_id: int,
):
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
        pattern=pattern,
        pattern_code=pattern_code,
        level=level,
        lesson_name=lesson_name,
        example_sentence=example_sentence,
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
    lesson_id = repo_get_or_create_lesson(course_id=course_id, lesson_name=lesson_name)

    if lesson_id:
        return {"lesson_id": lesson_id, "course_id": course_id, "lesson_name": lesson_name}

    # Fallback (should not happen)
    return {"lesson_id": None, "course_id": course_id, "lesson_name": lesson_name}


def link_word_to_lesson(word_id: int, lesson_id: int):
    """
    Maps a word to a lesson. Ignores duplicates.
    """
    return map_word_to_lesson(word_id=word_id, lesson_id=lesson_id)

# ---------------------------------------------------------
# FETCH LESSONS FOR COURSE
# ---------------------------------------------------------
from spelling_app.repository.spelling_lesson_repo import (
    get_lessons_for_course as repo_get_lessons_for_course,
    get_lesson_words as repo_get_lesson_words,
)


def get_lessons_for_course(course_id: int):
    """
    Returns a list of lessons for the selected course.
    Each lesson is a dict: {lesson_id, course_id, lesson_name}
    """
    rows = repo_get_lessons_for_course(course_id)

    if not rows or isinstance(rows, dict):
        return []

    lessons = []
    for row in rows:
        if hasattr(row, "_mapping"):
            lessons.append(dict(row._mapping))
        elif isinstance(row, dict):
            lessons.append(row)
    return lessons


# ---------------------------------------------------------
# FETCH WORDS MAPPED TO A LESSON
# ---------------------------------------------------------
def get_lesson_words(course_id: int, lesson_id: int):
    """
    Returns all words mapped to a given lesson_id.
    Output columns: word_id, word, pattern_code, lesson_id
    """
    rows = repo_get_lesson_words(course_id=course_id, lesson_id=lesson_id)

    if not rows or isinstance(rows, dict):
        return []

    words = []
    for row in rows:
        if hasattr(row, "_mapping"):
            words.append(dict(row._mapping))
        elif isinstance(row, dict):
            words.append(row)
    return words

