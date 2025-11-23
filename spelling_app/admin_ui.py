print(">>> LOADED admin_ui FROM:", __file__)

import streamlit as st
import pandas as pd

from shared.db import fetch_all
from spelling_app.services.spelling_service import (
    create_course,
    create_lesson,
    create_item,
    map_item_to_lesson,
    load_course_data,
    load_lessons,
)


def _load_spelling_courses():
    return load_course_data()


def _load_spelling_lessons(course_id=None):
    """
    Load lessons for the spelling admin.

    The real lessons table uses:
    - lesson_id (NOT id)
    - course_id (NOT lesson_type)
    """
    if course_id:
        return fetch_all(
            """
            SELECT
                lesson_id,
                title,
                instructions,
                sort_order
            FROM lessons
            WHERE course_id = :cid
            ORDER BY sort_order NULLS LAST, lesson_id
            """,
            {"cid": course_id},
        )

    return fetch_all(
        """
        SELECT
            lesson_id,
            title,
            instructions,
            sort_order
        FROM lessons
        ORDER BY sort_order NULLS LAST, lesson_id
        """
    )


def _load_students():
    rows = fetch_all(
        """
        SELECT u.*
        FROM users u
        JOIN enrollments e ON u.user_id = e.user_id
        JOIN courses c ON e.course_id = c.course_id
        """,
    )

    if isinstance(rows, dict):
        return rows

    students = []
    for row in rows:
        user_id = row.get("user_id") or row.get("id")
        students.append(
            {
                "user_id": user_id,
                "name": row.get("name"),
                "email": row.get("email"),
                "label": row.get("name")
                or row.get("email")
                or (f"User {user_id}" if user_id is not None else "User"),
            }
        )

    return sorted(students, key=lambda s: s["label"])


def _load_word_accuracy(course_id: int | None, lesson_id: int | None, student_id: int | None):
    params: dict[str, int] = {}
    filters = []

    if course_id:
        filters.append("l.course_id = :course_id")
        params["course_id"] = course_id
    if lesson_id:
        filters.append("w.lesson_id = :lesson_id")
        params["lesson_id"] = lesson_id

    student_filter = ""
    if student_id:
        student_filter = "AND a.user_id = :student_id"
        params["student_id"] = student_id

    where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""

    return fetch_all(
        f"""
        SELECT w.id,
               w.word,
               l.title AS lesson_title,
               COUNT(a.*) AS total_attempts,
               COALESCE(SUM(CASE WHEN a.is_correct THEN 1 ELSE 0 END), 0) AS correct_attempts
        FROM spelling_words w
        JOIN lessons l ON l.lesson_id = w.lesson_id
        LEFT JOIN attempts a ON a.word_id = w.id
                           AND a.attempt_type IN ('spelling','spelling_missing','spelling_daily')
                           {student_filter}
        {where_clause}
        GROUP BY w.id, w.word, l.title
        ORDER BY w.id
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

        if isinstance(courses, dict) and courses.get("error"):
            st.error(f"Could not load courses: {courses['error']}")
            return

        if not courses:
            st.warning("No courses found. Please create one first.")
            return

        selected_course = st.selectbox(
            "Select Course",
            courses,
            format_func=lambda c: c.get("title", "Course"),
        )
        selected_course_id = selected_course.get("course_id") if selected_course else None
        selected_course_title = selected_course.get("title") if selected_course else None

        lesson_title = st.text_input("Lesson Title")
        instructions = st.text_area("Instructions (optional)")
        sort_order = st.number_input("Sort Order", min_value=1, step=1)

        if st.button("Create Lesson"):
            create_lesson(selected_course_id, lesson_title, instructions, sort_order)
            st.success(f"Lesson '{lesson_title}' created in '{selected_course_title}'")

        st.markdown("---")
        st.subheader("Lessons for Selected Course")
        if selected_course_title:
            lesson_rows = load_lessons(selected_course_id)
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

    st.markdown("---")
    st.subheader("Spelling Weak-Word Analytics")
    st.caption("Monitor accuracy across spelling words without impacting synonym analytics.")

    courses = _load_spelling_courses()
    lessons = _load_spelling_lessons()
    students = _load_students()

    if isinstance(courses, dict) and courses.get("error"):
        st.error(f"Could not load spelling courses: {courses['error']}")
        return
    if isinstance(lessons, dict) and lessons.get("error"):
        st.error(f"Could not load spelling lessons: {lessons['error']}")
        return
    if isinstance(students, dict) and students.get("error"):
        st.error(f"Could not load students: {students['error']}")
        return

    course_titles = {c["title"]: c["course_id"] for c in courses} if courses else {}
    lesson_titles = {l["title"]: l["lesson_id"] for l in lessons} if lessons else {}
    student_labels = {s["label"]: s["user_id"] for s in students} if students else {}

    c1, c2, c3 = st.columns(3)
    with c1:
        selected_course = st.selectbox("Filter by course", ["All courses"] + list(course_titles.keys()))
        selected_course_id = course_titles.get(selected_course)

    with c2:
        available_lessons = _load_spelling_lessons(selected_course_id) if selected_course_id else lessons
        lesson_titles = {l["title"]: l["lesson_id"] for l in available_lessons} if available_lessons else {}
        lesson_options = ["All lessons" if not selected_course_id else "All lessons in this course"] + list(lesson_titles.keys())
        selected_lesson = st.selectbox("Filter by lesson", lesson_options)
        selected_lesson_id = lesson_titles.get(selected_lesson)

    with c3:
        selected_student = st.selectbox("Filter by student", ["All students"] + list(student_labels.keys()))
        selected_student_id = student_labels.get(selected_student)

    analytics = _load_word_accuracy(selected_course_id, selected_lesson_id, selected_student_id)

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

