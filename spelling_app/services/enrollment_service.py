from spelling_app.repository.enrollment_repo import (
    assign_spelling_course,
    get_courses_for_student,
    list_all_enrollments,
)


def enroll_student_in_course(student_id: int, course_id: int):
    """
    Wraps the DB insert for assigning a course.
    """
    return assign_spelling_course(student_id, course_id)


def get_student_spelling_courses(student_id: int):
    """
    Returns list of courses a student is enrolled in.
    """
    return get_courses_for_student(student_id)


def get_all_spelling_enrollments():
    """
    Returns all student-course assignments.
    Used for admin lists.
    """
    return list_all_enrollments()
