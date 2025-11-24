import streamlit as st
from spelling_app.services.enrollment_service import get_student_spelling_courses
from shared.auth import get_logged_in_user


def render_spelling_dashboard():
    st.title("📘 My Spelling Courses")

    user = get_logged_in_user()
    if not user:
        st.error("You must be logged in to access spelling courses.")
        return

    student_id = user["id"]

    courses = get_student_spelling_courses(student_id)

    if isinstance(courses, dict) and "error" in courses:
        st.error("Error loading your courses: " + str(courses))
        return

    if not courses:
        st.info("No spelling courses assigned yet.")
        return

    st.subheader("Assigned Courses")

    for c in courses:
        title = c["title"]
        desc = c["description"] or ""
        lesson_info = f"Course ID: {c['course_id']}"

        with st.container():
            st.markdown(f"### {title}")
            if desc:
                st.markdown(f"{desc}")
            st.caption(lesson_info)

            # When a course is clicked, store in session and redirect
            if st.button(f"Open {title}", key=f"open_{c['course_id']}"):
                st.session_state["selected_course_id"] = c["course_id"]
                st.session_state["selected_course_title"] = title
                st.session_state["page"] = "lesson_list"
