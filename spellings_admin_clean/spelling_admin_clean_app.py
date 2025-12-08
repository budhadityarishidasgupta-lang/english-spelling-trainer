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
from spellings_admin_clean.upload_manager_clean import process_spelling_csv

# Utilities

from shared.db import execute, fetch_all


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
            df = pd.read_csv(uploaded_file)
            result = process_spelling_csv(df, selected_course_id)

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


def render_classrooms_page():
    st.subheader("🏫 Classroom Manager")

    st.write("### Create New Classroom")
    cname = st.text_input("Classroom Name")

    if st.button("Create Classroom"):
        create_classroom(cname)
        st.success(f"Created classroom: {cname}")

    st.write("### Existing Classrooms")
    classes = list_classrooms()
    st.table(pd.DataFrame(classes))

    from spellings_admin_clean.utils_clean import fetch_all_simple

    classes = fetch_all_simple("SELECT class_id, class_name FROM classes ORDER BY class_name")
    class_map = {c["class_name"]: c["class_id"] for c in classes} if classes else {}

    st.write("### Assign Student to Classroom")
    if class_map:
        selected_class = st.selectbox("Select Classroom", list(class_map.keys()))
        class_id = class_map[selected_class]
    else:
        st.warning("No classrooms found.")
        class_id = None

    students = fetch_all_simple("SELECT user_id, name FROM users WHERE role='student' ORDER BY name")
    student_map = {s["name"]: s["user_id"] for s in students} if students else {}

    if student_map:
        selected_student = st.selectbox("Select Student", list(student_map.keys()))
        student_id = student_map[selected_student]
    else:
        st.warning("No students found.")
        student_id = None

    if st.button("Assign Student"):
        if class_id is None:
            st.error("Please create a classroom before assigning students.")
        elif student_id is None:
            st.error("Please select a student to assign.")
        else:
            assign_students_to_class(class_id, [student_id])
            st.success("Student assigned.")

    st.write("### View Students in a Class")
    if class_map:
        view_class = st.selectbox(
            "Select Classroom to View", list(class_map.keys()), key="view_class_select"
        )
        cid = class_map[view_class]
    else:
        cid = st.number_input("Class ID to view", min_value=1, step=1)

    if st.button("Load Class"):
        students = get_students_in_class(cid)
        st.table(pd.DataFrame(students))

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
    # =====================================================================
    #   COURSES PANEL — CREATE / SELECT / MANAGE COURSES
    # =====================================================================

    st.sidebar.markdown("### 📘 Courses")

    # Fetch all existing courses
    all_courses = fetch_all(
        "SELECT course_id, course_name FROM spelling_courses ORDER BY course_id;"
    )

    def row_to_dict(row):
        """Convert SQLAlchemy Row / tuple / dict → dict safely."""
        if hasattr(row, "_mapping"):
            return dict(row._mapping)
        if isinstance(row, dict):
            return row
        if isinstance(row, tuple):
            # Fallback assumption: (course_id, course_name)
            return {
                "course_id": row[0],
                "course_name": row[1],
            }
        return {}

    course_name_map = {}
    if all_courses:
        for row in all_courses:
            r = row_to_dict(row)
            if "course_name" in r and "course_id" in r:
                course_name_map[r["course_name"]] = r["course_id"]

    # -----------------------------------------------------------
    # 1) CREATE NEW COURSE
    # -----------------------------------------------------------
    with st.sidebar.expander("➕ Create New Course"):
        new_course_name = st.text_input("Course Name", key="new_course_name_input")

        if st.button("Create Course", key="create_course_btn"):
            if not new_course_name.strip():
                st.warning("Please enter a course name.")
            else:
                rows = execute(
                    """
                    INSERT INTO spelling_courses (course_name)
                    VALUES (:name)
                    RETURNING course_id;
                    """,
                    {"name": new_course_name.strip()},
                )

                if rows and isinstance(rows, list) and hasattr(rows[0], "_mapping"):
                    new_id = rows[0]._mapping["course_id"]
                    st.success(f"Course created! (ID: {new_id})")
                    st.experimental_rerun()
                else:
                    st.error("Could not create course.")

    # -----------------------------------------------------------
    # 2) SELECT EXISTING COURSE
    # -----------------------------------------------------------

    st.sidebar.markdown("### 📂 Select Course")

    if course_name_map:
        selected_course_name = st.sidebar.selectbox(
            "Choose a course",
            list(course_name_map.keys()),
            key="course_select_box",
        )
        selected_course_id = course_name_map.get(selected_course_name)
    else:
        st.sidebar.info("No courses created yet.")
        selected_course_name = None
        selected_course_id = None

    # -----------------------------------------------------------
    # 3) LOAD COURSE DETAILS (BUTTON FIXED: UNIQUE KEY ADDED)
    # -----------------------------------------------------------

    if selected_course_id:
        if st.sidebar.button("Load Lessons", key=f"load_lessons_btn_{selected_course_id}"):
            st.session_state["selected_course_id"] = selected_course_id
            st.session_state["selected_course_name"] = selected_course_name
            st.success(f"Loaded course: {selected_course_name}")

    # Save fallback if user didn't click "Load Lessons" this session
    selected_course_id = st.session_state.get("selected_course_id", selected_course_id)
    selected_course_name = st.session_state.get("selected_course_name", selected_course_name)

    # Display header on main page
    if selected_course_id:
        st.markdown(
            f"## 📘 Managing Course: **{selected_course_name}** (ID {selected_course_id})"
        )


# =========================================================
#                PAGE: CLASSROOMS
# =========================================================

elif menu == "Classrooms":
    render_classrooms_page()
