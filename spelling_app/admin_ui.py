print(">>> LOADED admin_ui FROM:", __file__)

import streamlit as st
from shared.db import fetch_all
from spelling_app.services import spelling_service


def _load_spelling_courses():
    courses = spelling_service.load_course_data()
    return courses if courses else []


def render_spelling_admin():
    st.title("📘 Spelling App — Admin Console")

    st.markdown(
        """
    This console allows you to:
    - Create courses  \
    - Upload spelling questions using CSV  \
    - Assign courses to students  \
    """
    )

    tab1, tab2, tab3 = st.tabs([
        "Create Course",
        "Upload Items (CSV)",
        "Assign Courses",
    ])

    # -------------------------
    # TAB 1: CREATE COURSE
    # -------------------------
    with tab1:
        st.subheader("Create a New Course")

        title = st.text_input("Course Title")
        desc = st.text_area("Description (optional)")
        level = st.selectbox("Difficulty Level", ["Beginner", "Intermediate", "Advanced"])

        if st.button("Create Course"):
            if not title:
                st.error("Course title is required.")
            else:
                spelling_service.create_course(title, desc, level)
                st.success(f"Course '{title}' created successfully!")

        st.markdown("---")
        st.subheader("Existing Courses")

        courses = spelling_service.load_course_data()
        if isinstance(courses, dict) and courses.get("error"):
            st.error(courses["error"])
        elif courses:
            st.table(courses)
        else:
            st.info("No courses found yet.")

    # -------------------------
    # TAB 2: UPLOAD CSV TO IMPORT ITEMS
    # -------------------------
    with tab2:
        st.header("Upload Spelling Items (CSV)")

        courses = _load_spelling_courses()

        if not courses:
            st.warning("No spelling courses found. Please create a spelling course first.")
            st.stop()

        course_options = {
            f"{c['title']} (ID {c['course_id']})": c["course_id"]
            for c in courses
        }

        selected_course_label = st.selectbox(
            "Select Spelling Course",
            list(course_options.keys())
        )
        selected_course_id = course_options[selected_course_label]

        st.markdown(
            """
        Upload a CSV file containing spelling words.
        The CSV must have at least: **word, lesson_id**
        """
        )

        uploaded_file = st.file_uploader("Choose CSV file", type=["csv"])

        update_mode = st.radio(
            "Choose update mode",
            [
                "Overwrite existing words",
                "Update existing words",
                "Add new words only"
            ]
        )

        preview_only = st.checkbox("Preview only (do not insert into database)")

        csv_df = None
        if uploaded_file is not None:
            try:
                import pandas

                csv_df = pandas.read_csv(uploaded_file)
                if preview_only:
                    st.subheader("CSV Preview")
                    st.dataframe(csv_df.head(), use_container_width=True)
                    st.info("Validation and processing will occur after you click 'Process CSV Upload'.")
            except Exception as e:
                st.error(f"Error reading CSV: {e}")
                csv_df = None

        if st.button("Process CSV Upload"):
            if csv_df is None:
                st.error("Please upload a valid CSV file first.")
            else:
                result = spelling_service.process_csv_upload(csv_df, update_mode, preview_only, selected_course_id)

                if isinstance(result, dict) and "error" in result:
                    st.error(result["error"])
                else:
                    st.success(result)

    # -------------------------
    # TAB 3: ASSIGN COURSES
    # -------------------------
    with tab3:
        render_assign_courses_tab()


def render_assign_courses_tab():
    from spelling_app.services.enrollment_service import (
        enroll_student_in_course,
        get_all_spelling_enrollments,
    )

    st.header("Assign Spelling Courses to Students")

    students = fetch_all("SELECT id, name, email FROM users ORDER BY name ASC;")
    if isinstance(students, dict):
        st.error("Error loading students: " + str(students))
        return

    student_options = {
        f"{s._mapping['name']} ({s._mapping['email']})": s._mapping['id']
        for s in students
    }

    courses = _load_spelling_courses()
    course_options = {
        f"{c['title']} (ID {c['course_id']})": c['course_id']
        for c in courses
    }

    if not students or not courses:
        st.warning("Need at least one student and one spelling course.")
        return

    st.subheader("Assign a Course")

    selected_student = st.selectbox("Select Student", list(student_options.keys()))
    selected_course_option = st.selectbox("Select Spelling Course", list(course_options.keys()))

    if st.button("Assign Course"):
        sid = student_options[selected_student]
        cid = course_options[selected_course_option]
        result = enroll_student_in_course(sid, cid)

        if isinstance(result, dict) and "error" in result:
            st.error(result["error"])
        else:
            st.success(f"Assigned '{selected_course_option}' to {selected_student}")

    st.subheader("Existing Enrollments")

    enrollments = get_all_spelling_enrollments()
    if isinstance(enrollments, dict):
        st.error("Error loading enrollments: " + str(enrollments))
        return

    if not enrollments:
        st.info("No enrollments yet.")
        return

    st.dataframe(enrollments, use_container_width=True)
