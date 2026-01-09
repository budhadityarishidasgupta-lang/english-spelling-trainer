import streamlit as st
import re
from sqlalchemy import text

from shared.db import engine, fetch_all


TEXT_COLUMNS = {
    "word",
    "pattern",
    "lesson_name",
    "level",
    "example_sentence",
    "hint",
}

COLUMN_MAP = {
    "word": "word",
    "pattern": "pattern",
    "pattern_code": "pattern_code",
    "level": "level",
    "difficulty": "level",
    "lesson_name": "lesson_name",
    "example_sentence": "example_sentence",
    "hint": "hint",
}


def parse_word_selector(selector: str) -> dict:
    if selector is None:
        raise ValueError("word_selector is required")

    selector = selector.strip()
    if not selector:
        raise ValueError("word_selector is required")

    pairs = [chunk for chunk in selector.split(";") if chunk.strip()]
    filters: dict[str, str] = {}

    for pair in pairs:
        if "=" not in pair:
            raise ValueError(f"Invalid selector segment: '{pair}'")
        key, value = pair.split("=", 1)
        key = key.strip().lower()
        value = value.strip()
        if not key:
            raise ValueError("Selector key is required")
        if not value:
            raise ValueError(f"Selector value is required for '{key}'")
        filters[key] = value

    if not filters:
        raise ValueError("word_selector is required")

    return filters


def _safe_int(value: str) -> int | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    if not cleaned:
        return None
    if re.match(r"^-?\d+$", cleaned):
        return int(cleaned)
    return None


def get_matching_words(course_id: int, selector: str) -> list[int]:
    filters = parse_word_selector(selector)

    conditions = ["course_id = :course_id"]
    params: dict[str, object] = {"course_id": course_id}

    for idx, (key, raw_value) in enumerate(filters.items()):
        if key not in COLUMN_MAP:
            raise ValueError(f"Unsupported selector key: '{key}'")

        column = COLUMN_MAP[key]
        param_key = f"value_{idx}"

        if column in TEXT_COLUMNS:
            conditions.append(f"LOWER({column}) = LOWER(:{param_key})")
            params[param_key] = str(raw_value)
        else:
            int_value = _safe_int(raw_value)
            if int_value is None:
                raise ValueError(f"Selector '{key}' requires a numeric value")
            conditions.append(f"{column} = :{param_key}")
            params[param_key] = int_value

    where_clause = " AND ".join(conditions)

    rows = fetch_all(
        f"""
        SELECT word_id
        FROM spelling_words
        WHERE {where_clause}
        ORDER BY word_id
        """,
        params,
    )

    word_ids: list[int] = []
    for row in rows or []:
        if hasattr(row, "_mapping"):
            word_ids.append(row._mapping["word_id"])
        elif isinstance(row, dict):
            word_ids.append(row["word_id"])
        elif isinstance(row, (list, tuple)):
            word_ids.append(row[0])

    return word_ids

def _extract_lesson_id(row) -> int | None:
    if row is None:
        return None
    if hasattr(row, "_mapping"):
        return row._mapping.get("lesson_id")
    if isinstance(row, dict):
        return row.get("lesson_id")
    try:
        return row["lesson_id"]
    except (TypeError, KeyError):
        return None


def upsert_lesson(
    course_id: int,
    lesson_name: str,
    description: str | None,
    difficulty: int | None,
) -> int:
    if course_id is None:
        raise ValueError("course_id is required")

    lesson_name = (lesson_name or "").strip()
    display_name = lesson_name
    if not lesson_name:
        raise ValueError("lesson_name is required")
    existing = fetch_all(
        """
        SELECT lesson_id
        FROM spelling_lessons
        WHERE course_id = :course_id
          AND lesson_name = :lesson_name
        LIMIT 1;
        """,
        {"course_id": course_id, "lesson_name": lesson_name},
    )

    if existing:
        existing_row = existing[0]._mapping if hasattr(existing[0], "_mapping") else existing[0]
        lesson_id = _extract_lesson_id(existing_row)

        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    UPDATE spelling_lessons
                    SET lesson_name = :lesson_name
                    WHERE course_id = :course_id
                      AND lesson_name = :lesson_name
                    """
                ),
                {
                    "lesson_name": lesson_name,
                    "course_id": course_id,
                },
            )

            result = conn.execute(
                text(
                    """
                    SELECT lesson_id
                    FROM spelling_lessons
                    WHERE course_id = :course_id
                      AND lesson_name = :lesson_name
                    """
                ),
                {"course_id": course_id, "lesson_name": lesson_name},
            )
            lesson_id = _extract_lesson_id(result.fetchone())
    else:
        with engine.begin() as conn:
            result = conn.execute(
                text(
                    """
                    INSERT INTO spelling_lessons (course_id, lesson_name, display_name)
                    VALUES (:course_id, :lesson_name, :display_name)
                    RETURNING lesson_id
                    """
                ),
                {
                    "course_id": course_id,
                    "lesson_name": lesson_name,
                    "display_name": display_name,
                },
            )
            lesson_id = _extract_lesson_id(result.fetchone())

    if lesson_id is None:
        raise RuntimeError(
            f"Lesson upsert failed for course_id={course_id}, lesson_name={lesson_name}"
        )

    return lesson_id


def rebuild_lesson_mappings(lesson_id: int, word_ids: list[int]):
    if not word_ids:
        raise ValueError("word_selector matched zero words")

    unique_word_ids = sorted(set(word_ids))

    with engine.begin() as connection:
        connection.execute(
            text(
                """
                DELETE FROM spelling_lesson_items
                WHERE lesson_id = :lesson_id;
                """
            ),
            {"lesson_id": lesson_id},
        )

        payload = [
            {
                "lesson_id": lesson_id,
                "word_id": word_id,
                "sort_order": index + 1,
            }
            for index, word_id in enumerate(unique_word_ids)
        ]

        connection.execute(
            text(
                """
                INSERT INTO spelling_lesson_items (lesson_id, word_id, sort_order)
                VALUES (:lesson_id, :word_id, :sort_order)
                """
            ),
            payload,
        )
