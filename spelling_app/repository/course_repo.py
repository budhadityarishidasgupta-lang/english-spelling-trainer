from shared.db import fetch_all, execute


def get_all_courses():
    sql = """
    SELECT
        course_id,
        title,
        description,
        is_active,
        created_at
    FROM courses
    ORDER BY course_id ASC;
    """

    result = fetch_all(sql)

    # DEBUG: print the first DB row
    for row in result:
        print("DEBUG COURSE ROW:", row, type(row))
        return []  # stop here so we see debug output

    return [dict(row) for row in result]


def get_course(course_id):
    sql = """
    SELECT course_id, title, description, created_at
    FROM courses
    WHERE course_id = :id
    """

    return fetch_all(sql, {"id": course_id})


def create_course(title, description=None, level=None):
    return execute(
        """
        INSERT INTO courses (title, description)
        VALUES (:title, :desc)
        """,
        {"title": title, "desc": description},
    )
