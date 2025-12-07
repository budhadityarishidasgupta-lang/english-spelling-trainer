# spelling_app/repository/course_repo.py

from shared.db import fetch_all, execute


def get_all_courses():
    rows = fetch_all(
        """
        SELECT course_id, course_name
        FROM spelling_courses
        ORDER BY course_name
        """
    )

    if isinstance(rows, dict):
        return []

    result = []
    for r in rows:
        m = getattr(r, "_mapping", r)
        result.append({"course_id": m["course_id"], "course_name": m["course_name"]})

    return result


def get_all_spelling_courses():
    """
    Returns all spelling courses from spelling_courses table.
    """
    sql = """
        SELECT
            course_id,
            course_name,
            description
        FROM spelling_courses
        ORDER BY course_id ASC;
    """
    rows = fetch_all(sql)

    if isinstance(rows, dict):
        return []

    result = []
    for r in rows:
        if hasattr(r, "_mapping"):
            result.append(dict(r._mapping))
        else:
            result.append(dict(r))

    return result


def get_spelling_course_by_id(course_id: int):
    sql = """
        SELECT
            course_id,
            course_name,
            description
        FROM spelling_courses
        WHERE course_id = :course_id
        LIMIT 1;
    """
    rows = fetch_all(sql, {"course_id": course_id})

    if isinstance(rows, dict):
        return None

    if not rows:
        return None

    row = rows[0]
    return dict(row._mapping) if hasattr(row, "_mapping") else dict(row)


def create_spelling_course(course_name: str, description: str | None = None):
    """
    Insert a new spelling course.
    """
    sql = """
        INSERT INTO spelling_courses (course_name, description)
        VALUES (:course_name, :description)
        RETURNING course_id;
    """

    rows = fetch_all(
        sql,
        {"course_name": course_name, "description": description},
    )

    if isinstance(rows, dict):
        return None

    if not rows:
        return None

    row = rows[0]

    if hasattr(row, "_mapping"):
        return row._mapping.get("course_id")

    if isinstance(row, dict):
        return row.get("course_id")

    try:
        return row[0]
    except:
        return None


def update_spelling_course(course_id: int, course_name: str | None = None, description: str | None = None):
    """
    Update a course.
    """
    fields = []
    params = {"course_id": course_id}

    if course_name is not None:
        fields.append("course_name = :course_name")
        params["course_name"] = course_name

    if description is not None:
        fields.append("description = :description")
        params["description"] = description

    if not fields:
        return {"error": "No fields to update"}

    sql = f"""
        UPDATE spelling_courses
        SET {', '.join(fields)}
        WHERE course_id = :course_id;
    """

    return execute(sql, params)
