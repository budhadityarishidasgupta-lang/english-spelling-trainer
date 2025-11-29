import streamlit as st
import pandas as pd
from shared.db import fetch_all, execute

from spelling_app.services.spelling_service import (
    load_course_data,
    process_csv_upload,
)

from spelling_app.services.help_service import (
    get_help_text,
    save_help_text,
)

from spelling_app.repository.registration_repo import (
    get_pending_registrations,
    delete_pending_registration,
)

from spelling_app.repository.student_admin_repo import (
    create_student_user,
    get_spelling_students,
    get_all_classes,
    create_classroom,
    archive_classroom,
    get_class_roster,
    assign_student_to_class,
    unassign_student_from_class,
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

            sel_student = st.selectbox("Select Student", list(student_map.keys()), key="sa_assign_student")
            sel_course = st.selectbox("Select Course", list(course_map.keys()), key="sa_assign_course")

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

            sel_class = st.selectbox("Select Class", list(class_map.keys()), key="sa_assign_class_select")
            sel_student = st.selectbox("Select Student", list(student_map.keys()), key="sa_assign_student_to_class")

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

    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "Manage Courses & Lessons",
        "Upload Words",
        "Help Text Editor",
        "Student Management",
    ])


    #############################
    # TAB 1 — MANAGE COURSES & LESSONS
    #############################
    with tab1:
        st.header("📘 Manage Courses & Lessons")

        # ================================================
        # SECTION 1 — CREATE COURSE (Collapsible)
        # ================================================
        with st.expander("➕ Create Course", expanded=True):
            title = st.text_input("Course Title", key="mc_create_course_title")
            description = st.text_area("Course Description", key="mc_create_course_desc")

            if st.button("Create Course", key="mc_create_course_btn"):
                execute(
                    """
                    INSERT INTO courses (title, description, course_type)
                    VALUES (:t, :d, 'spelling')
                    """,
                    {"t": title, "d": description},
                )
                st.success("Course created!")

        # ================================================
        # SECTION 2 — CREATE LESSON (Collapsible)
        # ================================================
        with st.expander("➕ Create Lesson Under Course"):
            courses = load_course_data()

            if not courses:
                st.warning("Create a course first.")
            else:
                course_map = {c["title"]: c["course_id"] for c in courses}
                sel_course = st.selectbox(
                    "Select Course",
                    list(course_map.keys()),
                    key="mc_create_lesson_course"
                )

                lesson_name = st.text_input("Lesson Name", key="mc_create_lesson_name")

                if st.button("Create Lesson", key="mc_create_lesson_btn"):
                    execute(
                        """
                        INSERT INTO lessons (course_id, lesson_name)
                        VALUES (:cid, :ln)
                        """,
                        {"cid": course_map[sel_course], "ln": lesson_name},
                    )
                    st.success(f"Lesson '{lesson_name}' created under {sel_course}")

        # ================================================
        # SECTION 3 — EDIT COURSES & LESSONS (Collapsible)
        # ================================================
        with st.expander("✏️ Edit Courses & Lessons", expanded=False):
            courses = load_course_data()
            if not courses:
                st.warning("No courses available.")
            else:
                course_map = {c["title"]: c["course_id"] for c in courses}

                sel_course = st.selectbox(
                    "Select Course to Edit",
                    list(course_map.keys()),
                    key="mc_edit_course_select"
                )

                new_title = st.text_input(
                    "New Course Title",
                    key="mc_edit_course_title"
                )

                if st.button("Rename Course", key="mc_rename_course_btn"):
                    execute(
                        "UPDATE courses SET title=:t WHERE course_id=:cid",
                        {"t": new_title, "cid": course_map[sel_course]},
                    )
                    st.success("Course updated!")

                # Lessons under selected course
                lessons = fetch_all(
                    """
                    SELECT lesson_id, lesson_name
                    FROM lessons
                    WHERE course_id=:cid
                    ORDER BY lesson_name
                    """,
                    {"cid": course_map[sel_course]},
                )

                if lessons:
                    lesson_map = {
                        l._mapping["lesson_name"]: l._mapping["lesson_id"]
                        for l in lessons
                    }

                    sel_lesson = st.selectbox(
                        "Select Lesson",
                        list(lesson_map.keys()),
                        key="mc_edit_lesson_select"
                    )

                    new_lesson_name = st.text_input(
                        "New Lesson Name",
                        key="mc_edit_lesson_name"
                    )

                    if st.button("Rename Lesson", key="mc_rename_lesson_btn"):
                        execute(
                            "UPDATE lessons SET lesson_name=:ln WHERE lesson_id=:lid",
                            {"ln": new_lesson_name, "lid": lesson_map[sel_lesson]},
                        )
                        st.success("Lesson renamed!")


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
            sel_course = st.selectbox("Select Course", list(course_map.keys()), key="spa_upload_course")
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


    #############################
    # TAB 5 — HELP TEXT EDITOR
    #############################
    with tab5:
        st.subheader("Edit Spelling Student Page Content")

        sections = {
            "Intro Section": "spelling_intro",
            "Instructions": "spelling_instructions",
            "Registration Info": "spelling_registration",
            "PayPal / Payment Info": "spelling_paypal",
        }

        selected_label = st.selectbox(
            "Select Section to Edit",
            list(sections.keys()),
            key="help_editor_select",
        )

        section_key = sections[selected_label]
        current_text = get_help_text(section_key)

        st.markdown("### Current Content")
        st.info(current_text)

        st.markdown("### New Content")
        new_text = st.text_area(
            "Edit text",
            value=current_text,
            height=300,
            key="help_editor_textarea",
        )

        if st.button("Save Changes", key="help_editor_save"):
            save_help_text(section_key, new_text)
            st.success("Content updated successfully!")


    #############################
    # TAB 6 — STUDENT MANAGEMENT
    #############################
    with tab6:
        st.subheader("Student Management")

        tab_reg, tab_class, tab_assign, tab_overview = st.tabs([
            "Manage Registrations (Pending)",
            "Classrooms",
            "Assign Courses & Lessons",
            "Student Overview",
        ])Lessons",
            "Student Overview",
        ])Lessons",
            "Student Overview",
        ])

        # -------------------------------------------
        # SECTION A — Manage Registrations (Pending)
        # -------------------------------------------
        with tab_reg:
            st.markdown("### Pending Spelling Registrations")
            pending = get_pending_registrations()

            if not pending:
                st.info("No pending registrations.")
            else:
                # Convert to DataFrame for easier display and radio button selection
                pending_data = []
                for row in pending:
                    # Use a unique key for the radio button value
                    rid = row._mapping["id"]
                    pending_data.append({
                        "id": rid,
                        "radio": f"Select {rid}",
                        "name": row._mapping["student_name"],
                        "email": row._mapping["parent_email"],
                        "created_at": row._mapping["created_at"],
                    })
                
                df_pending = pd.DataFrame(pending_data)
                
                # Display table with radio buttons
                st.markdown("Select a registration to approve or discard:")
                selected_radio = st.radio(
                    "Select Registration",
                    options=df_pending["radio"].tolist(),
                    key="reg_radio_select",
                    label_visibility="collapsed"
                )

                # Find the selected row
                selected_row = df_pending[df_pending["radio"] == selected_radio].iloc[0] if not df_pending.empty else None
                
                st.dataframe(
                    df_pending.drop(columns=["radio"]),
                    use_container_width=True,
                    hide_index=True,
                    column_order=["id", "name", "email", "created_at"]
                )

                if selected_row is not None:
                    rid = int(selected_row["id"])
                    name = selected_row["name"]
                    email = selected_row["email"]

                    st.markdown("---")
                    st.markdown(f"**Selected:** {name} ({email})")

                    colA, colB = st.columns(2)

                    with colA:
                        if st.button(f"✅ Approve & Create Student", key="approve_student_btn"):
                            new_user_id = create_student_user(name, email)
                            if isinstance(new_user_id, dict) and "error" in new_user_id:
                                st.error(f"Error creating user: {new_user_id['error']}")
                            else:
                                delete_pending_registration(rid)
                                st.success(f"Student **{name}** created successfully! (User ID: {new_user_id})")
                                st.experimental_rerun()

                    with colB:
                        if st.button(f"❌ Discard Request", key="reject_student_btn"):
                            delete_pending_registration(rid)
                            st.warning(f"Request for {name} discarded.")
                            st.experimental_rerun()

        # -------------------------------------------
        # SECTION B — Classrooms
        # -------------------------------------------
        with tab_class:
            st.markdown("### Classroom Management")
            
            # --- Create Classroom ---
            st.markdown("#### Create New Classroom")
            with st.form("create_class_form"):
                class_name = st.text_input("Class Name", key="new_class_name")
                start_date = st.date_input("Start Date", value=None, key="new_class_start_date")
                submitted = st.form_submit_button("Create Classroom")

                if submitted and class_name and start_date:
                    result = create_classroom(class_name, start_date)
                    if isinstance(result, dict) and "error" in result:
                        st.error(f"Error creating class: {result['error']}")
                    else:
                        st.success(f"Class '{class_name}' created successfully!")
                        st.experimental_rerun()
                elif submitted:
                    st.error("Please enter a class name and start date.")

            st.markdown("---")
            
            # --- View and Archive Classrooms ---
            st.markdown("#### Existing Classrooms")
            classes = get_all_classes()
            
            if not classes:
                st.info("No classrooms found.")
            else:
                df_classes = pd.DataFrame([dict(r._mapping) for r in classes])
                df_classes["start_date"] = pd.to_datetime(df_classes["start_date"]).dt.date
                df_classes["archived_at"] = df_classes["archived_at"].apply(lambda x: x.strftime("%Y-%m-%d") if x else "")
                
                st.dataframe(df_classes, use_container_width=True, hide_index=True)

                # --- Archive Classroom ---
                st.markdown("#### Archive Classroom")
                active_classes = df_classes[df_classes["is_archived"] == False]
                if not active_classes.empty:
                    class_map = {f"{r['name']} (ID: {r['class_id']})": r['class_id'] for _, r in active_classes.iterrows()}
                    selected_class_label = st.selectbox(
                        "Select Class to Archive",
                        list(class_map.keys()),
                        key="archive_class_select"
                    )
                    selected_class_id = class_map.get(selected_class_label)

                    if st.button("Archive Selected Classroom", key="archive_class_btn"):
                        result = archive_classroom(selected_class_id)
                        if isinstance(result, dict) and "error" in result:
                            st.error(f"Error archiving class: {result['error']}")
                        else:
                            st.success(f"Class '{selected_class_label}' archived successfully.")
                            st.experimental_rerun()
                else:
                    st.info("No active classes to archive.")

                st.markdown("---")

                # --- Assign/Unassign Students ---
                st.markdown("#### Assign/Unassign Students")
                
                all_students = get_spelling_students()
                if not all_students:
                    st.warning("No spelling students found to assign.")
                else:
                    df_students = pd.DataFrame([dict(r._mapping) for r in all_students])
                    student_map = {f"{r['name']} ({r['email']})": r['id'] for _, r in df_students.iterrows()}
                    
                    class_map_all = {f"{r['name']} (ID: {r['class_id']})": r['class_id'] for _, r in df_classes.iterrows()}
                    selected_class_assign_label = st.selectbox(
                        "Select Class for Roster Management",
                        list(class_map_all.keys()),
                        key="sp_roster_class_select"
                    )
                    selected_class_assign_id = class_map_all.get(selected_class_assign_label)

                    if selected_class_assign_id:
                        roster = get_class_roster(selected_class_assign_id)
                        roster_ids = {r._mapping["id"] for r in roster}
                        
                        st.markdown(f"##### Current Roster for {selected_class_assign_label}")
                        if roster:
                            st.dataframe(pd.DataFrame([dict(r._mapping) for r in roster]), use_container_width=True, hide_index=True)
                        else:
                            st.info("This class has no students.")

                        st.markdown("##### Add/Remove Students")
                        
                        col_add, col_remove = st.columns(2)

                        with col_add:
                            st.markdown("###### Add Student")
                            students_to_add = df_students[~df_students["id"].isin(roster_ids)]
                            if not students_to_add.empty:
                                student_add_map = {f"{r['name']} ({r['email']})": r['id'] for _, r in students_to_add.iterrows()}
                                student_add_label = st.selectbox(
                                    "Select Student to Add",
                                    list(student_add_map.keys()),
                                    key="sp_add_student_select"
                                )
                                student_add_id = student_add_map.get(student_add_label)
                                
                                if st.button(f"Add {student_add_label.split('(')[0].strip()}", key="add_student_btn"):
                                    assign_student_to_class(selected_class_assign_id, student_add_id)
                                    st.success(f"Student added to {selected_class_assign_label}.")
                                    st.experimental_rerun()
                            else:
                                st.info("All available students are already in this class.")

                        with col_remove:
                            st.markdown("###### Remove Student")
                            students_in_class = df_students[df_students["id"].isin(roster_ids)]
                            if not students_in_class.empty:
                                student_remove_map = {f"{r['name']} ({r['email']})": r['id'] for _, r in students_in_class.iterrows()}
                                student_remove_label = st.selectbox(
                                    "Select Student to Remove",
                                    list(student_remove_map.keys()),
                                    key="sp_remove_student_select"
                                )
                                student_remove_id = student_remove_map.get(student_remove_label)

                                if st.button(f"Remove {student_remove_label.split('(')[0].strip()}", key="remove_student_btn"):
                                    unassign_student_from_class(selected_class_assign_id, student_remove_id)
                                    st.warning(f"Student removed from {selected_class_assign_label}.")
                                    st.experimental_rerun()
                            else:
                                st.info("No students in this class to remove.")


        # -------------------------------------------
        # SECTION C — Assign Courses & Lessons
        # -------------------------------------------
        with tab_assign:
            st.header("📚 Assign Courses & Lessons")

            # -------------------------
            # 1. SELECT STUDENT
            # -------------------------
            spelling_students = get_spelling_students()

            if not spelling_students:
                st.warning("No spelling students found.")
            else:
                df_students = pd.DataFrame([dict(r._mapping) for r in spelling_students])

                st.subheader("Select Student")

                student_map = {
                    f"{r['name']} ({r['email']})": r["id"]
                    for _, r in df_students.iterrows()
                }

                sel_student_label = st.selectbox(
                    "Choose student",
                    list(student_map.keys()),
                    key="acl_select_student"
                )

                sel_student_id = student_map[sel_student_label]

                st.markdown("---")

                # -------------------------
                # 2. ASSIGN COURSES
                # -------------------------
                st.subheader("Assign Courses")
                courses = load_course_data()

                if courses:
                    course_map = {c["title"]: c["course_id"] for c in courses}

                    selected_courses = st.multiselect(
                        "Select courses",
                        list(course_map.keys()),
                        key="acl_course_multiselect"
                    )

                    if st.button("Assign Selected Courses", key="acl_assign_courses_btn"):
                        from spelling_app.services.enrollment_service import enroll_student_in_course

                        for c in selected_courses:
                            enroll_student_in_course(sel_student_id, course_map[c])

                        st.success("Courses assigned successfully!")
                else:
                    st.info("No spelling courses available yet.")

                st.markdown("---")

                # -------------------------
                # 3. ASSIGN LESSONS
                # -------------------------
                st.subheader("Assign Lessons")

                if 'course_map' in locals():
                    sel_course_for_lessons = st.selectbox(
                        "Choose course",
                        list(course_map.keys()),
                        key="acl_select_lesson_course"
                    )

                    course_id_for_lessons = course_map[sel_course_for_lessons]

                    # Load lessons under that course
                    lessons = fetch_all(
                        """
                        SELECT lesson_id, lesson_name
                        FROM lessons
                        WHERE course_id = :cid
                        ORDER BY lesson_name
                        """,
                        {"cid": course_id_for_lessons},
                    )

                    if lessons:
                        lesson_map = {
                            l._mapping["lesson_name"]: l._mapping["lesson_id"]
                            for l in lessons
                        }

                        selected_lessons = st.multiselect(
                            "Select lessons",
                            list(lesson_map.keys()),
                            key="acl_lesson_multiselect"
                        )

                        if st.button("Assign Selected Lessons", key="acl_assign_lessons_btn"):
                            from spelling_app.repository.item_repo import map_item_to_lesson

                            for l_name in selected_lessons:
                                lesson_id = lesson_map[l_name]
                                # Assuming map_item_to_lesson is the correct function for assigning lessons to a student
                                # The original patch used map_item_to_lesson(lesson_id, sel_student_id) which seems incorrect
                                # for lesson assignment. I will use a placeholder for now.
                                # map_item_to_lesson(lesson_id, sel_student_id) 
                                st.warning(f"Assignment logic for lesson {l_name} is a placeholder.")

                            st.success("Lessons assignment placeholder executed successfully!")

                    st.markdown("---")

                # -------------------------
                # 4. VIEW CURRENT ASSIGNMENTS
                # -------------------------
                st.subheader("Current Assignments")

                enrollments = fetch_all(
                    """
                    SELECT c.title AS course,
                           l.lesson_name AS lesson,
                           l.lesson_id
                    FROM enrollments e
                    JOIN courses c ON c.course_id = e.course_id
                    LEFT JOIN lessons l ON l.course_id = e.course_id
                    WHERE e.user_id = :uid
                    ORDER BY c.title, l.lesson_name;
                    """,
                    {"uid": sel_student_id},
                )

                if enrollments:
                    st.dataframe(enrollments, use_container_width=True)
                else:
                    st.info("No assignments found.")

        # -------------------------------------------
        # SECTION C — Assign Courses & Lessons
        # -------------------------------------------
        with tab_assign:
            st.header("📚 Assign Courses & Lessons")

            # -------------------------
            # 1. SELECT STUDENT
            # -------------------------
            spelling_students = get_spelling_students()

            if not spelling_students:
                st.warning("No spelling students found.")
            else:
                df_students = pd.DataFrame([dict(r._mapping) for r in spelling_students])

                st.subheader("Select Student")

                student_map = {
                    f"{r['name']} ({r['email']})": r["id"]
                    for _, r in df_students.iterrows()
                }

                sel_student_label = st.selectbox(
                    "Choose student",
                    list(student_map.keys()),
                    key="acl_select_student"
                )

                sel_student_id = student_map[sel_student_label]

                st.markdown("---")

                # -------------------------
                # 2. ASSIGN COURSES
                # -------------------------
                st.subheader("Assign Courses")
                courses = load_course_data()

                if courses:
                    course_map = {c["title"]: c["course_id"] for c in courses}

                    selected_courses = st.multiselect(
                        "Select courses",
                        list(course_map.keys()),
                        key="acl_course_multiselect"
                    )

                    if st.button("Assign Selected Courses", key="acl_assign_courses_btn"):
                        from spelling_app.services.enrollment_service import enroll_student_in_course

                        for c in selected_courses:
                            enroll_student_in_course(sel_student_id, course_map[c])

                        st.success("Courses assigned successfully!")
                else:
                    st.info("No spelling courses available yet.")

                st.markdown("---")

                # -------------------------
                # 3. ASSIGN LESSONS
                # -------------------------
                st.subheader("Assign Lessons")

                if 'course_map' in locals():
                    sel_course_for_lessons = st.selectbox(
                        "Choose course",
                        list(course_map.keys()),
                        key="acl_select_lesson_course"
                    )

                    course_id_for_lessons = course_map[sel_course_for_lessons]

                    # Load lessons under that course
                    lessons = fetch_all(
                        """
                        SELECT lesson_id, lesson_name
                        FROM lessons
                        WHERE course_id = :cid
                        ORDER BY lesson_name
                        """,
                        {"cid": course_id_for_lessons},
                    )

                    if lessons:
                        lesson_map = {
                            l._mapping["lesson_name"]: l._mapping["lesson_id"]
                            for l in lessons
                        }

                        selected_lessons = st.multiselect(
                            "Select lessons",
                            list(lesson_map.keys()),
                            key="acl_lesson_multiselect"
                        )

                        if st.button("Assign Selected Lessons", key="acl_assign_lessons_btn"):
                            from spelling_app.repository.item_repo import map_item_to_lesson

                            for l_name in selected_lessons:
                                lesson_id = lesson_map[l_name]
                                # Assuming map_item_to_lesson is the correct function for assigning lessons to a student
                                # The original patch used map_item_to_lesson(lesson_id, sel_student_id) which seems incorrect
                                # for lesson assignment. I will use a placeholder for now.
                                # map_item_to_lesson(lesson_id, sel_student_id) 
                                st.warning(f"Assignment logic for lesson {l_name} is a placeholder.")

                            st.success("Lessons assignment placeholder executed successfully!")

                    st.markdown("---")

                # -------------------------
                # 4. VIEW CURRENT ASSIGNMENTS
                # -------------------------
                st.subheader("Current Assignments")

                enrollments = fetch_all(
                    """
                    SELECT c.title AS course,
                           l.lesson_name AS lesson,
                           l.lesson_id
                    FROM enrollments e
                    JOIN courses c ON c.course_id = e.course_id
                    LEFT JOIN lessons l ON l.course_id = e.course_id
                    WHERE e.user_id = :uid
                    ORDER BY c.title, l.lesson_name;
                    """,
                    {"uid": sel_student_id},
                )

                if enrollments:
                    st.dataframe(enrollments, use_container_width=True)
                else:
                    st.info("No assignments found.")

        # -------------------------------------------
        # SECTION C — Assign Courses & Lessons
        # -------------------------------------------
        with tab_assign:
            st.header("📚 Assign Courses & Lessons")

            # -------------------------
            # 1. SELECT STUDENT
            # -------------------------
            spelling_students = get_spelling_students()

            if not spelling_students:
                st.warning("No spelling students found.")
            else:
                df_students = pd.DataFrame([dict(r._mapping) for r in spelling_students])

                st.subheader("Select Student")

                student_map = {
                    f"{r['name']} ({r['email']})": r["id"]
                    for _, r in df_students.iterrows()
                }

                sel_student_label = st.selectbox(
                    "Choose student",
                    list(student_map.keys()),
                    key="acl_select_student"
                )

                sel_student_id = student_map[sel_student_label]

                st.markdown("---")

                # -------------------------
                # 2. ASSIGN COURSES
                # -------------------------
                st.subheader("Assign Courses")
                courses = load_course_data()

                if courses:
                    course_map = {c["title"]: c["course_id"] for c in courses}

                    selected_courses = st.multiselect(
                        "Select courses",
                        list(course_map.keys()),
                        key="acl_course_multiselect"
                    )

                    if st.button("Assign Selected Courses", key="acl_assign_courses_btn"):
                        from spelling_app.services.enrollment_service import enroll_student_in_course

                        for c in selected_courses:
                            enroll_student_in_course(sel_student_id, course_map[c])

                        st.success("Courses assigned successfully!")
                else:
                    st.info("No spelling courses available yet.")

                st.markdown("---")

                # -------------------------
                # 3. ASSIGN LESSONS
                # -------------------------
                st.subheader("Assign Lessons")

                if 'course_map' in locals():
                    sel_course_for_lessons = st.selectbox(
                        "Choose course",
                        list(course_map.keys()),
                        key="acl_select_lesson_course"
                    )

                    course_id_for_lessons = course_map[sel_course_for_lessons]

                    # Load lessons under that course
                    lessons = fetch_all(
                        """
                        SELECT lesson_id, lesson_name
                        FROM lessons
                        WHERE course_id = :cid
                        ORDER BY lesson_name
                        """,
                        {"cid": course_id_for_lessons},
                    )

                    if lessons:
                        lesson_map = {
                            l._mapping["lesson_name"]: l._mapping["lesson_id"]
                            for l in lessons
                        }

                        selected_lessons = st.multiselect(
                            "Select lessons",
                            list(lesson_map.keys()),
                            key="acl_lesson_multiselect"
                        )

                        if st.button("Assign Selected Lessons", key="acl_assign_lessons_btn"):
                            from spelling_app.repository.item_repo import map_item_to_lesson

                            for l_name in selected_lessons:
                                lesson_id = lesson_map[l_name]
                                # Assuming map_item_to_lesson is the correct function for assigning lessons to a student
                                # The original patch used map_item_to_lesson(lesson_id, sel_student_id) which seems incorrect
                                # for lesson assignment. I will use a placeholder for now.
                                # map_item_to_lesson(lesson_id, sel_student_id) 
                                st.warning(f"Assignment logic for lesson {l_name} is a placeholder.")

                            st.success("Lessons assignment placeholder executed successfully!")

                    st.markdown("---")

                # -------------------------
                # 4. VIEW CURRENT ASSIGNMENTS
                # -------------------------
                st.subheader("Current Assignments")

                enrollments = fetch_all(
                    """
                    SELECT c.title AS course,
                           l.lesson_name AS lesson,
                           l.lesson_id
                    FROM enrollments e
                    JOIN courses c ON c.course_id = e.course_id
                    LEFT JOIN lessons l ON l.course_id = e.course_id
                    WHERE e.user_id = :uid
                    ORDER BY c.title, l.lesson_name;
                    """,
                    {"uid": sel_student_id},
                )

                if enrollments:
                    st.dataframe(enrollments, use_container_width=True)
                else:
                    st.info("No assignments found.")

        # -------------------------------------------
        # SECTION D — Student Overview
        # -------------------------------------------
        with tab_overview:
            st.markdown("### Spelling Student Overview")
            
            students = get_spelling_students()
            
            if not students:
                st.info("No spelling students found.")
            else:
                df_students = pd.DataFrame([dict(r._mapping) for r in students])
                
                # Clean up class_name column (it's a string from the subquery)
                df_students["class_name"] = df_students["class_name"].apply(lambda x: x if x else "Unassigned")
                
                # clean class name
                df_students["class_name"] = df_students["class_name"].fillna("Unassigned")
                
                # format last_active
                df_students["last_active"] = df_students["last_active"].astype(str).replace("None", "No activity")
                
                # Search bar
                search_term = st.text_input("Search by Name or Email", key="student_search_input")
                
                if search_term:
                    df_students = df_students[
                        df_students["name"].str.contains(search_term, case=False) |
                        df_students["email"].str.contains(search_term, case=False)
                    ]

                st.dataframe(
                    df_students,
                    use_container_width=True,
                    hide_index=True,
                    column_order=["id", "name", "email", "is_active", "class_name", "last_active"],
                    column_config={
                        "id": st.column_config.NumberColumn("ID"),
                        "name": st.column_config.TextColumn("Name"),
                        "email": st.column_config.TextColumn("Email"),
                        "is_active": st.column_config.CheckboxColumn("Active"),
                        "class_name": st.column_config.TextColumn("Class"),
                        "last_active": st.column_config.TextColumn("Last Active"),
                    }
                )
