import streamlit as st
import pandas as pd

from spelling_app.services.spelling_service import (
    create_course,
    create_lesson,
    create_item,
    map_item_to_lesson,
    load_course_data,
    load_lessons,
)

def render_spelling_admin():
    st.title("📘 Spelling App — Admin Console")

    st.markdown("""
    This console allows you to:
    - Create courses  \
    - Create lessons  \
    - Upload spelling questions using CSV  \
    - Map items to lessons  \
    """)

    tab1, tab2, tab3 = st.tabs(["Create Course", "Create Lesson", "Upload Items (CSV)"])

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
                create_course(title, desc, level)
                st.success(f"Course '{title}' created successfully!")

        st.markdown("---")
        st.subheader("Existing Courses")
        courses = load_course_data()
        st.dataframe(courses)

    # -------------------------
    # TAB 2: CREATE LESSON
    # -------------------------
    with tab2:
        st.subheader("Create a New Lesson")

        courses = load_course_data()
        course_map = {c["title"]: c["sp_course_id"] for c in courses}

        course_title = st.selectbox("Select Course", list(course_map.keys()))

        lesson_title = st.text_input("Lesson Title")
        instructions = st.text_area("Instructions (optional)")
        sort_order = st.number_input("Sort Order", min_value=1, step=1)

        if st.button("Create Lesson"):
            cid = course_map[course_title]
            create_lesson(cid, lesson_title, instructions, sort_order)
            st.success(f"Lesson '{lesson_title}' created in '{course_title}'")

        st.markdown("---")
        st.subheader("Lessons for Selected Course")
        if course_title:
            cid = course_map[course_title]
            lesson_rows = load_lessons(cid)
            st.dataframe(lesson_rows)

    # -------------------------
    # TAB 3: UPLOAD CSV TO IMPORT ITEMS
    # -------------------------
    with tab3:
        st.subheader("Upload Spelling Items")

        st.markdown("""
        **CSV Format must include:**
        - base_word  \
        - display_form  \
        - pattern_type  \
        - options  \
        - difficulty  \
        - hint  \
        - lesson_id  \
        """)

        file = st.file_uploader("Upload CSV", type=["csv"])

        if file:
            df = pd.read_csv(file)
            st.success("CSV Loaded Successfully")
            st.dataframe(df)

            if st.button("Insert Items Into Database"):
                for _, row in df.iterrows():
                    # Insert item into items table
                    create_item(
                        row["base_word"],
                        row["display_form"],
                        row.get("pattern_type"),
                        row.get("options"),
                        row.get("difficulty", 2),
                        row.get("hint"),
                    )

                st.success("All items inserted!")

