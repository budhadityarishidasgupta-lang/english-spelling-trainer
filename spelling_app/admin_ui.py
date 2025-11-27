import streamlit as st
import pandas as pd

from shared.db import fetch_all

# Import only service functions, not the module
from spelling_app.services.spelling_service import (
    load_course_data,
    process_csv_upload,
)

import streamlit as st



def _load_spelling_courses():
    courses = spelling_service.load_course_data()
    return courses if courses else []


def render_spelling_admin():
    """
    Main entrypoint for the Spelling Admin console.
    Streamlit calls this from app.py.
    """
    

    st.header("Spelling Trainer – Admin Console")

    # 1. Load courses
    courses = load_course_data()
    if isinstance(courses, dict) and "error" in courses:
        st.error(courses["error"])
        return

    # 2. Course selector
    course_map = {c["title"]: c["course_id"] for c in courses}
    selected_course = st.selectbox("Choose Spelling Course", list(course_map.keys()))
    course_id = course_map[selected_course]

    st.subheader("Upload CSV file containing spelling lessons")
    uploaded = st.file_uploader("Choose CSV", type=["csv"])

    update_mode = st.radio(
        "Choose update mode",
        ["overwrite", "append"],
        horizontal=True
    )

    preview_only = st.checkbox("Preview only (do not insert into DB)")

    if st.button("Process CSV Upload"):
        if uploaded is None:
            st.error("Please upload a CSV first.")
            return

        import pandas as pd
        df = pd.read_csv(uploaded)
        result = process_csv_upload(df, update_mode, preview_only, course_id)

        if "error" in result:
            st.error(result["error"])
        else:
            st.success("CSV processed successfully.")
            st.dataframe(pd.DataFrame(result["details"]))


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
