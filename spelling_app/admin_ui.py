import streamlit as st
import pandas as pd

from spelling_app.services.spelling_service import (
    load_course_data,
    load_lessons_for_course,
    process_csv_upload,
)

def render_spelling_admin():
    st.header("📘 Spelling Admin Panel")

    # --------------------------------------------
    # Load courses
    # --------------------------------------------
    courses = load_course_data()
    if isinstance(courses, dict) and "error" in courses:
        st.error(courses["error"])
        return
    if not courses:
        st.warning("No spelling courses found.")
        return

    course_map = {c["title"]: c["course_id"] for c in courses}
    selected_course = st.selectbox("Select Spelling Course", list(course_map.keys()))
    course_id = course_map[selected_course]

    st.subheader("Upload Spelling CSV")
    csv_file = st.file_uploader("Upload CSV", type=["csv"])

    if csv_file:
        df = pd.read_csv(csv_file)
        st.dataframe(df)

        update_mode = st.selectbox("Update Mode", ["append", "replace"])
        preview_only = st.checkbox("Preview Only", value=False)

        if st.button("Process CSV"):
            result = process_csv_upload(df, update_mode, preview_only, course_id)
            if "error" in result:
                st.error(result["error"])
            else:
                st.success(result["message"])
                st.dataframe(pd.DataFrame(result["details"]), use_container_width=True)
