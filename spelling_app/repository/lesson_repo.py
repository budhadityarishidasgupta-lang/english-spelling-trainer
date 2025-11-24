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


def update_spelling_lesson(lesson_id, title=None, description=None, is_active=None):
    set_clauses = []
    params = {"lesson_id": lesson_id}

    if title is not None:
        set_clauses.append("title = :title")
        params["title"] = title

    if description is not None:
        set_clauses.append("instructions = :instructions")
        params["instructions"] = description

    if is_active is not None:
        set_clauses.append("is_active = :is_active")
        params["is_active"] = is_active

    if not set_clauses:
        return {"error": "No fields to update"}

    sql = f"""
        UPDATE lessons
        SET {", ".join(set_clauses)}
        WHERE id = :lesson_id AND lesson_type = 'spelling'
    """
    return execute(sql, params)
