import pandas as pd
from shared.db import fetch_all, fetch_one, execute
from spelling_app.repository.spelling_lesson_repo import (
    get_lesson_by_name_and_course,
    get_or_create_lesson as repo_get_or_create_lesson,
    map_word_to_lesson,
)

# ---------------------------
# Utility Helpers
# ---------------------------

def _safe_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


# ---------------------------
# WORD CREATION
# ---------------------------

def get_or_create_word(
    word: str,
    pattern: str | None,
    pattern_code: int | None,
    level: int | None,
    lesson_name: str | None,
    course_id: int,
    example_sentence: str | None = None,
):
    """
    Creates a word if it doesn't exist.
    If it exists and example_sentence is missing, backfills it.
    Always returns an integer word_id.
    """

    normalized_example = example_sentence.strip() if example_sentence else None

    existing = fetch_one(
        """
        SELECT word_id, example_sentence
        FROM spelling_words
        WHERE LOWER(word) = LOWER(:word)
          AND course_id = :course_id
        """,
        {"word": word, "course_id": course_id},
    )

    if existing:
        existing_mapping = getattr(existing, "_mapping", existing)
        word_id = existing_mapping.get("word_id")

        # 🔑 BACKFILL example sentence if missing
        db_example = existing_mapping.get("example_sentence")
        db_example_normalized = db_example.strip() if isinstance(db_example, str) else None

        if normalized_example and not db_example_normalized:
            execute(
                """
                UPDATE spelling_words
                SET example_sentence = :example_sentence
                WHERE word_id = :id AND course_id = :course_id
                """,
                {
                    "example_sentence": normalized_example,
                    "id": word_id,
                    "course_id": course_id,
                },
            )

        return word_id

    # 🆕 Create new word
    result = execute(
        """
        INSERT INTO spelling_words (
            word,
            course_id,
            pattern,
            pattern_code,
            level,
            lesson_name,
            example_sentence
        )
        VALUES (
            :word,
            :course_id,
            :pattern,
            :pattern_code,
            :level,
            :lesson_name,
            :example_sentence
        )
        RETURNING word_id
        """,
        {
            "word": word.strip(),
            "course_id": course_id,
            "pattern": pattern,
            "pattern_code": pattern_code,
            "level": level,
            "lesson_name": lesson_name,
            "example_sentence": normalized_example,
        },
    )

    if isinstance(result, list) and result:
        first_row = getattr(result[0], "_mapping", result[0])
        return first_row.get("word_id")

    if isinstance(result, dict):
        return result.get("word_id")

    return None


# ---------------------------
# LESSON CREATION
# ---------------------------

def get_or_create_lesson(lesson_name: str, course_id: int):
    """
    Always returns dict {lesson_id, course_id, lesson_name}
    """
    existing = get_lesson_by_name_and_course(
        lesson_name=lesson_name,
        course_id=course_id
    )

    if existing and isinstance(existing, dict):
        return {
            "lesson_id": existing["lesson_id"],
            "course_id": existing["course_id"],
            "lesson_name": existing["lesson_name"],
        }

    # Create new lesson
    lesson_id = repo_get_or_create_lesson(
        course_id=course_id,
        lesson_name=lesson_name
    )

    if lesson_id:
        return {"lesson_id": lesson_id, "course_id": course_id, "lesson_name": lesson_name}

    return {"lesson_id": None, "course_id": course_id, "lesson_name": lesson_name}


# ---------------------------
# LINK WORD → LESSON
# ---------------------------

def link_word_to_lesson(word_id: int, lesson_id: int):
    """
    Correct mapping insertion.
    Uses columns: lesson_id, word_id, sort_order.
    """
    execute(
        """
        INSERT INTO spelling_lesson_items (lesson_id, word_id, sort_order)
        SELECT
            :lesson_id,
            :word_id,
            COALESCE(MAX(sort_order) + 1, 1)
        FROM spelling_lesson_items
        WHERE lesson_id = :lesson_id
        ON CONFLICT DO NOTHING;
        """,
        {"lesson_id": lesson_id, "word_id": word_id},
    )
    print(f"[LINK] word_id={word_id} → lesson_id={lesson_id}")


# ---------------------------
# PROCESS UPLOADED CSV
# ---------------------------

def process_uploaded_csv(uploaded_file, course_id: int):
    """
    Full CSV processor: creates lessons, words, and mappings.
    Ensures student dashboard will show words for practice.
    """
    try:
        df = pd.read_csv(uploaded_file)
    except Exception as exc:
        return {"error": f"Could not read CSV: {exc}"}

    # Normalize headers
    df.columns = [str(c).strip().lower() for c in df.columns]

    words_added = 0
    lessons_set = set()
    patterns_set = set()

    lesson_cache = {}

    for _, row in df.iterrows():
        word = str(row.get("word", "")).strip()
        if not word:
            continue

        pattern_raw = row.get("pattern")
        pattern = str(pattern_raw).strip() if pattern_raw else None
        pattern = pattern or None

        pattern_code = _safe_int(row.get("pattern_code"))
        level = _safe_int(row.get("level"))

        raw_lesson_name = row.get("lesson_name")
        lesson_name = str(raw_lesson_name).strip() if raw_lesson_name else None

        if not lesson_name:
            lesson_name = pattern or "General"

        example_sentence_raw = row.get("example_sentence")
        example_sentence = str(example_sentence_raw).strip() if example_sentence_raw else None

        # 1) LESSON (cached)
        if lesson_name not in lesson_cache:
            lesson_info = get_or_create_lesson(
                lesson_name=lesson_name,
                course_id=course_id
            )
            lesson_id = lesson_info.get("lesson_id")
            lesson_cache[lesson_name] = lesson_id
            lessons_set.add(lesson_name)
        else:
            lesson_id = lesson_cache[lesson_name]

        if not lesson_id:
            print(f"[WARN] Lesson creation failed for '{lesson_name}'. Skipping row.")
            continue

        # 2) WORD
        word_id = get_or_create_word(
            word=word,
            pattern=pattern,
            pattern_code=pattern_code,
            level=level,
            lesson_name=lesson_name,
            example_sentence=example_sentence,
            course_id=course_id
        )
        if not word_id:
            print(f"[WARN] Word creation failed for '{word}'.")
            continue

        # 3) LINK WORD → LESSON
        link_word_to_lesson(word_id=word_id, lesson_id=lesson_id)

        if pattern:
            patterns_set.add(pattern)
        words_added += 1

    return {
        "words_added": words_added,
        "lessons_created": len(lessons_set),
        "patterns": sorted(patterns_set),
        "status": "success",
    }


# ---------------------------
# LESSON QUERIES
# ---------------------------

from spelling_app.repository.spelling_lesson_repo import (
    get_lessons_for_course as repo_get_lessons_for_course,
    get_lesson_words as repo_get_lesson_words,
)


def get_lessons_for_course(course_id: int):
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


def get_lesson_words(course_id: int, lesson_id: int):
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
