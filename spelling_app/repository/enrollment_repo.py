from shared.db import fetch_all


def assign_spelling_course(student_id: int, course_id: int):
    """
    Assign a spelling course to a student.
    Inserts student_id + course_id into spelling_enrollments.
    Unique constraint prevents duplicates.
    """
    sql = """
        INSERT INTO spelling_enrollments (student_id, course_id)
        VALUES (:student_id, :course_id)
        ON CONFLICT (student_id, course_id) DO NOTHING;
    """
    return fetch_all(sql, {"student_id": student_id, "course_id": course_id})


def get_courses_for_student(student_id: int):
    """
    Returns all assigned spelling courses for a student.
    """
    sql = """
        SELECT e.course_id, c.title, c.description, e.assigned_on
        FROM spelling_enrollments e
        JOIN courses c ON c.course_id = e.course_id
        WHERE e.student_id = :student_id
        ORDER BY e.assigned_on DESC;
    """
    result = fetch_all(sql, {"student_id": student_id})
    if isinstance(result, dict):
        return result
    return [dict(r._mapping) for r in result]


def list_all_enrollments():
    """
    Returns all spelling enrollments with student + course metadata.
    """
    sql = """
        SELECT
            e.id,
            e.student_id,
            u.name AS student_name,
            e.course_id,
            c.title AS course_title,
            e.assigned_on
        FROM spelling_enrollments e
        JOIN users u ON u.id = e.student_id
        JOIN courses c ON c.course_id = e.course_id
        ORDER BY e.assigned_on DESC;
    """
    result = fetch_all(sql)
    if isinstance(result, dict):
        return result
    return [dict(r._mapping) for r in result]
