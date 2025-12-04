import pandas as pd

from spellings_admin_clean.word_manager_clean import (
    get_or_create_word,
    get_or_create_lesson,
    link_word_to_lesson,
)


def process_spelling_csv(df: pd.DataFrame, course_id: int):
    """
    Process CSV with columns:
      - word
      - pattern_code
      - lesson_name

    Returns a summary dict.
    """

    required_cols = {"word", "pattern_code", "lesson_name"}
    if not required_cols.issubset(df.columns):
        return {"error": f"CSV must contain columns: {required_cols}"}

    inserted_words = 0
    existing_words = 0
    created_lessons = 0
    linked = 0

    lesson_cache = {}  # lesson_name -> lesson_id

    for idx, row in df.iterrows():
        word = str(row["word"]).strip()
        pattern_code = int(row["pattern_code"])
        lesson_name = str(row["lesson_name"]).strip()

        # 1. Create or fetch lesson
        if lesson_name not in lesson_cache:
            lesson_row = get_or_create_lesson(lesson_name, course_id)
            if not lesson_row or "lesson_id" not in lesson_row:
                continue

            lesson_id = lesson_row["lesson_id"]
            lesson_cache[lesson_name] = lesson_id
            created_lessons += 1
        else:
            lesson_id = lesson_cache[lesson_name]

        # 2. Create or fetch word
        word_id = get_or_create_word(word, pattern_code, course_id)
        if not word_id:
            continue

        if isinstance(word_id, int):
            inserted_words += 1
        else:
            existing_words += 1

        # 3. Link word to lesson
        link_word_to_lesson(word_id, lesson_id)
        linked += 1

    return {
        "created_lessons": created_lessons,
        "inserted_words": inserted_words,
        "existing_words": existing_words,
        "linked": linked,
    }
