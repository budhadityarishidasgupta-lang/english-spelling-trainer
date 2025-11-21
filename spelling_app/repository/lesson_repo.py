from shared.db import fetch_all, execute


def get_lessons(course_id):
    return fetch_all(
        """
        SELECT * FROM lessons
        WHERE sp_course_id = :cid
        ORDER BY sort_order NULLS LAST, sp_lesson_id
        """,
        {"cid": course_id}
    )


def create_lesson(course_id, title, instructions=None, sort_order=None):
    return execute(
        """
        INSERT INTO lessons (sp_course_id, title, instructions, sort_order)
        VALUES (:cid, :title, :instr, :sort)
        """,
        {
            "cid": course_id,
            "title": title,
            "instr": instructions,
            "sort": sort_order,
        }
    )
