import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from passlib.hash import bcrypt as passlib_bcrypt

load_dotenv()

from spelling_app.repository.course_repo import get_all_spelling_courses
from spelling_app.repository.student_repo import (
    assign_courses_to_student,
    approve_spelling_student,
    get_pending_spelling_students,
    get_student_courses,
    list_registered_spelling_students,
    remove_courses_from_student,
    update_student_profile,
)
from Spellings_Admin_Clean.upload_manager_clean import process_spelling_csv
from Spellings_Admin_Clean.utils_clean import read_csv_to_df, show_upload_summary
from Spellings_Admin_Clean.word_manager_clean import (
    get_lesson_words,
    get_lessons_for_course,
)
from shared.db import fetch_all, engine


DEFAULT_PASSWORD = "Learn123!"


def ui_get_all_courses():
    courses = get_all_spelling_courses() or []
    normalized = []
    for course in courses:
        course_id = course.get("course_id")
        name = course.get("course_name") or course.get("title") or f"Course {course_id}"
        normalized.append({"course_id": course_id, "course_name": name})
    return normalized


def generate_default_password_hash() -> str:
    return passlib_bcrypt.hash(DEFAULT_PASSWORD)


def render_pending_registration_section():
    st.subheader("Pending registrations")

    pending_students = get_pending_spelling_students()
    if not pending_students:
        st.info("No pending student registrations.")
        return

    header_cols = st.columns([3, 3, 3, 2])
    header_cols[0].write("**Name**")
    header_cols[1].write("**Email**")
    header_cols[2].write("**Created at**")
    header_cols[3].write(" ")

    for student in pending_students:
        cols = st.columns([3, 3, 3, 2])
        cols[0].write(student.get("student_name", "-"))
        cols[1].write(student.get("email", "-"))
        cols[2].write(student.get("created_at", "-"))
        pending_id = student.get("pending_id")
        if cols[3].button("Approve", key=f"approve_{pending_id}"):
            password_hash = generate_default_password_hash()
            approve_spelling_student(pending_id, password_hash)
            st.success(f"Approved {student.get('student_name')} with default password.")
            st.experimental_rerun()


def render_words_lessons_section(course_id: int):
    st.subheader("Words & Lessons Overview")

    lessons = get_lessons_for_course(course_id)
    if not lessons:
        st.info("No lessons found yet. Upload a CSV to create lessons and words.")
        return

    lesson_label_map = {
        f"{lesson['lesson_id']}: {lesson['lesson_name']}": lesson["lesson_id"]
        for lesson in lessons
    }

    selected_lesson_label = st.selectbox(
        "Select lesson",
        options=list(lesson_label_map.keys()),
    )
    lesson_id = lesson_label_map[selected_lesson_label]

    lesson_words = get_lesson_words(course_id=course_id, lesson_id=lesson_id)
    if not lesson_words:
        st.info("No words mapped to this lesson yet.")
    else:
        st.dataframe(lesson_words)


def render_upload_section(course_id: int):
    st.subheader("Upload CSV for course words & lessons")

    uploaded = st.file_uploader(
        "Upload CSV (columns: word, pattern_code, lesson_name)",
        type=["csv"],
        key="spelling_csv_uploader",
    )

    if uploaded is not None:
        df = read_csv_to_df(uploaded)
        if df.empty:
            st.warning("CSV appears to be empty or invalid.")
            return

        st.write("Preview of uploaded CSV:")
        st.dataframe(df.head())

        if st.button("Process CSV for this course"):
            summary = process_spelling_csv(df=df, course_id=course_id)
            show_upload_summary(summary)


def render_registered_students_section(all_courses):
    st.subheader("Registered students")

    students = list_registered_spelling_students()
    if not students:
        st.info("No registered spelling students yet.")
        return

    df = pd.DataFrame(students)
    if df.empty:
        st.info("No registered spelling students yet.")
        return

    df["registered_courses"] = df["registered_courses"].fillna("")
    df = df[["user_id", "name", "email", "class_name", "status", "registered_courses"]]
    df.set_index("user_id", inplace=True)

    original_df = df.copy(deep=True)
    df_display = df.copy(deep=True)
    df_display["email"] = df_display["email"].apply(
        lambda email: f"mailto:{email}" if isinstance(email, str) and email else ""
    )

    edited_df = st.data_editor(
        df_display,
        hide_index=True,
        num_rows="fixed",
        column_config={
            "name": st.column_config.TextColumn("Name", disabled=True),
            "email": st.column_config.LinkColumn("Email", disabled=True),
            "class_name": st.column_config.TextColumn("Class name"),
            "status": st.column_config.SelectboxColumn(
                "Status", options=["ACTIVE", "ARCHIVED"], required=True
            ),
            "registered_courses": st.column_config.TextColumn(
                "Registered courses", disabled=True
            ),
        },
    )

    if st.button("💾 Save profile changes"):
        updates_applied = False
        for user_id, row in edited_df.iterrows():
            original_row = original_df.loc[user_id]
            new_class = row.get("class_name")
            new_status = row.get("status")
            if (
                original_row.get("class_name") != new_class
                or original_row.get("status") != new_status
            ):
                update_student_profile(
                    user_id=int(user_id),
                    class_name=new_class if new_class else None,
                    status=new_status,
                )
                updates_applied = True

        if updates_applied:
            st.success("Student profiles updated.")
            st.experimental_rerun()
        else:
            st.info("No changes detected.")

    render_course_assignment_panel(all_courses, students)


def render_course_assignment_panel(all_courses, students):
    st.subheader("Assign or remove courses for a student")

    student_options = {
        f"{s['name']} ({s['email']})": s["user_id"] for s in students if s.get("user_id")
    }

    if not student_options:
        st.info("No students available for course assignment.")
        return

    selected_student_label = st.selectbox(
        "Select student",
        options=list(student_options.keys()),
    )
    selected_user_id = student_options[selected_student_label]

    current_courses = get_student_courses(selected_user_id)
    current_course_names = ", ".join([c.get("course_name") or "" for c in current_courses])
    st.write(f"Current registered courses: {current_course_names or 'None'}")

    course_options = {c["course_name"]: c["course_id"] for c in all_courses}
    selected_courses = st.multiselect(
        "Select courses", options=list(course_options.keys())
    )
    selected_course_ids = [course_options[name] for name in selected_courses]

    assign_col, remove_col = st.columns(2)
    with assign_col:
        if st.button("➕ Assign selected courses") and selected_course_ids:
            assign_courses_to_student(selected_user_id, selected_course_ids)
            st.success("Courses assigned successfully.")
            st.experimental_rerun()
    with remove_col:
        if st.button("➖ Remove selected courses") and selected_course_ids:
            remove_courses_from_student(selected_user_id, selected_course_ids)
            st.success("Courses removed successfully.")
            st.experimental_rerun()


def main():
    st.set_page_config(
        page_title="Spelling Admin Console (Clean Build)",
        layout="wide",
    )

    st.title("Spelling Admin Console (Clean Build)")

    courses = ui_get_all_courses()
    if not courses:
        st.info("No spelling courses available. Please create one before proceeding.")
        return

    course_options = {c["course_name"]: c["course_id"] for c in courses}
    selected_course_name = st.selectbox(
        "Select course for CSV upload", options=list(course_options.keys())
    )
    selected_course_id = course_options[selected_course_name]

    col1, col2 = st.columns([2, 2])

    with col1:
        render_upload_section(selected_course_id)

    with col2:
        render_words_lessons_section(selected_course_id)

    st.divider()

    render_pending_registration_section()

    st.divider()

    render_registered_students_section(courses)


if __name__ == "__main__":
    main()
