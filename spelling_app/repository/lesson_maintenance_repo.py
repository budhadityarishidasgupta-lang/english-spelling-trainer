from shared.db import execute, fetch_all


def _row_to_dict(row):
    if row is None:
        return None
    if isinstance(row, dict):
        return row
    if hasattr(row, "_mapping"):
        return dict(row._mapping)
    try:
        return dict(row)
    except Exception:
        return None


def _rows_to_dicts(rows):
    if not rows or isinstance(rows, dict):
        return []
    out = []
    for r in rows:
        m = _row_to_dict(r)
        if m:
            out.append(m)
    return out


def _extract_pattern_name(lesson_name: str):
    if not lesson_name:
        return None

    for sep in [" – ", " –", "–", " - ", " -", "-"]:
        if sep in lesson_name:
            parts = lesson_name.split(sep, 1)
            if len(parts) > 1:
                return parts[1]
    return None


def _normalize_pattern_name(pattern_raw: str):
    if not pattern_raw:
        return None

    pattern = pattern_raw.strip()
    if pattern.lower().endswith("patterns"):
        pattern = pattern[: -len("patterns")] + "pattern"
    return pattern


def _get_or_create_pattern_lesson(course_id: int, lesson_name: str):
    existing = _rows_to_dicts(
        fetch_all(
            """
            SELECT lesson_id
            FROM spelling_lessons
            WHERE course_id = :cid
              AND LOWER(lesson_name) = LOWER(:lname)
            LIMIT 1;
            """,
            {"cid": course_id, "lname": lesson_name},
        )
    )

    if existing:
        return existing[0].get("lesson_id"), False

    created = _rows_to_dicts(
        fetch_all(
            """
            INSERT INTO spelling_lessons (course_id, lesson_name, display_name)
            VALUES (:cid, :lname, :display_name)
            RETURNING lesson_id;
            """,
            {"cid": course_id, "lname": lesson_name, "display_name": lesson_name},
        )
    )

    if created:
        return created[0].get("lesson_id"), True

    return None, False


def consolidate_legacy_lessons_into_patterns(course_id: int) -> dict:
    """
    Consolidate word mappings from legacy lessons (L4- prefixed) into
    their pattern lessons.
    """

    stats = {
        "course_id": course_id,
        "legacy_lessons_found": 0,
        "pattern_lessons_created": 0,
        "word_mappings_copied": 0,
        "processed": [],
    }

    legacy_lessons = _rows_to_dicts(
        fetch_all(
            """
            SELECT lesson_id, lesson_name
            FROM spelling_lessons
            WHERE course_id = :cid
              AND lesson_name LIKE 'L4-%';
            """,
            {"cid": course_id},
        )
    )

    stats["legacy_lessons_found"] = len(legacy_lessons)

    for lesson in legacy_lessons:
        legacy_lesson_id = lesson.get("lesson_id")
        lesson_name = lesson.get("lesson_name") or ""

        pattern_raw = _extract_pattern_name(lesson_name)
        pattern_name = _normalize_pattern_name(pattern_raw)

        if not pattern_name:
            continue

        target_lesson_id, created = _get_or_create_pattern_lesson(
            course_id, pattern_name
        )
        if not target_lesson_id:
            continue

        if created:
            stats["pattern_lessons_created"] += 1

        insert_result = execute(
            """
            INSERT INTO spelling_lesson_words (lesson_id, word_id, position)
            SELECT :target_lesson_id, word_id, position
            FROM spelling_lesson_words
            WHERE lesson_id = :legacy_lesson_id
            ON CONFLICT (lesson_id, word_id) DO NOTHING;
            """,
            {
                "target_lesson_id": target_lesson_id,
                "legacy_lesson_id": legacy_lesson_id,
            },
        )

        copied = 0
        if isinstance(insert_result, dict):
            copied = insert_result.get("rows_affected") or 0

        stats["word_mappings_copied"] += copied
        stats["processed"].append(
            {
                "legacy_lesson_id": legacy_lesson_id,
                "legacy_lesson_name": lesson_name,
                "pattern_lesson_id": target_lesson_id,
                "pattern_lesson_name": pattern_name,
                "copied": copied,
            }
        )

    return stats
