# --------------------------------------------------------
# FIX PYTHON PATH (MUST RUN BEFORE ANY OTHER IMPORTS)
# --------------------------------------------------------
import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# --------------------------------------------------------
# IMPORTS
# --------------------------------------------------------
from dotenv import load_dotenv
import streamlit as st
import sqlalchemy

from shared.db import engine, fetch_all
from spelling_app.repository.spelling_lesson_repo import (
    update_lesson_name,
    delete_lesson,
)
from spelling_app.repository.student_pending_repo import (
    list_pending_registrations,
    approve_pending_registration,
    delete_pending_registration,
)
from spelling_app.repository.student_repo import (
    list_registered_students,
    get_student_courses,
    assign_course_to_student,
    remove_course_from_student,
    update_student_status,
    update_student_class_name,
)
from spellings_admin_clean.upload_manager_clean import process_spelling_csv
from spellings_admin_clean.course_manager_clean import (
    list_courses,
    create_course_admin,
)

# --------------------------------------------------------
# STREAMLIT CONFIG (MUST BE FIRST STREAMLIT CALL)
# --------------------------------------------------------
st.set_page_config(
    page_title="Spelling Admin Console (Clean Build)",
    layout="wide",
)

# --------------------------------------------------------
# ENV + DEBUG
# --------------------------------------------------------
load_dotenv()

st.write("DEBUG DATABASE_URL:", os.getenv("DATABASE_URL"))

with engine.connect() as conn:
    schema_path = conn.execute(sqlalchemy.text("SHOW search_path;")).scalar()

st.write("DEBUG: Active search_path:", schema_path)


# --------------------------------------------------------
# HELPER UI FUNCTIONS
# --------------------------------------------------------
def ui_get_lessons_for_course(course_id: int):
    rows = fetch_all(
        """
        SELECT lesson_id, lesson_name
        FROM spelling_lessons
        WHERE course_id = :cid
        ORDER BY lesson_id ASC;
        """,
        {"cid": course_id},
    )

    if isinstance(rows, dict) or not rows:
        return []

    return [dict(getattr(r, "_mapping", r)) for r in rows]


def ui_get_lesson_words(lesson_id: int):
    rows = fetch_all(
        """
        SELECT w.word_id, w.word, w.pattern_code
        FROM spelling_words w
        JOIN spelling_lesson_words lw ON lw.word_id = w.word_id
        WHERE lw.lesson_id = :lid
        ORDER BY w.word_id ASC;
        """,
        {"lid": lesson_id},
    )

    if isinstance(rows, dict) or not rows:
        return []

    return [dict(getattr(r, "_mapping", r)) for r in rows]


def ui_get_all_courses():
    courses = list_courses()
    if isinstance(courses, dict):
        return []
    return courses or []


# --------------------------------------------------------
# COURSE SECTION
# --------------------------------------------------------
def render_course_section():
    st.subheader("Courses")

    courses = list_courses()
    if isinstance(courses, dict):
        st.error("Error loading courses.")
        courses = []

    course_options = {
        f"{c['course_id']}: {c['course_name']}": c["course_id"] for c in courses
    }

    selected_course_label = st.selectbox(
        "Select course",
        options=list(course_options.keys()) if course_options else ["No courses yet"],
    )

    selected_course_id = None
    if course_options:
        selected_course_id = course_options.get(selected_course_label)

    with st.expander("Create new course"):
        new_title = st.text_input("Course title", key="new_course_title")
        new_desc = st.text_area("Course description", key="new_course_desc")
        if st.button("Create course"):
            if not new_title.strip():
                st.error("Title is required.")
            else:
                cid = create_course_admin(new_title.strip(), new_desc.strip() or None)
                if isinstance(cid, dict) and "error" in cid:
                    st.error(f"Error creating course: {cid['error']}")
                elif cid:
                    st.success(f"Created course with ID {cid}")
                else:
                    st.error("Error creating course.")
                st.experimental_rerun()

    return selected_course_id


# --------------------------------------------------------
# UPLOAD SECTION
# --------------------------------------------------------
def render_upload_section(course_id: int):
    st.subheader("Upload CSV for course words & lessons")

    uploaded = st.file_uploader(
        "Upload CSV (columns: word, pattern_code, lesson_name OR pattern_text + difficulty)",
        type=["csv"],
        key="spelling_csv_uploader",
    )

    if uploaded is not None:
        import pandas as pd

        try:
            df = pd.read_csv(uploaded)
        except Exception as e:
            st.error(f"Error reading CSV: {e}")
            return

        if df.empty:
            st.warning("CSV appears empty or invalid.")
            return

        st.write("Preview:")
        st.dataframe(df.head())

        if st.button("Process CSV for this course"):
            summary = process_spelling_csv(df=df, course_id=course_id)
            if isinstance(summary, dict) and summary.get("error"):
                st.error(summary["error"])
                st.write(summary)
            else:
                st.success("Upload processed.")
                st.write(summary)
            st.experimental_rerun()


