import os
import sys
import streamlit as st
import pandas as pd
from dotenv import load_dotenv
from passlib.hash import bcrypt as passlib_bcrypt

# =========================================================
#                PYTHONPATH FIX
# =========================================================
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

load_dotenv()

st.set_page_config(page_title="Spelling Admin Console", layout="wide")
st.title("🛠️ Spelling Admin Console")

# =========================================================
#                IMPORTS (CLEAN & CORRECTED)
# =========================================================

# Courses
from spelling_app.repository.course_repo import (
    get_all_spelling_courses,
)
from spellings_admin_clean.utils_clean import fetch_all_simple

# Students
from spelling_app.repository.student_repo import (
    approve_spelling_student,
    assign_courses_to_student,
    remove_courses_from_student,
    update_student_profile,
    get_pending_spelling_students,
    list_registered_spelling_students,
)

# Classroom
from spelling_app.repository.classroom_repo import (
    assign_students_to_class,
    create_classroom,
    get_students_in_class,
    list_classrooms,
)

# Upload Manager (fixed)
from spellings_admin_clean.word_manager_clean import process_uploaded_csv

# Utilities

# Lesson helpers
from spellings_admin_clean.word_manager_clean import (
    get_lesson_words,
    get_lessons_for_course,
)


def render_spelling_csv_upload():
    st.header("📤 Upload Spelling Word CSV")

    # --- Load course dropdown ---
    courses = fetch_all_simple(
        "SELECT course_id, course_name FROM spelling_courses ORDER BY course_name"
    )
    if not courses:
        st.error("No courses available. Create a course first.")
        return

    course_name_to_id = {c["course_name"]: c["course_id"] for c in courses}
    selected_course = st.selectbox("Select Course", list(course_name_to_id.keys()))
    selected_course_id = course_name_to_id[selected_course]

    st.info(f"Words will be uploaded into: **{selected_course}**")

    uploaded_file = st.file_uploader(
        "Upload CSV (columns: word, pattern, pattern_code, level, lesson_name)",
        type=["csv"],
    )

    if uploaded_file is None:
        return

    st.info("CSV Loaded Successfully")

    if st.button("Process Upload"):
        with st.spinner("Processing CSV…"):
            result = process_uploaded_csv(uploaded_file, selected_course_id)

        if result.get("error"):
            st.error(result["error"])
            return

        # SUCCESS OUTPUT
        st.success(f"Words uploaded to **{selected_course}**!")

        st.subheader("Upload Summary")
        st.write(f"**Words Added:** {result['words_added']}")
        st.write(f"**Lessons Created:** {result['lessons_created']}")

        if result["patterns"]:
            st.write("**Patterns Found:**")
            st.write(", ".join(result["patterns"]))

# =========================================================
#                SIDEBAR NAVIGATION
# =========================================================

menu = st.sidebar.radio(
    "Navigation",
    [
        "Dashboard",
        "Upload Words CSV",
        "Students",
        "Courses",
        "Classrooms",
    ]
)

# =========================================================
#                PAGE: DASHBOARD
# =========================================================

if menu == "Dashboard":
    st.subheader("📊 Overview")

    st.info("Use the sidebar to upload CSVs, manage students, courses, or classes.")

    st.write("### Existing Courses")
    courses = get_all_spelling_courses()
    if courses:
        st.table(pd.DataFrame(courses))
    else:
        st.write("No courses found.")


# =========================================================
#                PAGE: UPLOAD WORD CSV
# =========================================================

elif menu == "Upload Words CSV":
    render_spelling_csv_upload()


# =========================================================
#                PAGE: STUDENTS
# =========================================================

elif menu == "Students":
    st.subheader("👨‍🎓 Student Management")

    tabs = st.tabs(["Pending Approvals", "Registered Students"])

    # -------- Pending Students --------
    with tabs[0]:
        st.write("### Pending Students")
        pending = get_pending_spelling_students()
        if pending:
            df = pd.DataFrame(pending)
            st.dataframe(df)

            row = st.selectbox("Select a student to approve:", df.index)

            if st.button("Approve Student"):
                student = df.loc[row]
                approve_spelling_student(student["email"])
                st.success(f"Approved {student['email']}")
                st.experimental_rerun()

        else:
            st.info("No pending students.")

    # -------- Registered Students --------
    with tabs[1]:
        st.write("### Registered")
        students = list_registered_spelling_students()
        if students:
            df = pd.DataFrame(students)
            st.dataframe(df)

            st.write("### Update Courses for Student")
            student_id = st.number_input("Student ID", min_value=1, step=1)

            add_course_id = st.number_input("Add Course ID", min_value=1, step=1)
            if st.button("Assign Course"):
                assign_courses_to_student(student_id, [add_course_id])
                st.success("Course assigned.")

            remove_course_id = st.number_input("Remove Course ID", min_value=1, step=1)
            if st.button("Remove Course"):
                remove_courses_from_student(student_id, [remove_course_id])
                st.success("Course removed.")

        else:
            st.info("No registered students.")


# =========================================================
#                PAGE: COURSES
# =========================================================

elif menu == "Courses":
    st.subheader("📘 Course Overview")

    courses = get_all_spelling_courses()
    if courses:
        st.table(pd.DataFrame(courses))
    else:
        st.warning("No courses found.")

    st.write("### View Lessons for a Course")
    cid = st.number_input("Course ID", min_value=1, step=1)

    if st.button("Load Lessons"):
        lessons = get_lessons_for_course(cid)

        if lessons:
            st.success("Lessons found")
            st.table(pd.DataFrame(lessons))
        else:
            st.warning("No lessons exist for this course.")


# =========================================================
#                PAGE: CLASSROOMS
# =========================================================

elif menu == "Classrooms":
    st.subheader("🏫 Classroom Manager")

    st.write("### Create New Classroom")
    cname = st.text_input("Classroom Name")

    if st.button("Create Classroom"):
        create_classroom(cname)
        st.success(f"Created classroom: {cname}")

    st.write("### Existing Classrooms")
    classes = list_classrooms()
    st.table(pd.DataFrame(classes))

    st.write("### Assign Student to Classroom")
    class_id = st.number_input("Class ID", min_value=1, step=1)
    student_id = st.number_input("Student ID", min_value=1, step=1)

    if st.button("Assign Student"):
        assign_students_to_class(class_id, [student_id])
        st.success("Student assigned.")

    st.write("### View Students in a Class")
    cid = st.number_input("Class ID to view", min_value=1, step=1)

    if st.button("Load Class"):
        students = get_students_in_class(cid)
        st.table(pd.DataFrame(students))
