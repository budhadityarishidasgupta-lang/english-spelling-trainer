# spelling_app/repository/course_repo.py

from shared.db import fetch_all, execute


def get_all_spelling_courses():
    """
    Returns all spelling courses from spelling_courses table.
    Always returns a list of dicts or an error dict.
    """
    sql = """
        SELECT
            course_id,
            title,
            description,
            created_at
        FROM spelling_courses
        ORDER BY course_id ASC;
    """

    rows = fetch_all(sql)

    if isinstance(rows, dict):
        return rows

    return [dict(getattr(r, "_mapping", r)) for r in rows] if rows else []


def get_spelling_course_by_id(course_id: int):
    """
    Returns a single spelling course row as a dict, or None.
    """

    sql = """
        SELECT
            course_id,
            title,
            description,
            created_at
        FROM spelling_courses
        WHERE course_id = :course_id
        LIMIT 1;
    """

    rows = fetch_all(sql, {"course_id": course_id})

    if isinstance(rows, dict):
        return rows

    if not rows:
        return None

    row = rows[0]
    if hasattr(row, "_mapping"):
        return dict(row._mapping)
    if isinstance(row, dict):
        return row
    try:
        return dict(row)
    except Exception:
        return None


def create_spelling_course(title: str, description: str | None = None):
    """
    Insert a new spelling course and return course_id.
    """

    sql = """
        INSERT INTO spelling_courses (title, description)
        VALUES (:title, :description)
        RETURNING course_id;
    """

    rows = fetch_all(sql, {"title": title, "description": description})

    if isinstance(rows, dict):
        return rows

    if rows:
        row = rows[0]
        if hasattr(row, "_mapping"):
            return row._mapping.get("course_id")
        if isinstance(row, dict):
            return row.get("course_id")
        try:
            return row[0]
        except Exception:
            return None

    return None


def update_spelling_course(course_id: int, title: str | None = None, description: str | None = None):
    """
    Update title/description for a spelling course.
    """

    fields = []
    params = {"course_id": course_id}

    if title is not None:
        fields.append("title = :title")
        params["title"] = title

    if description is not None:
        fields.append("description = :description")
        params["description"] = description

    if not fields:
        return {"error": "No fields to update"}

    sql = f"""
        UPDATE spelling_courses
        SET {", ".join(fields)}
        WHERE course_id = :course_id;
    """

    return execute(sql, params)
