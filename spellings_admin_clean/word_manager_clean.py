import pandas as pd
from shared.db import execute
from shared.db import safe_row
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
    hint: str | None = None,
    return_created: bool = False,
):
    w = (word or "").strip()
    if not w:
        return (None, False) if return_created else None

    example_sentence = example_sentence.strip() if example_sentence else None
    hint = hint.strip() if hint else None

    # 1) SELECT existing word
    existing = execute(
        """
        SELECT word_id
        FROM spelling_words
        WHERE LOWER(word) = LOWER(:word)
        LIMIT 1
        """,
        {"word": w},
    )

    if isinstance(existing, dict) and existing.get("error"):
        print(f"[DB-ERROR] SELECT spelling_words failed: {existing.get('error')}")
        return (None, False) if return_created else None

    if isinstance(existing, list) and existing:
        row = safe_row(existing[0])
        word_id = row.get("word_id")
        return (word_id, False) if return_created else word_id

    # 2) INSERT new word
    inserted = execute(
        """
        INSERT INTO spelling_words (
            word,
            course_id,
            pattern,
            pattern_code,
            level,
            lesson_name,
            example_sentence,
            hint
        )
        VALUES (
            :word,
            :course_id,
            :pattern,
            :pattern_code,
            :level,
            :lesson_name,
            :example_sentence,
            :hint
        )
        RETURNING word_id
        """,
        {
            "word": w,
            "course_id": course_id,
            "pattern": pattern,
            "pattern_code": pattern_code,
            "level": level,
            "lesson_name": lesson_name,
            "example_sentence": example_sentence,
            "hint": hint,
        },
    )

    if isinstance(inserted, dict) and inserted.get("error"):
        print(
            f"[DB-ERROR] INSERT spelling_words failed "
            f"(word='{w}', course_id={course_id}): {inserted.get('error')}"
        )
        return (None, False) if return_created else None

    if isinstance(inserted, list) and inserted:
        row = safe_row(inserted[0])
        word_id = row.get("word_id")
        return (word_id, True) if return_created else word_id

    return (None, False) if return_created else None


# ---------------------------
# LESSON CREATION
# ---------------------------

def get_or_create_lesson(course_id: int, lesson_name: str):
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
    # Ensure core mapping exists for reporting / practice queries
    map_word_to_lesson(word_id=word_id, lesson_id=lesson_id)

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
        if hasattr(uploaded_file, "seek"):
            uploaded_file.seek(0)
        df = pd.read_csv(uploaded_file)
    except Exception as exc:
        return {"error": f"Could not read CSV: {exc}"}

    # Normalize headers
    df.columns = [str(c).strip().lower() for c in df.columns]

    words_added = 0
    mappings_added = 0
    lessons_created = 0
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

        pattern_code_raw = row.get("pattern_code")
        pattern_code = _safe_int(pattern_code_raw)
        lesson_name = (str(pattern_code_raw).strip() if pattern_code_raw is not None else None) or "Uncategorized"

        level = _safe_int(row.get("difficulty") or row.get("level"))

        example_sentence_raw = row.get("example") or row.get("example_sentence")
        example_sentence = str(example_sentence_raw).strip() if example_sentence_raw else None

        hint = str(row.get("hint", "")).strip()

        # 1) LESSON (cached)
        if lesson_name not in lesson_cache:
            lesson_info = get_or_create_lesson(
                lesson_name=lesson_name,
                course_id=course_id
            )
            lesson_id = lesson_info.get("lesson_id")
            lesson_cache[lesson_name] = lesson_id
            lessons_set.add(lesson_name)
            lessons_created += 1
        else:
            lesson_id = lesson_cache[lesson_name]

        if not lesson_id:
            print(f"[WARN] Lesson creation failed for '{lesson_name}'. Skipping row.")
            continue

        # 2) WORD
        word_id, created = get_or_create_word(
            word=word,
            pattern=pattern,
            pattern_code=pattern_code,
            level=level,
            lesson_name=lesson_name,
            example_sentence=example_sentence,
            hint=hint,
            course_id=course_id,
            return_created=True,
        )
        if not word_id:
            print(f"[WARN] Word creation failed for '{word}'.")
            continue

        # 3) LINK WORD → LESSON
        link_word_to_lesson(word_id=word_id, lesson_id=lesson_id)
        mappings_added += 1

        if pattern:
            patterns_set.add(pattern)
        if created:
            words_added += 1

    return {
        "status": "success",
        "words_added": words_added,
        "lessons_created": lessons_created,
        "mappings_added": mappings_added,
        "patterns": sorted(patterns_set),
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
