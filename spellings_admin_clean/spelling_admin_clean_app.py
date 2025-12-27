#!/usr/bin/env python3
# -------------------------------------------------
# Spelling Admin App (FINAL, CLEAN)
# -------------------------------------------------

import sys
import streamlit as st

# ---- Force project root for Render ----
PROJECT_ROOT = "/opt/render/project/src"
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from shared.db import engine, fetch_all
from spellings_admin_clean.spelling_help_text_repo import (
    get_help_text,
    upsert_help_text,
)
from spellings_admin_clean.upload_manager_clean import process_spelling_csv
from spelling_app.repository.spelling_course_repo import archive_course
from spelling_app.repository.spelling_lesson_repo import (
    archive_lesson,
    get_lessons_for_course,
)
from spelling_app.repository.student_pending_repo import (
    approve_pending_registration,
    delete_pending_registration,
    list_pending_registrations,
)


# -------------------------------------------------
# Helpers
# -------------------------------------------------

def rows_to_dicts(rows):
    if not rows:
        return []
    out = []
    for r in rows:
        if hasattr(r, "_mapping"):
            out.append(dict(r._mapping))
        elif isinstance(r, dict):
            out.append(r)
    return out


def get_all_courses():
    rows = fetch_all(
        "SELECT course_id, course_name FROM spelling_courses ORDER BY course_name"
    )
    return rows_to_dicts(rows)


def create_course(course_name: str):
    if not course_name.strip():
        return None

    rows = fetch_all(
        """
        INSERT INTO spelling_courses (course_name)
        VALUES (:name)
        RETURNING course_id;
        """,
        {"name": course_name.strip()},
    )
    rows = rows_to_dicts(rows)
    return rows[0]["course_id"] if rows else None


def rename_course(course_id: int, new_name: str):
    if not course_id or not new_name.strip():
        return False

    rows = fetch_all(
        """
        UPDATE spelling_courses
        SET course_name = :name
        WHERE course_id = :cid
        RETURNING course_id;
        """,
        {"name": new_name.strip(), "cid": course_id},
    )
    rows = rows_to_dicts(rows)
    return bool(rows)


def fetch_active_students():
    rows = fetch_all(
        """
        SELECT DISTINCT
            u.user_id,
            u.name,
            u.email
        FROM users u
        JOIN spelling_enrollments e
            ON e.user_id = u.user_id
        JOIN spelling_courses c
            ON c.course_id = e.course_id
        WHERE u.role = 'student'
          AND u.is_active = true
        ORDER BY u.name;
        """
    )
    return rows_to_dicts(rows)


def fetch_student_course_map():
    rows = fetch_all(
        """
        SELECT
            e.user_id,
            STRING_AGG(c.course_name, ', ' ORDER BY c.course_name) AS assigned_courses
        FROM spelling_enrollments e
        JOIN spelling_courses c
          ON c.course_id = e.course_id
        GROUP BY e.user_id;
        """
    )
    return {r["user_id"]: r.get("assigned_courses", "") for r in rows_to_dicts(rows)}


def assign_course_to_student(user_id: int, course_id: int):
    if not user_id or not course_id:
        return False

    fetch_all(
        """
        INSERT INTO spelling_enrollments (user_id, course_id)
        VALUES (:uid, :cid)
        ON CONFLICT DO NOTHING;
        """,
        {"uid": user_id, "cid": course_id},
    )
    return True


# -------------------------------------------------
# Main UI
# -------------------------------------------------

