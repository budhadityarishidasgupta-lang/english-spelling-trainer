import streamlit as st
from spelling_app.services.spelling_service import (
    load_lessons_for_course,
    get_lesson_progress,
)
from shared.auth import get_logged_in_user


def render_lesson_list(course_id: int, course_title: str):
    st.title(f"📘 {course_title}")
    st.subheader("Lessons")

    user = get_logged_in_user()
    if not user:
        st.error("You must be logged in.")
        return
    student_id = user["id"]

    lessons = load_lessons_for_course(course_id)

    if isinstance(lessons, dict) and "error" in lessons:
        st.error("Error loading lessons: " + str(lessons))
        return

    if not lessons:
        st.info("No lessons yet in this course.")
        return

    for lesson in lessons:
        lid = lesson["lesson_id"]
        title = lesson["title"]
        instructions = lesson.get("instructions", "")

        progress = get_lesson_progress(student_id, lid)

        with st.container():
            st.markdown(f"### {title}")
            if instructions:
                st.caption(instructions)

            # Progress badge
            if progress == 100:
                st.success("Completed")
            elif progress > 0:
                st.warning(f"In Progress ({progress}%)")
            else:
                st.info("Not Started")

            st.button(
                f"Start Lesson",
                key=f"start_{lid}",
                args=(lid, title),
                on_click=st.session_state.update,
            )
