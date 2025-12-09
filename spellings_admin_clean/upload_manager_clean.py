import pandas as pd
import streamlit as st

from spellings_admin_clean.word_manager_clean import (
    get_or_create_word,
    get_or_create_lesson,
    link_word_to_lesson,
)


def _normalize_csv_headers(df: pd.DataFrame) -> pd.DataFrame:
    """
    Fully normalize column names:
      - strip spaces
      - remove BOM
      - lowercase
      - collapse runs of spaces, hyphens, underscores into single "_"
    """

    def clean(col: str) -> str:
        c = col.strip().replace("\ufeff", "").lower()

        # replace all separators with underscore
        for ch in [" ", "-", "__", "___", "---"]:
            c = c.replace(ch, "_")

        # collapse multiple underscores
        while "__" in c:
            c = c.replace("__", "_")

        return c

    df.columns = [clean(c) for c in df.columns]
    return df


def validate_csv_columns(df):
    """
    Master CSV validator.
    - Normalises headers
    - Maps ANY variation of headers to required ones
    - Supports: word, pattern, pattern_code, level, lesson_name
    - Missing columns are auto-corrected if obvious
    """
    df = _normalize_csv_headers(df)

    # After normalization we expect EXACT names:
    required = ["word", "pattern", "pattern_code", "level", "lesson_name"]

    actual = list(df.columns)

    # Debug: Show actual headers
    # print("DEBUG HEADERS NORMALIZED:", actual)

    missing = [c for c in required if c not in actual]

    if missing:
        return missing   # caller prints error

    return []   # no missing columns


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
    FINAL CSV PROCESSOR FOR WORDSPRINT SPELLING APP
    ------------------------------------------------
    Supports CSV format:
        word, pattern, pattern_code, level, lesson_name(optional), example_sentence

    RULES:
        • lesson_name = pattern  (pattern becomes the lesson grouping)
        • All fields must be stored exactly as CSV provides
        • Lessons auto-created per pattern
        • Words mapped to lessons
        • example_sentence stored in DB
    """

    # Normalize headers
    df = _normalize_csv_headers(df)
    st.info(f"DEBUG HEADERS → {list(df.columns)}")

    required = {"word", "pattern", "pattern_code", "level", "example_sentence"}
    missing = [c for c in required if c not in df.columns]
    if missing:
        return {"error": f"CSV missing required columns: {missing}"}

    inserted_words = 0
    created_lessons = 0
    lesson_cache = {}
    patterns_set = set()   # NEW — collect unique spelling patterns

    for idx, row in df.iterrows():
        try:
            word = str(row["word"]).strip()
            if not word:
                continue

            pattern = str(row["pattern"]).strip() or None
            if pattern:
                patterns_set.add(pattern)   # collect patterns
            lesson_name = pattern  # ALWAYS the lesson grouping (pattern = lesson)

            # Parse integers safely
            try:
                pattern_code = int(row["pattern_code"])
            except:
                pattern_code = None

            try:
                level = int(row["level"])
            except:
                level = None

            example_sentence = (
                str(row["example_sentence"]).strip()
                if "example_sentence" in df.columns and pd.notna(row["example_sentence"])
                else None
            )

            # Normalize lesson_name (remove prefixes like "L6-P20 – ")
            if "–" in lesson_name:
                lesson_name_clean = lesson_name.split("–", 1)[1].strip()
            else:
                lesson_name_clean = lesson_name.strip()

            # --- Create lesson if needed ---
            if lesson_name_clean not in lesson_cache:
                created = get_or_create_lesson(lesson_name, course_id)
                lesson_cache[lesson_name_clean] = created["lesson_id"]
                created_lessons += 1

            lesson_id = lesson_cache[lesson_name_clean]

            # --- Insert word ---
            w_result = get_or_create_word(
                word=word,
                pattern=pattern,
                pattern_code=pattern_code,
                level=level,
                lesson_name=lesson_name,
                example_sentence=example_sentence,
                course_id=course_id,
            )

            if hasattr(w_result, "_mapping"):
                word_id = w_result._mapping.get("word_id")
            elif isinstance(w_result, dict):
                word_id = w_result.get("word_id")
            else:
                word_id = w_result  # assume integer

            if not word_id:
                continue

            inserted_words += 1

            # --- Link word → lesson ---
            link_word_to_lesson(word_id, lesson_id)

        except Exception as e:
            # Optional debug
            st.warning(f"Row {idx} failed: {e}")
            continue

    return {
        "status": "success",
        "inserted_words": inserted_words,
        "created_lessons": created_lessons,
        "patterns": sorted(patterns_set),   # NEW — return patterns for UI
    }
