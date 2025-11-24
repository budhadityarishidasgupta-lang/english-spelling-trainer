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
    """
    Insert a new spelling course into the courses table.
    course_type is always set to 'spelling'.
    """
    sql = """
        INSERT INTO courses (title, description, course_type)
        VALUES (:title, :description, 'spelling')
        RETURNING course_id;
    """
    result = fetch_all(sql, {"title": title, "description": description})

    # Normal case: return the created ID
    if isinstance(result, list) and len(result) > 0:
        row = result[0]
        return row._mapping["course_id"]

    # Bubble up error dicts
    return result


def get_all_spelling_courses():
    query = """
        SELECT course_id, title, description, created_at
        FROM courses
        WHERE course_type = 'spelling'
        ORDER BY course_id ASC;
    """
    return fetch_all(query)


def update_spelling_course(course_id, title=None, description=None, difficulty=None, course_type=None):
    set_clauses = []
    params = {"course_id": course_id}

    if title is not None:
        set_clauses.append("title = :title")
        params["title"] = title

    if description is not None:
        set_clauses.append("description = :description")
        params["description"] = description

    if difficulty is not None:
        set_clauses.append("difficulty = :difficulty")
        params["difficulty"] = difficulty

    if course_type is not None:
        set_clauses.append("course_type = :course_type")
        params["course_type"] = course_type

    if not set_clauses:
        return {"error": "No updatable fields provided"}

    sql = f"""
        UPDATE courses
        SET {", ".join(set_clauses)}
        WHERE course_id = :course_id
    """
    return execute(sql, params)
