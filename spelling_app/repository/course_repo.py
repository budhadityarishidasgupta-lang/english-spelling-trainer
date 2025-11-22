from shared.db import fetch_all, execute


def get_all_courses():
    sql = """
    SELECT course_id, title, description
    FROM courses
    ORDER BY course_id ASC;
    """

    return fetch_all(sql)


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
