from sqlalchemy import text
from shared.db import engine
from typing import Any, Dict, List, Optional
from shared.db import execute, fetch_all


def _row_to_mapping(row: Any) -> Dict[str, Any]:
    if hasattr(row, "_mapping"):
        return dict(row._mapping)
    if isinstance(row, dict):
        return row
    try:
        return dict(row)
    except Exception:
        return {}


# ----------------------------------------------------------
# GET WORD BY TEXT
# ----------------------------------------------------------
def get_word_by_text(word: str, course_id: int) -> List[Dict[str, Any]]:
    rows = fetch_all(
        """
        SELECT word_id, word, pattern, pattern_code, level,
               lesson_name, example_sentence, course_id
        FROM spelling_words
        WHERE LOWER(word) = LOWER(:word)
          AND course_id = :cid
        """,
        {"word": word, "cid": course_id},
    )

    if isinstance(rows, dict) or not rows:
        return []

    return [_row_to_mapping(r) for r in rows]


# ----------------------------------------------------------
# INSERT OR UPDATE WORD (UPSERT)
# ----------------------------------------------------------
def insert_word(
    *,
    word: str,
    pattern: Optional[str],
    pattern_code: Optional[int],
    level: Optional[int],
    lesson_name: Optional[str],
    example_sentence: Optional[str],
    course_id: int,
) -> Optional[int]:

    sql = text("""
        INSERT INTO spelling_words
            (word, pattern, pattern_code, level, lesson_name, example_sentence, course_id)
        VALUES
            (:word, :pattern, :pattern_code, :level, :lesson_name, :example_sentence, :course_id)
        ON CONFLICT (word, course_id)
        DO UPDATE SET
            pattern          = EXCLUDED.pattern,
            pattern_code     = EXCLUDED.pattern_code,
            level            = EXCLUDED.level,
            lesson_name      = EXCLUDED.lesson_name,
            example_sentence = EXCLUDED.example_sentence
        RETURNING word_id;
    """)

    rows = fetch_all(
        sql,
        {
            "word": word,
            "pattern": pattern,
            "pattern_code": pattern_code,
            "level": level,
            "lesson_name": lesson_name,
            "example_sentence": example_sentence,
            "course_id": course_id,
        },
    )

    if isinstance(rows, dict) or not rows:
        return None

    return _row_to_mapping(rows[0]).get("word_id")


# ----------------------------------------------------------
# GET ALL WORDS FOR COURSE
# ----------------------------------------------------------
def get_words_for_course(course_id: int) -> List[Dict[str, Any]]:
    rows = fetch_all(
        """
        SELECT word_id, word, pattern, pattern_code,
               level, lesson_name, example_sentence, course_id
        FROM spelling_words
        WHERE course_id = :cid
        ORDER BY level, pattern_code, word
        """,
        {"cid": course_id},
    )

    if isinstance(rows, dict) or not rows:
        return []

    out = []
    for r in rows:
        m = getattr(r, "_mapping", r)
        out.append({
            "word_id": m["word_id"],
            "word": m["word"],
            "pattern": m.get("pattern"),
            "pattern_code": m.get("pattern_code"),
            "level": m.get("level"),
            "lesson_name": m.get("lesson_name"),
            "example_sentence": m.get("example_sentence"),
            "course_id": m.get("course_id"),
        })
    return out


# ----------------------------------------------------------
# BULK CSV IMPORT (UPSERT)
# ----------------------------------------------------------
def insert_spelling_words_from_csv(course_id: int, rows: List[Dict[str, Any]]):
    sql = text("""
        INSERT INTO spelling_words
            (course_id, word, pattern_code, level, pattern, lesson_name, example_sentence)
        VALUES
            (:course_id, :word, :pattern_code, :level, :pattern, :lesson_name, :example_sentence)
        ON CONFLICT (word, course_id)
        DO UPDATE SET
            pattern          = EXCLUDED.pattern,
            pattern_code     = EXCLUDED.pattern_code,
            level            = EXCLUDED.level,
            lesson_name      = EXCLUDED.lesson_name,
            example_sentence = EXCLUDED.example_sentence;
    """)

    with engine.begin() as conn:
        for r in rows:
            w = (r.get("word") or "").strip()
            if not w:
                continue

            # Safe parse
            pattern_code_raw = (r.get("pattern_code") or "").strip()
            level_raw        = (r.get("level") or "").strip()

            pattern_code = int(pattern_code_raw) if pattern_code_raw else 0
            level        = int(level_raw) if level_raw else None

            conn.execute(sql, {
                "course_id": course_id,
                "word": w,
                "pattern": (r.get("pattern") or "").strip() or None,
                "pattern_code": pattern_code,
                "level": level,
                "lesson_name": (r.get("lesson_name") or "").strip() or None,
                "example_sentence": (r.get("example_sentence") or "").strip() or None,
            })
