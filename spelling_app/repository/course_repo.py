from shared.db import fetch_all, execute


def get_all_courses():
    sql = """
    SELECT
        course_id,
        title,
        description,
        level,
        is_active,
        created_at
    FROM courses
    ORDER BY course_id ASC;
    """

    result = fetch_all(sql)

    return [dict(row) for row in result]


def get_course(course_id):
    sql = """
    SELECT course_id, title, description, level
    FROM courses
    WHERE course_id = :id
    """

    return fetch_all(sql, {"id": course_id})


def create_course(title, description=None, level=None):
    return execute(
        """
        INSERT INTO courses (title, description, level)
        VALUES (:title, :desc, :level)
        """,
        {"title": title, "desc": description, "level": level},
    )
