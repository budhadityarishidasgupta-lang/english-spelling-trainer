print(">>> LOADED admin_ui FROM:", __file__)

import streamlit as st
import pandas as pd
from typing import List, Dict


from shared.db import fetch_all
from spelling_app.repository.course_repo import *
from spelling_app.repository.lesson_repo import *
from spelling_app.services.spelling_service import (
    create_course,
    create_lesson,
    create_item,
    map_item_to_lesson,
    load_course_data,
    load_lessons,
    update_course_details,
    update_lesson_details,
)


def _load_spelling_courses():
    from spelling_app.repository import course_repo
    result = course_repo.get_all_spelling_courses()
    # Convert SQLAlchemy rows to dicts
    return [dict(r._mapping) for r in result] if result else []


def _load_spelling_lessons(course_id: int | None = None):
    """
    Load ONLY spelling lessons using lesson_type = 'spelling'.
    Optionally filter by course_id.
    """
    params: dict[str, int] = {}
    where_clauses = ["lesson_type = 'spelling'"]

    if course_id is not None:
        where_clauses.append("course_id = :course_id")
        params["course_id"] = course_id

    where_sql = " AND ".join(where_clauses)

    sql = f"""
        SELECT
            lesson_id,
            title,
            instructions,
            course_id,
            is_active,
            created_at
        FROM lessons
        WHERE {where_sql}
        ORDER BY created_at DESC;
    """

    result = fetch_all(sql, params)

    if isinstance(result, dict):
        return result

    return [dict(getattr(row, "_mapping", row)) for row in result]


