from shared.db import fetch_all, execute


def get_all_courses():
    return fetch_all(
        """
        SELECT id, title, description 
        FROM courses 
        WHERE course_type = 'spelling'
        ORDER BY id ASC;
        """
    )


def get_course(course_id):
    return fetch_all(
        "SELECT * FROM courses WHERE sp_course_id = :id",
        {"id": course_id}
    )


def create_course(title, description=None, level=None):
    return execute(
        """
        INSERT INTO courses (title, description, level, course_type)
        VALUES (:title, :desc, :level, 'spelling')
        """,
        {"title": title, "desc": description, "level": level}
    )
