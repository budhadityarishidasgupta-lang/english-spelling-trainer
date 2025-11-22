from shared.db import fetch_all, execute


def get_lessons(course_id=None):
    if course_id is not None:
        return fetch_all(
            """
            SELECT lesson_id, course_id, title, instructions, sort_order
            FROM lessons
            WHERE course_id = :cid
            ORDER BY sort_order ASC
            """,
            {"cid": course_id},
        )
    return fetch_all(
        """
        SELECT lesson_id, course_id, title, instructions, sort_order
        FROM lessons
        ORDER BY sort_order ASC
        """,
    )


def create_lesson(course_id, title, instructions=None, sort_order=None):
    return execute(
        """
        INSERT INTO lessons (course_id, title, instructions, sort_order)
        VALUES (:cid, :title, :instr, :sort)
        """,
        {
            "cid": course_id,
            "title": title,
            "instr": instructions,
            "sort": sort_order,
        }
    )
