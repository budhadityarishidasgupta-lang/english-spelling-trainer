from shared.db import fetch_all, execute


def get_all_courses():
    return fetch_all(
        """
        SELECT course_id, title, description
        FROM courses
        ORDER BY course_id ASC;
        """,
    )


def get_course(course_id):
    return fetch_all(
        "SELECT * FROM courses WHERE course_id = :id",
        {"id": course_id}
    )


def create_course(title, description=None, level=None):
    return execute(
        """
        INSERT INTO courses (title, description, level)
        VALUES (:title, :desc, :level)
        """,
        {"title": title, "desc": description, "level": level},
    )
