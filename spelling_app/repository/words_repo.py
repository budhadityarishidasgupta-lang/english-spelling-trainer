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


def get_word_by_text(word: str, course_id: int) -> List[Dict[str, Any]]:
    rows = fetch_all(
        """
        SELECT word_id,
               word,
               pattern,
               pattern_code,
               level,
               lesson_name,
               example_sentence,
               course_id
        FROM spelling_words
        WHERE LOWER(word) = LOWER(:word)
          AND course_id = :cid
        """,
        {"word": word, "cid": course_id},
    )

    if isinstance(rows, dict) or not rows:
        return []

    return [_row_to_mapping(r) for r in rows]


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
    rows = fetch_all(
        """
        INSERT INTO spelling_words
            (word, pattern, pattern_code, level, lesson_name, example_sentence, course_id)
        VALUES
            (:word, :pattern, :pattern_code, :level, :lesson_name, :example_sentence, :course_id)
        RETURNING word_id;
        """,
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

    mapping = _row_to_mapping(rows[0])
    return mapping.get("word_id")


def get_words_for_course(course_id: int) -> List[Dict[str, Any]]:
    rows = fetch_all(
        """
        SELECT word_id,
               word,
               pattern,
               pattern_code,
               level,
               lesson_name,
               example_sentence
        FROM spelling_words
        WHERE course_id = :cid
        ORDER BY level, pattern_code, word
        """,
        {"cid": course_id},
    )

    if isinstance(rows, dict) or not rows:
        return []

    words = []
    for r in rows:
        m = getattr(r, "_mapping", r)
        words.append(
            {
                "word_id": m["word_id"],
                "word": m["word"],
                "pattern": m.get("pattern"),
                "pattern_code": m.get("pattern_code"),
                "level": m.get("level"),
                "lesson_name": m.get("lesson_name"),
                "example_sentence": m.get("example_sentence"),
            }
        )
    return words