def render_course_management():
    st.header("Course Management")

    courses = get_all_courses()
    course_map = {c["course_name"]: c["course_id"] for c in courses}

    selected_course_name = None
    selected_course_id = None
    if course_map:
        selected_course_name = st.selectbox(
            "Existing Courses",
            list(course_map.keys()),
        )
        selected_course_id = course_map.get(selected_course_name)
    else:
        st.info("No courses yet.")

    new_course_name = st.text_input("New Course Name")

    action_cols = st.columns(3)
    with action_cols[0]:
        if st.button("Create"):
            if not new_course_name.strip():
                st.error("Please enter a course name to create.")
            else:
                cid = create_course(new_course_name)
                if cid:
                    st.success(f"Course '{new_course_name}' created.")
                    st.experimental_rerun()
                else:
                    st.error("Failed to create course.")

    with action_cols[1]:
        if st.button("Rename"):
            if not selected_course_id:
                st.error("Select a course to rename.")
            elif not new_course_name.strip():
                st.error("Enter a new course name.")
            else:
                if rename_course(selected_course_id, new_course_name):
                    st.success(f"Course renamed to '{new_course_name}'.")
                    st.experimental_rerun()
                else:
                    st.error("Course rename failed.")

    with action_cols[2]:
        if st.checkbox("Confirm archive"):
            if st.button("Archive Course"):
                if not selected_course_id:
                    st.error("Select a course to archive.")
                else:
                    archive_course(selected_course_id)
                    st.success("Course archived successfully.")
                    st.experimental_rerun()

    st.subheader("Lessons")

    if not selected_course_id:
        st.info("Select a course to view its lessons.")
    else:
        show_archived = st.checkbox("Show archived", value=False)
        lessons = get_lessons_for_course(
            selected_course_id,
            include_archived=show_archived,
        )

        # Guard: selected lesson must belong to this course
        if st.session_state.get("selected_lesson_id"):
            valid_lesson_ids = {l["lesson_id"] for l in lessons}
            if st.session_state.selected_lesson_id not in valid_lesson_ids:
                st.session_state.selected_lesson_id = None

        if not lessons:
            st.info("No lessons for this course yet.")
        else:
            for lesson in lessons:
                if not lesson.get("is_active") and not show_archived:
                    continue

                col1, col2 = st.columns([5, 1])
                with col1:
                    st.write(lesson.get("lesson_name"))

                with col2:
                    if lesson.get("is_active"):
                        if st.button("Archive", key=f"archive_{lesson['lesson_id']}"):
                            archive_lesson(lesson["lesson_id"])
                            st.success(f"Lesson '{lesson['lesson_name']}' archived.")
                            st.experimental_rerun()
                    else:
                        st.caption("Archived")

    st.markdown("## Upload Spelling CSV")

    uploaded_file = st.file_uploader(
        "Upload CSV (word, pattern, pattern_code, level, lesson_name, example_sentence)",
        type=["csv"],
    )

    if uploaded_file and not selected_course_id:
        st.warning("Please select or create a course first.")
        return

    if uploaded_file and selected_course_id:
        if st.button("Process CSV"):
            result = process_spelling_csv(uploaded_file, selected_course_id)

            if result.get("status") == "error":
                st.error(result.get("error"))
                return

            st.success("CSV processed successfully!")

            st.markdown("### Upload Summary")
            st.write("Words Added:", result["words_added"])
            st.write("Lessons Created:", result["lessons_created"])

            if result["patterns"]:
                st.write("Patterns:", ", ".join(result["patterns"]))

    with st.expander("Debug DB Status"):
        words = fetch_all("SELECT COUNT(*) AS c FROM spelling_words")
        lessons = fetch_all("SELECT COUNT(*) AS c FROM spelling_lessons")
        mappings = fetch_all("SELECT COUNT(*) AS c FROM spelling_lesson_items")

        words = rows_to_dicts(words)
        lessons = rows_to_dicts(lessons)
        mappings = rows_to_dicts(mappings)

        st.write("Words:", words[0]["c"] if words else 0)
        st.write("Lessons:", lessons[0]["c"] if lessons else 0)
        st.write("Lesson–Word Mappings:", mappings[0]["c"] if mappings else 0)

        sample = fetch_all(
            """
            SELECT sl.lesson_name, sw.word
            FROM spelling_lesson_items sli
            JOIN spelling_lessons sl ON sl.lesson_id = sli.lesson_id
            JOIN spelling_words sw ON sw.word_id = sli.word_id
            ORDER BY sl.lesson_id, sli.sort_order
            LIMIT 20;
            """
        )
        st.write("Sample mappings:")
        st.write(rows_to_dicts(sample))