# --------------------------------------------------------
# WORD + LESSON OVERVIEW
# --------------------------------------------------------
def render_words_lessons_section(course_id: int):
    st.subheader("Words & Lessons Overview")

    lessons = ui_get_lessons_for_course(course_id)
    if not lessons:
        st.info("No lessons found yet. Upload a CSV.")
        return

    lesson_label_map = {
        f"{l['lesson_id']}: {l['lesson_name']}": l["lesson_id"] for l in lessons
    }

    selected_label = st.selectbox(
        "Select lesson",
        options=list(lesson_label_map.keys()),
    )

    lesson_id = lesson_label_map[selected_label]

    # -------- Lesson edit / delete --------
    st.markdown("### Edit or delete this lesson")

    current_name = selected_label.split(": ", 1)[1]
    new_lesson_name = st.text_input(
        "Lesson name",
        value=current_name,
        key="edit_lesson_name",
    )

    colA, colB = st.columns(2)

    with colA:
        if st.button("💾 Save lesson name", key="save_lesson_name"):
            update_lesson_name(lesson_id, new_lesson_name.strip())
            st.success("Lesson renamed.")
            st.experimental_rerun()

    with colB:
        if st.button("🗑 Delete lesson", key="delete_lesson_button"):
            delete_lesson(lesson_id)
            st.success("Lesson deleted.")
            st.experimental_rerun()

    # -------- Words in lesson --------
    words = ui_get_lesson_words(lesson_id)

    if not words:
        st.info("No words mapped to this lesson yet.")
        return

    st.write("Words in this lesson:")
    st.dataframe(words)


# --------------------------------------------------------
# STUDENT MANAGEMENT: PENDING REGISTRATIONS
# --------------------------------------------------------
def render_pending_registrations_section():
    st.subheader("Pending registrations")

    pending = list_pending_registrations()

    if isinstance(pending, dict):
        st.error("Error loading pending registrations.")
        return

    if not pending:
        st.info("No pending registrations.")
        return

    for row in pending:
        col1, col2, col3, col4 = st.columns([3, 4, 2, 2])

        with col1:
            st.write(row["student_name"])

        with col2:
            st.write(row["email"])

        with col3:
            approve_key = f"approve_{row['id']}"
            if st.button("✅ Approve", key=approve_key):
                result = approve_pending_registration(row["id"])
                if isinstance(result, dict) and result.get("error"):
                    st.error(result["error"])
                else:
                    st.success(
                        f"Approved {result.get('email')} "
                        f"(temp password: {result.get('default_password')})"
                    )
                st.experimental_rerun()

        with col4:
            reject_key = f"reject_{row['id']}"
            if st.button("🗑 Disregard", key=reject_key):
                delete_pending_registration(row["id"])
                st.success("Registration disregarded.")
                st.experimental_rerun()


# --------------------------------------------------------
# STUDENT MANAGEMENT: REGISTERED STUDENTS
# --------------------------------------------------------
def render_registered_students_section():
    st.subheader("Registered students")

    students = list_registered_students()
    if not students:
        st.info("No registered students found.")
        return

    all_courses = ui_get_all_courses()
    course_label_map = {
        f"{c['course_id']}: {c['course_name']}": c["course_id"] for c in all_courses
    }
    course_labels = list(course_label_map.keys())

    for student in students:
        st.markdown("---")
        col1, col2, col3 = st.columns([3, 3, 4])

        # Basic info
        with col1:
            st.write(f"**Name:** {student['name']}")
            st.write(f"**Email:** {student['email']}")
            st.write("**Password:** Learn123! (default for new users)")

        # Class name + status
        with col2:
            current_class = student.get("class_name") or ""
            new_class = st.text_input(
                "Class name",
                value=current_class,
                key=f"class_{student['user_id']}",
            )

            current_status = (student.get("status") or "ACTIVE").upper()
            new_status = st.selectbox(
                "Status",
                options=["ACTIVE", "ARCHIVED"],
                index=0 if current_status == "ACTIVE" else 1,
                key=f"status_{student['user_id']}",
            )

            if st.button("💾 Save profile", key=f"save_profile_{student['user_id']}"):
                update_student_class_name(student["user_id"], new_class.strip())
                update_student_status(student["user_id"], new_status)
                st.success("Student profile updated.")
                st.experimental_rerun()

        # Course assignment
        with col3:
            enrolled = get_student_courses(student["user_id"])
            enrolled_names = ", ".join([c["course_name"] for c in enrolled]) or "None"

            st.write(f"**Registered courses:** {enrolled_names}")

            selection = st.multiselect(
                "Select courses",
                options=course_labels,
                key=f"courses_select_{student['user_id']}",
            )
            selected_course_ids = [course_label_map[label] for label in selection]

            c1, c2 = st.columns(2)
            with c1:
                if st.button("➕ Assign", key=f"assign_{student['user_id']}"):
                    if not selected_course_ids:
                        st.warning("Select at least one course to assign.")
                    else:
                        for cid in selected_course_ids:
                            assign_course_to_student(student["user_id"], cid)
                        st.success("Courses assigned.")
                        st.experimental_rerun()
            with c2:
                if st.button("➖ De-register", key=f"deregister_{student['user_id']}"):
                    if not selected_course_ids:
                        st.warning("Select at least one course to de-register.")
                    else:
                        for cid in selected_course_ids:
                            remove_course_from_student(student["user_id"], cid)
                        st.success("Courses de-registered.")
                        st.experimental_rerun()


# --------------------------------------------------------
# MAIN
# --------------------------------------------------------
def main():
    st.title("Spelling Admin Console (Clean Build)")

    course_id = render_course_section()

    if not course_id:
        st.info("Create or select a course to continue.")
        return

    col1, col2 = st.columns([2, 2])

    with col1:
        render_upload_section(course_id)

    with col2:
        render_words_lessons_section(course_id)

    st.markdown("---")
    st.header("Student Management")

    render_pending_registrations_section()
    st.markdown("---")
    render_registered_students_section()


if __name__ == "__main__":
    main()
