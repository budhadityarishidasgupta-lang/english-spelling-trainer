import re
from shared.db import fetch_all, execute


def consolidate_legacy_lessons_into_patterns(course_id: int) -> dict:
    """
    Consolidate legacy lessons (L*-*) into pattern lessons.

    Returns stats for auditability.
    """

    stats = {
        "legacy_lessons_scanned": 0,
        "pattern_lessons_created": 0,
        "mappings_copied": 0,
    }

    # 1. Find legacy lessons
    legacy_lessons = fetch_all(
        """
        SELECT lesson_id, lesson_name
        FROM spelling_lessons
        WHERE course_id = :cid
          AND lesson_name ~ '^L[0-9]+-'
        """,
        {"cid": course_id},
    )

    for row in legacy_lessons:
        stats["legacy_lessons_scanned"] += 1
        legacy_lesson_id = row["lesson_id"]
        legacy_name = row["lesson_name"]

        # 2. Extract pattern text
        if "–" in legacy_name:
            raw = legacy_name.split("–", 1)[1]
        elif "-" in legacy_name:
            raw = legacy_name.split("-", 1)[1]
        else:
            continue

        pattern = raw.strip().lower()
        if pattern.endswith("patterns"):
            pattern = pattern[:-1]

        # 3. Ensure pattern lesson exists
        pattern_rows = fetch_all(
            """
            SELECT lesson_id
            FROM spelling_lessons
            WHERE course_id = :cid AND lesson_name = :lname
            """,
            {"cid": course_id, "lname": pattern},
        )

        if pattern_rows:
            pattern_lesson_id = pattern_rows[0]["lesson_id"]
        else:
            execute(
                """
                INSERT INTO spelling_lessons (course_id, lesson_name)
                VALUES (:cid, :lname)
                """,
                {"cid": course_id, "lname": pattern},
            )
            stats["pattern_lessons_created"] += 1

            pattern_lesson_id = fetch_all(
                """
                SELECT lesson_id
                FROM spelling_lessons
                WHERE course_id = :cid AND lesson_name = :lname
                """,
                {"cid": course_id, "lname": pattern},
            )[0]["lesson_id"]

        # 4. Copy lesson-word mappings
        copied = execute(
            """
            INSERT INTO spelling_lesson_words (lesson_id, word_id, position)
            SELECT :target_lesson, word_id, position
            FROM spelling_lesson_words
            WHERE lesson_id = :legacy_lesson
            ON CONFLICT DO NOTHING
            """,
            {
                "target_lesson": pattern_lesson_id,
                "legacy_lesson": legacy_lesson_id,
            },
        )

        if copied:
            stats["mappings_copied"] += copied.rowcount or 0

    return stats
