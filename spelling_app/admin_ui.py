import streamlit as st
import pandas as pd
from shared.db import fetch_all, execute

from spelling_app.services.spelling_service import (
    load_course_data,
    process_csv_upload,
)

###########################################
# STUDENT ADMIN PANEL (TABBED INTERFACE)
###########################################

def render_student_admin():
    st.header("👨‍🎓 Student Administration")

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "Create Student",
        "Assign to Courses",
        "Create Class",
        "Assign Students to Class",
        "Performance Dashboard",
    ])

    #############################################
    # TAB 1 — CREATE STUDENT
    #############################################
    with tab1:
        st.subheader("Create New Student")

        name = st.text_input("Student Name")
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")

        if st.button("Create Student"):
            if not name or not email or not password:
                st.error("All fields are required.")
            else:
                execute(
                    """
                    INSERT INTO users (name, email, password, role)
                    VALUES (:n, :e, :p, 'student')
                    """,
                    {"n": name, "e": email, "p": password},
                )
                st.success(f"Student '{name}' created successfully!")


    #############################################
    # TAB 2 — ASSIGN STUDENT → COURSE
    #############################################
    with tab2:
        st.subheader("Assign Student to Course")

        from spelling_app.services.enrollment_service import (
            enroll_student_in_course,
            get_all_spelling_enrollments
        )

        students = fetch_all("SELECT id, name, email FROM users WHERE role='student' ORDER BY name;")

        if not students:
            st.warning("No students found.")
        else:
            student_map = {
                f"{s._mapping['name']} ({s._mapping['email']})": s._mapping["id"]
                for s in students
            }

            courses = load_course_data()

            course_map = {c["title"]: c["course_id"] for c in courses}

            sel_student = st.selectbox("Select Student", list(student_map.keys()))
            sel_course = st.selectbox("Select Course", list(course_map.keys()))

            if st.button("Assign Course"):
                sid = student_map[sel_student]
                cid = course_map[sel_course]
                enroll_student_in_course(sid, cid)
                st.success(f"Assigned {sel_student} → {sel_course}")


        st.subheader("Existing Enrollments")
        st.dataframe(get_all_spelling_enrollments(), use_container_width=True)


    #############################################
    # TAB 3 — CREATE CLASS
    #############################################
    with tab3:
        st.subheader("Create a Class")
        class_name = st.text_input("Class Name")

        if st.button("Create Class"):
            execute(
                "INSERT INTO classes (class_name) VALUES (:c)",
                {"c": class_name}
            )
            st.success(f"Class '{class_name}' created")


    #############################################
    # TAB 4 — ASSIGN STUDENTS TO CLASS
    #############################################
    with tab4:
        st.subheader("Assign Students to Class")

        classes = fetch_all("SELECT id, class_name FROM classes ORDER BY class_name;")
        students = fetch_all("SELECT id, name FROM users WHERE role='student' ORDER BY name;")

        if classes and students:
            class_map = {c._mapping["class_name"]: c._mapping["id"] for c in classes}
            student_map = {s._mapping["name"]: s._mapping["id"] for s in students}

            sel_class = st.selectbox("Select Class", list(class_map.keys()))
            sel_student = st.selectbox("Select Student", list(student_map.keys()))

            if st.button("Add to Class"):
                execute(
                    "INSERT INTO class_students (class_id, student_id) VALUES (:cid, :sid) ON CONFLICT DO NOTHING",
                    {"cid": class_map[sel_class], "sid": student_map[sel_student]},
                )
                st.success(f"Added {sel_student} to {sel_class}")


    #############################################
    # TAB 5 — PERFORMANCE DASHBOARD
    #############################################
    with tab5:
        st.subheader("Student Performance")

        results = fetch_all("""
            SELECT u.name AS student,
                   c.title AS course,
                   l.lesson_name,
                   a.word,
                   a.correct,
                   a.created_at
            FROM attempts a
            JOIN users u ON u.id = a.user_id
            JOIN lessons l ON l.lesson_id = a.lesson_id
            JOIN courses c ON c.course_id = l.course_id
            ORDER BY a.created_at DESC;
        """)

        st.dataframe(results, use_container_width=True)


###########################################
# SPELLING ADMIN PANEL
###########################################

def render_spelling_admin():
    st.header("📘 Spelling Administration")

    tab1, tab2, tab3, tab4 = st.tabs([
        "Create Course",
        "Create Lesson",
        "Edit Courses/Lessons",
        "Upload Words",
    ])


    #############################
    # TAB 1 — CREATE COURSE
    #############################
    with tab1:
        st.subheader("Create Spelling Course")

        title = st.text_input("Course Title")
        description = st.text_area("Course Description")

        if st.button("Create Course"):
            execute(
                """
                INSERT INTO courses (title, description, course_type)
                VALUES (:t, :d, 'spelling')
                """,
                {"t": title, "d": description},
            )
            st.success("Course created!")


    #############################
    # TAB 2 — CREATE LESSON
    #############################
    with tab2:
        st.subheader("Create Lesson Under Course")

        courses = load_course_data()

        if not courses:
            st.warning("Create a course first.")
        else:
            course_map = {c["title"]: c["course_id"] for c in courses}
            sel_course = st.selectbox("Select Course", list(course_map.keys()))

            lesson_name = st.text_input("Lesson Name")

            if st.button("Create Lesson"):
                execute(
                    """
                    INSERT INTO lessons (course_id, lesson_name)
                    VALUES (:cid, :ln)
                    """,
                    {"cid": course_map[sel_course], "ln": lesson_name},
                )
                st.success(f"Lesson '{lesson_name}' created under {sel_course}")


    #############################
    # TAB 3 — EDIT COURSES & LESSONS
    #############################
    with tab3:
        st.subheader("Edit Existing Courses & Lessons")

        courses = load_course_data()
        course_map = {c["title"]: c["course_id"] for c in courses}

        sel_course = st.selectbox("Select Course to Edit", list(course_map.keys()))
        new_title = st.text_input("New Course Title")

        if st.button("Rename Course"):
            execute(
                "UPDATE courses SET title=:t WHERE course_id=:cid",
                {"t": new_title, "cid": course_map[sel_course]},
            )
            st.success("Course updated!")


        st.subheader("Edit Lessons")

        lessons = fetch_all(
            "SELECT lesson_id, lesson_name FROM lessons WHERE course_id=:cid ORDER BY lesson_name",
            {"cid": course_map[sel_course]},
        )

        if lessons:
            lesson_map = {l._mapping["lesson_name"]: l._mapping["lesson_id"] for l in lessons}

            sel_lesson = st.selectbox("Select Lesson", list(lesson_map.keys()))
            new_name = st.text_input("New Lesson Name")

            if st.button("Rename Lesson"):
                execute(
                    "UPDATE lessons SET lesson_name=:ln WHERE lesson_id=:lid",
                    {"ln": new_name, "lid": lesson_map[sel_lesson]},
                )
                st.success("Lesson name updated!")


    #############################
    # TAB 4 — UPLOAD WORDS
    #############################
    with tab4:
        st.subheader("Upload Spelling CSV")

        courses = load_course_data()
        if not courses:
            st.warning("Create a course first.")
        else:
            course_map = {c["title"]: c["course_id"] for c in courses}
            sel_course = st.selectbox("Select Course", list(course_map.keys()))
            course_id = course_map[sel_course]

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