def _load_word_accuracy(course_id: int | None, lesson_id: int | None):
    params: dict[str, int] = {}
    filters = []

    if course_id:
        filters.append("l.course_id = :course_id")
        params["course_id"] = course_id
    if lesson_id:
        filters.append("l.lesson_id = :lesson_id")
        params["lesson_id"] = lesson_id

    where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""

    return fetch_all(
        f"""
        SELECT si.item_id,
               si.word,
               l.title AS lesson_title,
               COUNT(sa.*) AS total_attempts,
               COALESCE(SUM(CASE WHEN sa.is_correct THEN 1 ELSE 0 END), 0) AS correct_attempts
        FROM spelling_items si
        JOIN spelling_lesson_items sli ON sli.item_id = si.item_id
        JOIN lessons l ON l.lesson_id = sli.lesson_id
        LEFT JOIN spelling_attempts sa ON sa.item_id = si.item_id
        {where_clause}
        GROUP BY si.item_id, si.word, l.title
        ORDER BY si.item_id
        """,
        params,
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

    tab1, tab2, tab3, tab4 = st.tabs([
        "Create Course",
        "Create Lesson",
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
                create_course(title, desc, level)
                st.success(f"Course '{title}' created successfully!")

        st.markdown("---")
        st.subheader("Existing Courses")

        # Load courses
        courses = load_course_data()
        df = pd.DataFrame(courses)
        orig = df.copy()

        editable = ["title", "description", "difficulty", "course_type"]
        disabled = [c for c in df.columns if c not in editable]

        edited = st.data_editor(df, disabled=disabled, num_rows="fixed", key="edit_courses")

        for _, row in edited.iterrows():
            old = orig.loc[orig["course_id"] == row["course_id"]].iloc[0]
            changes = {}
            for col in editable:
                if col in df.columns and row[col] != old[col]:
                    changes[col] = row[col]
            if changes:
                update_course_details(row["course_id"], **changes)
                st.success("Course updated.")

    # -------------------------
    # TAB 2: CREATE LESSON
    # -------------------------
    with tab2:
        st.subheader("Create a New Lesson")

        # Load spelling courses
        courses = _load_spelling_courses()

        if isinstance(courses, dict):
            st.error("Error loading courses: " + str(courses))
            return

        if not courses:
            st.warning("No spelling courses found. Please create a course first.")
            return

        course_options = {
            f"{c['title']} (ID {c['course_id']})": c['course_id']
            for c in courses
        }

        selected_option = st.selectbox("Select Course", list(course_options.keys()))

        selected_course_id = course_options[selected_option]
        selected_course_title = next(
            (c["title"] for c in courses if c["course_id"] == selected_course_id),
            "",
        )

        lesson_title = st.text_input("Lesson Title")
        instructions = st.text_area("Instructions (optional)")
        sort_order = st.number_input("Sort Order", min_value=1, step=1)

        if st.button("Create Lesson"):
            create_lesson(selected_course_id, lesson_title, instructions, sort_order)
            st.success(f"Lesson '{lesson_title}' created in '{selected_course_title}'")

        st.subheader("Manage Lessons for This Course")

        all_lessons = _load_spelling_lessons()
        filtered = [l for l in all_lessons if l.get("course_id") == selected_course_id]
        df2 = pd.DataFrame(filtered)
        orig2 = df2.copy()

        editable2 = ["title", "instructions", "is_active"]
        disabled2 = [c for c in df2.columns if c not in editable2]

        edited2 = st.data_editor(df2, disabled=disabled2, num_rows="fixed", key="edit_lessons")

        for _, row in edited2.iterrows():
            old = orig2.loc[orig2["lesson_id"] == row["lesson_id"]].iloc[0]
            changes = {}
            if row["title"] != old["title"]:
                changes["title"] = row["title"]
            if row["instructions"] != old["instructions"]:
                changes["description"] = row["instructions"]
            if row["is_active"] != old["is_active"]:
                changes["is_active"] = bool(row["is_active"])

            if changes:
                update_lesson_details(row["lesson_id"], **changes)
                st.success("Lesson updated.")

        st.markdown("---")
        st.subheader("Lessons for Selected Course")
        if selected_course_title:
            lesson_rows = load_lessons(selected_course_id)
            st.dataframe(lesson_rows)

    # -------------------------
    # TAB 3: UPLOAD CSV TO IMPORT ITEMS
    # -------------------------
    with tab3:
        st.header("Upload Spelling Items (CSV)")

        # -------------------------------------------------------
        # LOAD SPELLING COURSES FOR CSV UPLOAD
        # -------------------------------------------------------
        courses = _load_spelling_courses()

        if not courses:
            st.warning("No spelling courses found. Please create a spelling course first.")
            return

        course_options = {
            f"{c['title']} (ID {c['course_id']})": c["course_id"]
            for c in courses
        }

        selected_course_label = st.selectbox(
            "Select Spelling Course",
            list(course_options.keys())
        )
        selected_course_id = course_options[selected_course_label]

        st.markdown("""
        Upload a CSV file containing spelling words.
        The CSV must have at least: **word, lesson_id**
        """)

        uploaded_file = st.file_uploader("Choose CSV file", type=["csv"])

        # Add update mode selector
        update_mode = st.selectbox(
            "Choose update mode",
            [
                "Overwrite existing words",
                "Update existing words",
                "Add new words only"
            ]
        )

        # Add preview-only mode
        preview_only = st.checkbox("Preview only (do not insert into database)")

        # Show CSV preview
        if uploaded_file is not None:
            import pandas as pd

            try:
                df = pd.read_csv(uploaded_file)
                st.subheader("CSV Preview")
                st.dataframe(df.head(), use_container_width=True)
                st.info("Validation and processing will occur after you click 'Process CSV Upload'.")
            except Exception as e:
                st.error(f"Error reading CSV: {e}")
                return

            # Submit button
            if st.button("Process CSV Upload"):
                st.info(
                    f"Uploaded with mode: {update_mode}, "
                    f"Preview only: {preview_only}"
                )

                # Pass to backend service (Patch 2 will implement this)
                from spelling_app.services.spelling_service import process_csv_upload
                result = process_csv_upload(df, update_mode, preview_only, selected_course_id)

                if isinstance(result, dict) and "error" in result:
                    st.error(result["error"])
                else:
                    st.success(result)

    # -------------------------
    # TAB 4: ASSIGN COURSES
    # -------------------------
    with tab4:
        render_assign_courses_tab()

    st.markdown("---")
    st.subheader("Spelling Weak-Word Analytics")
    st.caption("Monitor accuracy across spelling words without impacting synonym analytics.")

    courses = _load_spelling_courses()
    lessons = _load_spelling_lessons()

    if isinstance(courses, dict) and courses.get("error"):
        st.error(f"Could not load spelling courses: {courses['error']}")
        return
    if isinstance(lessons, dict) and lessons.get("error"):
        st.error(f"Could not load spelling lessons: {lessons['error']}")
        return
    course_options = {
        f"{c['title']} (ID {c['course_id']})": c["course_id"]
        for c in courses
    } if courses else {}
    lesson_titles = {l["title"]: l["lesson_id"] for l in lessons} if lessons else {}

    c1, c2 = st.columns(2)
    with c1:
        selected_course_option = st.selectbox("Filter by course", ["All courses"] + list(course_options.keys()))
        selected_course_id = course_options.get(selected_course_option)

    with c2:
        available_lessons = _load_spelling_lessons(selected_course_id) if selected_course_id else lessons
        lesson_titles = {l["title"]: l["lesson_id"] for l in available_lessons} if available_lessons else {}
        lesson_options = ["All lessons" if not selected_course_id else "All lessons in this course"] + list(lesson_titles.keys())
        selected_lesson = st.selectbox("Filter by lesson", lesson_options)
        selected_lesson_id = lesson_titles.get(selected_lesson)

    analytics = _load_word_accuracy(selected_course_id, selected_lesson_id)

    if isinstance(analytics, dict) and analytics.get("error"):
        st.error(f"Could not load analytics: {analytics['error']}")
        return

    if not analytics:
        st.info("No spelling attempts found for the selected filters yet.")
        return

    df = pd.DataFrame(analytics)
    df["accuracy"] = df.apply(
        lambda r: (r.get("correct_attempts", 0) / r.get("total_attempts", 1) * 100) if r.get("total_attempts", 0) else 0.0,
        axis=1,
    )
    df["weak"] = df.apply(lambda r: r["total_attempts"] >= 2 and r["accuracy"] < 80, axis=1)
    df = df.sort_values(by=["accuracy"], ascending=[True])

    total_words_attempted = len(df[df["total_attempts"] > 0])
    weak_words_count = len(df[df["weak"]])
    total_attempts_sum = df["total_attempts"].sum()
    correct_attempts_sum = df["correct_attempts"].sum()
    average_accuracy = (correct_attempts_sum / total_attempts_sum * 100) if total_attempts_sum else 0.0
    st.markdown(
        """
        <div class="quiz-surface">
          <div class="lesson-header">
            <h3>Selection Overview</h3>
            <p class="lesson-instruction">Tracks spelling practice only. Synonym data remains separate.</p>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    m1, m2, m3 = st.columns(3)
    m1.metric("Words attempted", total_words_attempted)
    m2.metric("Weak words", weak_words_count)
    m3.metric("Average accuracy", f"{average_accuracy:.1f}%")

    display_df = df[["word", "lesson_title", "total_attempts", "correct_attempts", "accuracy", "weak"]]
    display_df = display_df.rename(
        columns={
            "word": "Word",
            "lesson_title": "Lesson",
            "total_attempts": "Total Attempts",
            "correct_attempts": "Correct",
            "accuracy": "Accuracy %",
            "weak": "Weak?",
        }
    )

    def _highlight_row(row):
        color = "background-color: #3c1c20; color: #ffb3b3" if row["Weak?"] else ""
        return [color] * len(row)

    st.dataframe(display_df.style.apply(_highlight_row, axis=1), use_container_width=True)


def render_assign_courses_tab():
    import streamlit as st
    from shared.db import fetch_all
    from spelling_app.services.enrollment_service import (
        enroll_student_in_course,
        get_all_spelling_enrollments,
    )

    st.header("Assign Spelling Courses to Students")

    # Load all students (users table)
    students = fetch_all("SELECT id, name, email FROM users ORDER BY name ASC;")
    if isinstance(students, dict):
        st.error("Error loading students: " + str(students))
        return

    student_options = {
        f"{s._mapping['name']} ({s._mapping['email']})": s._mapping['id']
        for s in students
    }

    # Load spelling courses only
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

