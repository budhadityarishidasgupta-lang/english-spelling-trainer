import re
from sqlalchemy import text

from shared.db import engine, fetch_all


TEXT_COLUMNS = {
    "word",
    "pattern",
    "lesson_name",
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
        mapping = row._mapping if hasattr(row, "_mapping") else row
        word_id = mapping.get("word_id") if isinstance(mapping, dict) else None
        if word_id is not None:
            word_ids.append(word_id)

    return word_ids


def _extract_lesson_id(rows, action: str) -> int:
    row = (
        rows[0]._mapping
        if rows and hasattr(rows[0], "_mapping")
        else (rows[0] if rows else None)
    )
    lesson_id = row.get("lesson_id") if isinstance(row, dict) else None
    if lesson_id is None:
        raise RuntimeError(f"Failed to {action} lesson")
    return lesson_id


def upsert_lesson(
    course_id: int,
    lesson_code: str,
    lesson_name: str,
    description: str | None,
    difficulty: int | None,
) -> int:
    if course_id is None:
        raise ValueError("course_id is required")
    if lesson_code is None or not str(lesson_code).strip():
        raise ValueError("lesson_code is required")

    lesson_code = str(lesson_code).strip()
    lesson_name = (lesson_name or "").strip()
    description = description.strip() if isinstance(description, str) else description

    existing = fetch_all(
        """
        SELECT lesson_id
        FROM spelling_lessons
        WHERE course_id = :course_id
          AND lesson_code = :lesson_code
        LIMIT 1;
        """,
        {"course_id": course_id, "lesson_code": lesson_code},
    )

    if existing:
        lesson_id = _extract_lesson_id(existing, "read")

        updated = fetch_all(
            """
            UPDATE spelling_lessons
            SET lesson_name = :lesson_name,
                description = :description,
                difficulty = :difficulty
            WHERE lesson_id = :lesson_id
            RETURNING lesson_id;
            """,
            {
                "lesson_name": lesson_name,
                "description": description,
                "difficulty": difficulty,
                "lesson_id": lesson_id,
            },
        )

        return _extract_lesson_id(updated, "update")

    inserted = fetch_all(
        """
        INSERT INTO spelling_lessons (
            course_id,
            lesson_code,
            lesson_name,
            description,
            difficulty
        )
        VALUES (
            :course_id,
            :lesson_code,
            :lesson_name,
            :description,
            :difficulty
        )
        RETURNING lesson_id;
        """,
        {
            "course_id": course_id,
            "lesson_code": lesson_code,
            "lesson_name": lesson_name,
            "description": description,
            "difficulty": difficulty,
        },
    )

    return _extract_lesson_id(inserted, "insert")


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
