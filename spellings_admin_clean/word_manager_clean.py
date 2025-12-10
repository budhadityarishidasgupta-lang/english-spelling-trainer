import pandas as pd

from shared.db import fetch_all, execute

from spelling_app.repository.words_repo import get_word_by_text, insert_word

from spelling_app.repository.spelling_lesson_repo import (
    get_lesson_by_name_and_course,
    get_or_create_lesson as repo_get_or_create_lesson,
    map_word_to_lesson,
)


def _safe_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


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


def get_or_create_lesson(lesson_name: str | None, course_id: int):
    """
    Always returns a dict: {lesson_id, course_id, lesson_name}

    If lesson_name is None or empty, we fall back to a generic name.
    """
    # Fallback for missing lesson name
    if not lesson_name:
        lesson_name = "General"

    existing = get_lesson_by_name_and_course(
        lesson_name=lesson_name,
        course_id=course_id,
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
    Link a word to a lesson in spelling_lesson_items.
    Uses columns: lesson_id, word_id, sort_order.
    sort_order is assigned as (max + 1) per lesson.
    """
    execute(
        """
        INSERT INTO spelling_lesson_items (lesson_id, word_id, sort_order)
        VALUES (
            :lesson_id,
            :word_id,
            COALESCE(
                (SELECT MAX(sort_order) + 1 FROM spelling_lesson_items WHERE lesson_id = :lesson_id),
                1
            )
        )
        ON CONFLICT DO NOTHING;
        """,
        {"lesson_id": lesson_id, "word_id": word_id},
    )


def process_uploaded_csv(uploaded_file, course_id: int):
    """
    Process CSV upload and insert words, lessons, and mapping relationships.

    Expected columns in CSV (case-insensitive):
      - word
      - pattern
      - pattern_code
      - level
      - lesson_name
      - example_sentence (optional)

    For each row:
      1) Ensure lesson exists (or create it)
      2) Ensure word exists (or create it)
      3) Link word to lesson in spelling_lesson_items
    """
    try:
        df = pd.read_csv(uploaded_file)
    except Exception as exc:  # defensive guard for malformed uploads
        return {"error": f"Could not read CSV: {exc}"}

    # Normalise headers (trim + lower)
    df.columns = [str(c).strip().lower() for c in df.columns]

    words_added = 0
    lessons_set: set[str | None] = set()
    patterns_set: set[str] = set()
    lesson_cache: dict[str, int | None] = {}

    for _, row in df.iterrows():
        # ----- WORD -----
        word_raw = row.get("word", "")
        word = str(word_raw).strip()
        if not word:
            # Skip blank rows
            continue

        # ----- PATTERN -----
        pattern_raw = row.get("pattern")
        pattern = str(pattern_raw).strip() if pattern_raw is not None else None
        pattern = pattern or None

        # ----- PATTERN CODE & LEVEL -----
        pattern_code = _safe_int(row.get("pattern_code"))
        level = _safe_int(row.get("level"))

        # ----- LESSON NAME -----
        lesson_name_raw = row.get("lesson_name")
        lesson_name = str(lesson_name_raw).strip() if lesson_name_raw is not None else None
        if not lesson_name:
            # Fallback if CSV does not specify lesson_name
            lesson_name = pattern or "General"

        # ----- EXAMPLE SENTENCE -----
        example_sentence_raw = row.get("example_sentence")
        example_sentence = (
            str(example_sentence_raw).strip()
            if example_sentence_raw is not None
            else None
        )

        # 1) Ensure lesson exists (use cache to reduce DB hits)
        cache_key = lesson_name
        if cache_key not in lesson_cache:
            lesson_info = get_or_create_lesson(lesson_name=lesson_name, course_id=course_id)
            lesson_id = lesson_info.get("lesson_id")
            lesson_cache[cache_key] = lesson_id
            lessons_set.add(lesson_name)
        else:
            lesson_id = lesson_cache[cache_key]

        if not lesson_id:
            # If lesson creation somehow failed, skip linking but continue
            continue

        # 2) Ensure word exists
        word_id = get_or_create_word(
            word=word,
            pattern=pattern,
            pattern_code=pattern_code,
            level=level,
            lesson_name=lesson_name,
            example_sentence=example_sentence,
            course_id=course_id,
        )

        if not word_id:
            # If word creation failed, skip linking
            continue

        # 3) Link word → lesson
        link_word_to_lesson(word_id=word_id, lesson_id=lesson_id)
        # Optional debug print (visible in logs)
        print(f"[CSV LINK] word='{word}' (id={word_id}) → lesson='{lesson_name}' (id={lesson_id})")

        words_added += 1

        if pattern is not None:
            patterns_set.add(pattern)

    return {
        "words_added": words_added,
        "lessons_created": len(lessons_set),
        "patterns": sorted(patterns_set),
    }


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
