import pandas as pd
from spellings_admin_clean.utils_clean import read_csv_to_df, show_upload_summary
from spelling_app.repository.words_repo import insert_word
from spelling_app.repository.spelling_lesson_repo import (
    create_lesson,
    map_word_to_lesson,
)
from spelling_app.repository.lesson_repo import get_lessons_by_course


def process_spelling_csv(uploaded_file, course_id: int):
    """
    Upload CSV structure (expected):
    -----------------------------------------
    word, pattern, pattern_code, lesson_name
    -----------------------------------------

    Required columns:
      - word
      - lesson_name

    Optional:
      - pattern
      - pattern_code
    """

    df = read_csv_to_df(uploaded_file)

    required_cols = ["word", "lesson_name"]
    for c in required_cols:
        if c not in df.columns:
            return {"error": f"Missing required column: {c}"}

    # Normalize optional columns
    if "pattern" not in df.columns:
        df["pattern"] = None
    if "pattern_code" not in df.columns:
        df["pattern_code"] = None

    # Fetch existing lessons to avoid duplicates
    existing_lessons = get_lessons_by_course(course_id)
    lesson_map = {l["lesson_name"].strip().lower(): l["lesson_id"] for l in existing_lessons}

    created_lessons = 0
    created_words = 0
    mapped_words = 0

    for _, row in df.iterrows():
        word = str(row["word"]).strip()
        lesson_name = str(row["lesson_name"]).strip()
        pattern = row.get("pattern")
        pattern_code = row.get("pattern_code")

        # -----------------------------------------
        # 1. Create lesson if not exists
        # -----------------------------------------
        lesson_key = lesson_name.lower()
        if lesson_key not in lesson_map:
            new_lesson_id = create_lesson(lesson_name, course_id)
            lesson_map[lesson_key] = new_lesson_id
            created_lessons += 1

        lesson_id = lesson_map[lesson_key]

        # -----------------------------------------
        # 2. Insert word into spelling_words
        # -----------------------------------------
        new_word_id = insert_word(
            word=word,
            pattern_code=pattern_code,
            pattern=pattern,
            course_id=course_id,
        )

        if new_word_id:
            created_words += 1

        # -----------------------------------------
        # 3. Map word to lesson
        # -----------------------------------------
        if new_word_id:
            map_word_to_lesson(lesson_id, new_word_id)
            mapped_words += 1

    summary = {
        "created_lessons": created_lessons,
        "created_words": created_words,
        "mapped_words": mapped_words,
    }

    show_upload_summary(summary)
    return summary