def render_student_management():
    st.markdown("## 👩‍🎓 Students (Spelling App)")

    students = fetch_active_students()
    courses_lookup = get_all_courses()
    courses = {course["course_name"]: course["course_id"] for course in courses_lookup}
    assigned_map = fetch_student_course_map()

    if not students:
        st.info("No active students found.")
    else:
        header_cols = st.columns([3, 4, 4, 2])
        header_cols[0].markdown("**Name**")
        header_cols[1].markdown("**Email**")
        header_cols[2].markdown("**Assigned Courses**")
        header_cols[3].markdown("**Assign Course**")

        for student in students:
            c1, c2, c3, c4 = st.columns([3, 4, 4, 2])

            with c1:
                st.write(student["name"])

            with c2:
                st.write(student["email"])

            with c3:
                st.write(
                    assigned_map.get(student["user_id"], "—")
                )

            with c4:
                selected_course = st.selectbox(
                    "Assign Course",
                    options=list(courses.keys()),
                    key=f"assign_course_{student['user_id']}",
                    label_visibility="collapsed",
                )

                if st.button(
                    "Assign",
                    key=f"assign_btn_{student['user_id']}",
                ):
                    assign_course_to_student(
                        user_id=student["user_id"],
                        course_id=courses[selected_course],
                    )
                    st.success("Course assigned")
                    st.experimental_rerun()

    st.subheader("Pending Registrations")
    pending_rows = list_pending_registrations()

    if not pending_rows:
        st.info("No pending registrations.")
    else:
        for pending in pending_rows:
            cols = st.columns([2, 3, 2, 2, 2])
            cols[0].write(pending.get("student_name"))
            cols[1].write(pending.get("email"))
            cols[2].write(pending.get("requested_at"))

            with cols[3]:
                if st.button(
                    "Approve",
                    key=f"approve_{pending.get('id')}",
                ):
                    result = approve_pending_registration(pending.get("id"))
                    if result.get("error"):
                        st.error(result["error"])
                    else:
                        st.success("Registration approved and student created.")
                        st.experimental_rerun()

            with cols[4]:
                confirm_reject = st.checkbox(
                    "Confirm", key=f"reject_confirm_{pending.get('id')}"
                )
                if st.button(
                    "Reject",
                    key=f"reject_{pending.get('id')}",
                ):
                    if not confirm_reject:
                        st.warning("Confirm rejection before proceeding.")
                    else:
                        delete_pending_registration(pending.get("id"))
                        st.success("Pending registration rejected.")
                        st.experimental_rerun()


def render_help_texts_page(db):
    st.header("🛠️ Help Texts")
    st.caption("Manage instructional messages shown to students")

    st.subheader("Daily 5 Help Text")

    existing = get_help_text(db, "daily5_intro")

    title = st.text_input(
        "Title (optional)",
        value=existing.title if existing else "Daily 5 — Why it matters",
    )

    body = st.text_area(
        "Help text (Markdown supported)",
        height=220,
        value=existing.body if existing else "",
    )

    if st.button("💾 Save"):
        upsert_help_text(
            db=db,
            help_key="daily5_intro",
            title=title,
            body=body,
        )
        st.success("Daily 5 help text saved successfully.")


def main():
    st.set_page_config(
        page_title="WordSprint – Spelling Admin",
        layout="wide",
    )

    if "admin_page" not in st.session_state:
        st.session_state.admin_page = "course_management"

    admin_options = ["Course Management", "Students", "Help Texts"]
    default_index = 0
    if st.session_state.admin_page == "students":
        default_index = admin_options.index("Students")
    elif st.session_state.admin_page == "help_texts":
        default_index = admin_options.index("Help Texts")

    admin_section = st.sidebar.radio(
        "Admin Sections",
        admin_options,
        index=default_index,
    )

    if admin_section == "Course Management":
        st.session_state.admin_page = "course_management"
    elif admin_section == "Students":
        st.session_state.admin_page = "students"
    elif admin_section == "Help Texts":
        st.session_state.admin_page = "help_texts"

    st.sidebar.markdown("### 🛠️ Content")
    if st.sidebar.button("Help Texts"):
        st.session_state.admin_page = "help_texts"

    if st.session_state.admin_page == "course_management":
        render_course_management()
    elif st.session_state.admin_page == "students":
        render_student_management()
    elif st.session_state.admin_page == "help_texts":
        with engine.connect() as db:
            render_help_texts_page(db)


if __name__ == "__main__":
    main()
