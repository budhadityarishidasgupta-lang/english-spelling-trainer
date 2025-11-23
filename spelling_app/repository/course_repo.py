from shared.db import fetch_all, execute


def get_all_courses():
    sql = """
    SELECT
        course_id,
        title,
        description,
        created_at
    FROM courses
    ORDER BY course_id ASC;
    """
    result = fetch_all(sql)

    # If fetch_all returns an error dict, just bubble it up
    if isinstance(result, dict):
        return result

    # Normal case: SQLAlchemy rows -> list[dict]
    return [dict(getattr(row, "_mapping", row)) for row in result]


def get_course(course_id):
    sql = """
    SELECT course_id, title, description, created_at
    FROM courses
    WHERE course_id = :id
    """

    result = fetch_all(sql, {"id": course_id})

    return [dict(row) for row in result]


def create_course(title, description=None, level=None):
    return execute(
        """
        INSERT INTO courses (title, description)
        VALUES (:title, :desc)
        """,
        {"title": title, "desc": description},
    )
