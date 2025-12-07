import pandas as pd
import streamlit as st

from spellings_admin_clean.word_manager_clean import (
    get_or_create_word,
    get_or_create_lesson,
    link_word_to_lesson,
)


def _normalize_csv_headers(df: pd.DataFrame) -> pd.DataFrame:
    """Trim whitespace/BOM and lowercase column headers."""

    df.columns = [c.strip().replace("\ufeff", "").lower() for c in df.columns]
    return df


def validate_csv_columns(df):
    """
    Ensures the uploaded CSV contains the required columns.
    FLEXIBLE MATCHING:
      - case-insensitive
      - ignores spaces, underscores, hyphens
      - pattern + example_sentence are OPTIONAL
    """
    df = _normalize_csv_headers(df)

    required = ["word", "pattern_code", "level", "lesson_name"]
    optional = ["pattern", "example_sentence"]

    # 🚀 Normalize everything: remove spaces, underscores, hyphens
    def norm(s):
        return s.strip().replace("\ufeff", "").lower().replace(" ", "").replace("_", "").replace("-", "")

    df_cols_norm = [norm(c) for c in df.columns]

    missing = []
    for col in required:
        if norm(col) not in df_cols_norm:
            missing.append(col)

    # pattern + example_sentence are OPTIONAL → do NOT include them in missing

    return missing


def _compute_difficulty(word: str, pattern_code: int | None, explicit: int | None):
    """
    Compute a difficulty value for internal use (not yet stored in DB).
    - If explicit difficulty is provided in CSV, use it (clamped 1–5).
    - Otherwise, derive from word length + pattern_code.
    """
    if explicit is not None:
        try:
            d = int(explicit)
            return max(1, min(5, d))
        except Exception:
            pass

    word = word or ""
    length = len(word)

    # Base on length
    if length <= 5:
        base = 1
    elif length <= 8:
        base = 2
    elif length <= 11:
        base = 3
    else:
        base = 4

    # Adjust with pattern_code a bit
    try:
        pc = int(pattern_code) if pattern_code is not None else 0
    except Exception:
        pc = 0

    if pc >= 10:
        base += 1

    return max(1, min(5, base))


def process_spelling_csv(df: pd.DataFrame, course_id: int):
    """
    Process CSV for uploading words & lessons.

    Supported formats:

    1) SIMPLE COURSE (current usage)
       Columns (required):
         - word
         - pattern_code
         - lesson_name

    2) PATTERN COURSE (future-friendly)
       Columns (required):
         - word
         - pattern_code
         - pattern_text
         - difficulty

       In this mode:
         - lesson_name is derived from pattern_text
         - difficulty is computed from CSV or rules
    """

    df = _normalize_csv_headers(df)

    # Validate CSV structure
    missing = validate_csv_columns(df)
    if missing:
        st.error(f"CSV is missing required columns: {', '.join(missing)}")
        return
    else:
        st.success("CSV successfully validated and ready for upload.")

    simple_cols = {"word", "pattern_code", "lesson_name"}
    pattern_cols = {"word", "pattern_code", "pattern_text", "difficulty"}

    mode = None
    if simple_cols.issubset(df.columns):
        mode = "simple"
    elif pattern_cols.issubset(df.columns):
        mode = "pattern"
    else:
        return {
            "error": (
                "CSV format not recognised. Expected either:\n"
                "A) word, pattern_code, lesson_name\n"
                "or\n"
                "B) word, pattern_code, pattern_text, difficulty"
            ),
            "columns_seen": list(df.columns),
        }

    inserted_words = 0
    existing_words = 0
    created_lessons = 0
    linked = 0

    difficulty_buckets = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}

    # Cache lesson_name -> lesson_id to reduce DB calls
    lesson_cache: dict[str, int] = {}

    for idx, row in df.iterrows():
        try:
            word = str(row["word"]).strip()
            if not word:
                continue

            pattern_code = row.get("pattern_code", None)
            try:
                pattern_code_int = int(pattern_code) if pd.notna(pattern_code) else None
            except Exception:
                pattern_code_int = None

            pattern = row.get("pattern") if "pattern" in row else None
            example_sentence = row.get("example_sentence") if "example_sentence" in row else None
            level_val = row.get("level", None)
            try:
                level_int = int(level_val) if pd.notna(level_val) else None
            except Exception:
                level_int = None

            # --- Decide lesson_name & difficulty based on mode ---
            if mode == "simple":
                # Use lesson_name from CSV
                lesson_name = str(row.get("lesson_name", "")).strip() or "Lesson 1"
                pattern_text = None
                explicit_diff = None
            else:
                # PATTERN mode: use pattern_text as lesson name
                pattern_text = str(row.get("pattern_text", "")).strip() or None
                lesson_name = pattern_text or f"Pattern {pattern_code_int or ''}".strip()
                explicit_diff = row.get("difficulty", None)

            difficulty = _compute_difficulty(
                word=word,
                pattern_code=pattern_code_int,
                explicit=explicit_diff,
            )
            difficulty_buckets[difficulty] += 1

            # 1) Create or get lesson
            if lesson_name not in lesson_cache:
                lesson_row = get_or_create_lesson(lesson_name, course_id)
                # lesson_row is a dict with lesson_id
                lesson_id = lesson_row["lesson_id"]
                lesson_cache[lesson_name] = lesson_id
                created_lessons += 1
            else:
                lesson_id = lesson_cache[lesson_name]

            # 2) Create or get word (DB schema currently: word, pattern_code, course_id, pattern=None)
            word_id = get_or_create_word(
                word=word,
                pattern=pattern,
                pattern_code=pattern_code_int,
                level=level_int,
                lesson_name=lesson_name,
                example_sentence=example_sentence,
                course_id=course_id,
            )

            if not word_id:
                continue

            # current get_or_create_word returns an int word_id
            inserted_words += 1  # we treat them as inserted or re-used; no strict split possible here

            # 3) Link word to lesson
            link_word_to_lesson(word_id, lesson_id)
            linked += 1

        except Exception as e:
            # You can optionally log per-row errors here
            # For now we just skip bad rows
            continue

    return {
        "mode": mode,
        "created_lessons": created_lessons,
        "inserted_words": inserted_words,
        "existing_words": existing_words,
        "linked": linked,
        "difficulty_distribution": difficulty_buckets,
    }
