import sys
import os

block_path = os.path.join(os.getcwd(), "..", "synonym_legacy")
block_path = os.path.abspath(block_path)
if block_path in sys.path:
    sys.path.remove(block_path)

import streamlit as st
import pandas as pd
from shared.db import fetch_all, execute
from spelling_app.repository.registration_repo import (
    get_pending_registrations,
    delete_pending_registration,
)
from spelling_app.repository.student_admin_repo import (
    create_student_user,
    get_spelling_students,
    create_classroom,
    get_all_classes,
    archive_classroom,
    get_class_roster,
    assign_student_to_class,
    unassign_student_from_class,
)
from spelling_app.services.spelling_service import (
    load_course_data,
    process_csv_upload,
)
from spelling_app.services.help_service import get_help_text, save_help_text

# ... (render_student_admin function remains unchanged) ...

def render_spelling_admin():
    st.header("📘 Spelling Administration")

    tab_registrations, tab_students, tab_courses, tab_upload, tab_help = st.tabs([
        "Pending Registrations",
        "Students",
        "Courses",
        "Upload Words (CSV)",
        "Help Text",
    ])

    # -------------------------------------------
    # TAB — PENDING REGISTRATIONS
    # -------------------------------------------
    with tab_registrations:
        st.markdown("### Pending Spelling Registrations")
        pending = get_pending_registrations()

        if not pending:
            st.info("No pending registrations.")
        else:
            # Build pending_data safely for DataFrame + radio
            pending_data = []
            for row in pending:
                if hasattr(row, "_mapping"):
                    rid = row._mapping["id"]
                    pending_data.append(
                        {
                            "id": rid,
                            "radio": f"Select {rid}",
                            "name": row._mapping["student_name"],
                            "email": row._mapping["parent_email"],
                            "created_at": row._mapping["created_at"],
                        }
                    )
                elif isinstance(row, dict) and "id" in row:
                    rid = row["id"]
                    pending_data.append(
                        {
                            "id": rid,
                            "radio": f"Select {rid}",
                            "name": row["student_name"],
                            "email": row["parent_email"],
                            "created_at": row["created_at"],
                        }
                    )

            df_pending = pd.DataFrame(pending_data)

            if df_pending.empty:
                st.info("No valid registrations found.")
            else:
                st.markdown("Select a registration to approve or discard:")
                selected_radio = st.radio(
                    "Select Registration",
                    options=df_pending["radio"].tolist(),
                    key="reg_radio_select",
                    label_visibility="collapsed",
                )

                selected_row = df_pending[df_pending["radio"] == selected_radio].iloc[0]

                st.dataframe(
                    df_pending.drop(columns=["radio"]),
                    use_container_width=True,
                    hide_index=True,
                    column_order=["id", "name", "email", "created_at"],
                )

                if selected_row is not None:
                    rid = int(selected_row["id"])
                    name = selected_row["name"]
                    email = selected_row["email"]
                    created = selected_row["created_at"]

                    st.markdown("---")
                    st.markdown(f"**Selected:** {name} ({email})")

                    colA, colB = st.columns(2)

                    with colA:
                        if st.button("✅ Approve & Create Student", key="approve_student_btn"):
                            new_user_id = create_student_user(name, email)
                            if isinstance(new_user_id, dict) and "error" in new_user_id:
                                st.error(f"Error creating user: {new_user_id['error']}")
                            else:
                                # create_student_user already deletes from pending_registrations_spelling
                                st.success(
                                    f"Student **{name}** created successfully! (User ID: {new_user_id})"
                                )
                                st.experimental_rerun()

                    with colB:
                        if st.button("❌ Discard Request", key="reject_student_btn"):
                            delete_pending_registration(rid)
                            st.warning(f"Request for {name} discarded.")
                            st.experimental_rerun()

    # -------------------------------------------
    # TAB — STUDENTS
    # -------------------------------------------
    with tab_students:
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
                    key="sp_roster_class_select",
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
                                key="sp_add_student_select",
                            )
                            student_add_id = student_add_map.get(student_add_label)

                            if st.button(f"Add {student_add_label.split('(')[0].strip()}", key="add_student_btn"):
                                assign_student_to_class(selected_class_assign_id, student_add_id)
                                st.success(f"Student added to {selected_class_assign_label}.")
                                st.experimental_rerun()
                        else:
                            st.info("All students are already in this class or there are no unassigned students.")

                    with col_remove:
                        st.markdown("###### Remove Student")
                        students_to_remove = df_students[df_students["id"].isin(roster_ids)]
                        if not students_to_remove.empty:
                            student_remove_map = {f"{r['name']} ({r['email']})": r['id'] for _, r in students_to_remove.iterrows()}
                            student_remove_label = st.selectbox(
                                "Select Student to Remove",
                                list(student_remove_map.keys()),
                                key="sp_remove_student_select",
                            )
                            student_remove_id = student_remove_map.get(student_remove_label)

                            if st.button(f"Remove {student_remove_label.split('(')[0].strip()}", key="remove_student_btn"):
                                unassign_student_from_class(
                                    selected_class_assign_id,
                                    student_remove_id,
                                )
                                st.success(f"Student removed from {selected_class_assign_label}.")
                                st.experimental_rerun()
                        else:
                            st.info("No students in this class to remove.")

        st.markdown("---")

        st.header("📚 Assign Courses")

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
                key="acl_select_student",
            )

            sel_student_id = student_map[sel_student_label]

            st.markdown("---")

            # -------------------------
            # ASSIGN COURSES
            # -------------------------
            st.subheader("Assign Courses")
            courses = load_course_data()

            if courses:
                course_map = {c["title"]: c["course_id"] for c in courses}

                selected_courses = st.multiselect(
                    "Select courses",
                    list(course_map.keys()),
                    key="acl_course_multiselect",
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
            # VIEW CURRENT ASSIGNMENTS
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

        st.markdown("---")

        # -------------------------
        # STUDENT OVERVIEW
        # -------------------------
        st.markdown("### Spelling Student Overview")

        students = get_spelling_students()

        if not students:
            st.warning("No spelling students found.")
        else:
            df_students = pd.DataFrame([dict(r._mapping) for r in students])

            search_term = st.text_input("Search by Name or Email", key="student_search")

            if search_term:
                df_students = df_students[
                    df_students["name"].str.contains(search_term, case=False)
                    |
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
    # -------------------------------------------
    # TAB — COURSES
    # -------------------------------------------
    with tab_courses:
        st.subheader("Manage Courses")

        # --- Create Course ---
        with st.expander("➕ Create New Course", expanded=False):
            with st.form("create_course_form"):
                new_course_title = st.text_input("Course Title", key="mc_new_course_title")
                submitted = st.form_submit_button("Create Course")
                if submitted and new_course_title:
                    execute("INSERT INTO courses (title, course_type) VALUES (:t, 'spelling')", {"t": new_course_title})
                    st.success(f"Course '{new_course_title}' created.")

        # --- Edit Course ---
        with st.expander("✏️ Edit Course", expanded=False):
            courses = load_course_data()
            if not courses:
                st.warning("No courses to edit.")
            else:
                course_map = {c["title"]: c["course_id"] for c in courses}
                sel_course = st.selectbox("Select Course to Edit", list(course_map.keys()), key="mc_edit_course_select")
                new_title = st.text_input("New Course Title", key="mc_edit_course_title")

                if st.button("Rename Course", key="mc_rename_course_btn"):
                    course_id = course_map[sel_course]
                    execute("UPDATE courses SET title=:t WHERE course_id=:cid", {"t": new_title, "cid": course_id})
                    st.success("Course renamed!")

    # -------------------------------------------
    # TAB — UPLOAD WORDS
    # -------------------------------------------
    with tab_upload:
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

    # -------------------------------------------
    # TAB — HELP TEXT
    # -------------------------------------------
    with tab_help:
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

