import streamlit as st
import pandas as pd
from sqlalchemy import text
from datetime import date

from shared.db import engine, fetch_all, execute
from spelling_app.student_ui import render_spelling_student
from spelling_app.admin_ui import render_spelling_admin


def user_by_email(email):
    sql = text("SELECT user_id, name, email, role, is_active FROM users WHERE email=:e")
    return engine.execute(sql, {"e": email}).mappings().first()


def all_students_df():
    df_users = pd.read_sql(
        text("SELECT user_id,name,email,is_active FROM users WHERE role='student'"),
        con=engine,
    )
    df_stats = pd.read_sql(
        text(
            """
            SELECT user_id,
                   SUM(correct_attempts) AS correct_total,
                   SUM(total_attempts)   AS attempts_total,
                   SUM(CASE WHEN mastered THEN 1 ELSE 0 END) AS mastered_count,
                   MAX(last_seen)        AS last_active
            FROM word_stats GROUP BY user_id
            """
        ),
        con=engine,
    )
    df = df_users.merge(df_stats, on="user_id", how="left")
    for c in ["correct_total", "attempts_total", "mastered_count"]:
        df[c] = df[c].fillna(0).astype(int)
    return df.sort_values("name")


def create_user(name, email, password, role):
    with engine.begin() as conn:
        uid = conn.execute(
            text(
                """INSERT INTO users(name, email, password, role, is_active)
                        VALUES (:n, :e, :p, :r, TRUE)
                        RETURNING user_id"""
            ),
            {"n": name, "e": email, "p": password, "r": role},
        ).scalar()
    return uid


def set_user_active(user_id, active: bool):
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE users SET is_active=:a WHERE user_id=:u"),
            {"a": bool(active), "u": int(user_id)},
        )


def list_pending_registrations(include_processed: bool = False):
    base_sql = "SELECT pending_id, name, email, status, default_password, created_at, processed_at, created_user_id FROM pending_registrations"
    if not include_processed:
        base_sql += " WHERE processed_at IS NULL"
    base_sql += " ORDER BY created_at DESC"
    return pd.read_sql(text(base_sql), con=engine)


def mark_pending_registration_processed(pending_id: int, created_user_id: int | None = None, status: str = "registered"):
    with engine.begin() as conn:
        conn.execute(
            text(
                """UPDATE pending_registrations
                        SET processed_at = CURRENT_TIMESTAMP,
                            status=:s,
                            created_user_id=:c
                      WHERE pending_id=:p"""
            ),
            {"p": int(pending_id), "s": status, "c": created_user_id},
        )


def delete_pending_registration(pending_id: int) -> None:
    with engine.begin() as conn:
        conn.execute(
            text("DELETE FROM pending_registrations WHERE pending_id=:p"),
            {"p": int(pending_id)},
        )


def create_classroom(name: str, start_date=None):
    with engine.begin() as conn:
        cid = conn.execute(
            text(
                """INSERT INTO classes(name,start_date)
                        VALUES (:n,:d)
                        RETURNING class_id"""
            ),
            {"n": name, "d": start_date},
        ).scalar()
    return cid


def get_classrooms(include_archived: bool = False) -> pd.DataFrame:
    sql = "SELECT class_id,name,start_date,is_archived,archived_at,created_at FROM classes"
    if not include_archived:
        sql += " WHERE is_archived=FALSE"
    sql += " ORDER BY is_archived, COALESCE(start_date, '1970-01-01'::date), name"
    return pd.read_sql(text(sql), con=engine)


def get_class_students(class_id: int) -> pd.DataFrame:
    sql = text(
        """
        SELECT u.user_id, u.name, u.email, u.is_active, cs.assigned_at
        FROM class_students cs
        JOIN users u ON u.user_id = cs.user_id
        WHERE cs.class_id = :cid
        ORDER BY u.name
        """
    )
    return pd.read_sql(sql, con=engine, params={"cid": int(class_id)})


def assign_students_to_class(class_id: int, student_ids: list[int]):
    if not student_ids:
        return
    with engine.begin() as conn:
        for sid in student_ids:
            conn.execute(
                text(
                    """INSERT INTO class_students(class_id,user_id)
                            VALUES (:c,:s)
                            ON CONFLICT (class_id,user_id) DO NOTHING"""
                ),
                {"c": int(class_id), "s": int(sid)},
            )


def unassign_students_from_class(class_id: int, student_ids: list[int]):
    if not student_ids:
        return
    with engine.begin() as conn:
        for sid in student_ids:
            conn.execute(
                text("DELETE FROM class_students WHERE class_id=:c AND user_id=:s"),
                {"c": int(class_id), "s": int(sid)},
            )


def set_class_archived(class_id: int, archive: bool):
    with engine.begin() as conn:
        if archive:
            conn.execute(
                text(
                    """UPDATE classes
                        SET is_archived=TRUE,
                            archived_at=COALESCE(archived_at, CURRENT_TIMESTAMP)
                      WHERE class_id=:c"""
                ),
                {"c": int(class_id)},
            )
        else:
            conn.execute(
                text(
                    """UPDATE classes
                        SET is_archived=FALSE,
                            archived_at=NULL
                      WHERE class_id=:c"""
                ),
                {"c": int(class_id)},
            )


DEFAULT_STUDENT_PASSWORD = "Learn123!"

# Load custom CSS theme
def load_css():
    try:
        with open("static/theme.css", "r") as f:
            css = f"<style>{f.read()}</style>"
            st.markdown(css, unsafe_allow_html=True)
    except Exception as e:
        st.error(f"Could not load CSS: {e}")

def main():
    load_css()
    st.sidebar.title("Spelling Trainer")

    mode = st.sidebar.radio("Select mode", ["Student", "Admin"])

    if mode == "Student":
        render_spelling_student()
    else:
        render_admin_section()


def render_student_overview():
    st.header("Student Overview")

    df_students = all_students_df()
    filtered_students = df_students.copy()

    with st.expander("Students Summary & Search", expanded=True):
        total_students = len(df_students)
        active_students = int(df_students["is_active"].sum()) if not df_students.empty else 0
        inactive_students = total_students - active_students

        metric_cols = st.columns(3)
        metric_cols[0].metric("Total Students", total_students)
        metric_cols[1].metric("Active Students", active_students)
        metric_cols[2].metric("Inactive Students", inactive_students)

        search_q = st.text_input("Search students")
        if search_q.strip():
            mask = (
                df_students["name"].str.contains(search_q, case=False, na=False)
                | df_students["email"].str.contains(search_q, case=False, na=False)
            )
            filtered_students = df_students[mask]

        st.dataframe(filtered_students, use_container_width=True)

    render_student_creation()

    return df_students, filtered_students


def render_pending_registrations():
    st.header("Pending Student Registrations")

    pending_df = list_pending_registrations()
    if pending_df.empty:
        st.info("No pending registrations at the moment.")
        return

    pending_display = pending_df.copy()
    pending_display["created_at"] = pending_display["created_at"].astype(str)
    if "processed_at" in pending_display:
        pending_display["processed_at"] = pending_display["processed_at"].astype(str)

    st.dataframe(
        pending_display[["name", "email", "status", "default_password", "created_at"]],
        use_container_width=True,
    )

    selection = st.radio(
        "Select a registration",
        pending_df["pending_id"].tolist(),
        format_func=lambda pid: f"{pending_df.loc[pending_df['pending_id']==pid, 'name'].values[0]} ({pending_df.loc[pending_df['pending_id']==pid, 'email'].values[0]})",
    )

    action_col_create, action_col_disregard = st.columns(2)

    with action_col_create:
        create_student_clicked = st.button("Create Student", type="primary")

    with action_col_disregard:
        disregard_clicked = st.button("Disregard")

    if create_student_clicked:
        pending_row = pending_df[pending_df["pending_id"] == selection].iloc[0]
        email_lc = pending_row["email"].strip().lower()
        existing = user_by_email(email_lc)
        if existing and existing.get("role") == "student":
            mark_pending_registration_processed(int(pending_row["pending_id"]), existing.get("user_id"), status="already registered")
            set_user_active(existing.get("user_id"), True)
            st.info("This email is already registered. The student has been reactivated if necessary.")
            st.rerun()
        elif existing:
            st.warning("An account with this email already exists with a different role.")
        else:
            try:
                password = pending_row.get("default_password") or DEFAULT_STUDENT_PASSWORD
                new_user_id = create_user(pending_row["name"], email_lc, password, "student")
                if new_user_id:
                    set_user_active(new_user_id, True)
                mark_pending_registration_processed(int(pending_row["pending_id"]), new_user_id, status="registered")
                st.success("Student account created from registration.")
                st.rerun()
            except Exception as ex:
                st.error(f"Failed to create student: {ex}")

    if disregard_clicked:
        try:
            delete_pending_registration(int(selection))
            st.success("Pending registration removed.")
            st.rerun()
        except Exception as ex:
            st.error(f"Failed to remove registration: {ex}")


def render_student_creation():
    st.header("Student Creation")
    with st.form("create_student_form"):
        c1, c2, c3 = st.columns(3)
        with c1:
            s_name = st.text_input("Name")
        with c2:
            s_email = st.text_input("Email")
        with c3:
            s_pwd = st.text_input("Temp Password", value=DEFAULT_STUDENT_PASSWORD, type="password")

        if st.form_submit_button("Create Student", type="primary"):
            if s_name and s_email:
                try:
                    create_user(s_name, s_email.strip().lower(), s_pwd, "student")
                    st.success("✅ Student created successfully.")
                    st.rerun()
                except Exception as ex:
                    st.error(f"Creation failed: {ex}")
            else:
                st.warning("Please fill all fields.")


def render_classroom_management(filtered_students):
    st.header("Classroom Management")

    show_archived = st.checkbox("Show archived classes", value=False)
    df_classes = get_classrooms(include_archived=show_archived)
    if df_classes.empty:
        st.info("No classrooms yet. Create one below.")
    else:
        df_display = df_classes.copy()
        for col in ["start_date", "created_at", "archived_at"]:
            if col in df_display:
                df_display[col] = df_display[col].astype(str)
        st.dataframe(df_display, use_container_width=True)

    with st.form("adm_create_classroom"):
        c1, c2 = st.columns([2, 1])
        with c1:
            class_name = st.text_input("Class name")
        with c2:
            default_date = date.today()
            class_start = st.date_input("Commencement date", value=default_date)
        if st.form_submit_button("Create Classroom", type="primary"):
            if class_name and class_name.strip():
                create_classroom(class_name.strip(), class_start)
                st.success("Classroom created.")
                st.rerun()
            else:
                st.warning("Please provide a class name.")

    if not df_classes.empty:
        st.subheader("Classroom Roster Management")
        class_options = df_classes["class_id"].tolist()
        selected_class = st.selectbox(
            "Select classroom",
            class_options,
            format_func=lambda x: f"{df_classes.loc[df_classes['class_id']==x,'name'].values[0]}",
        )

        class_row = df_classes[df_classes["class_id"] == selected_class].iloc[0]
        start_label = class_row.get("start_date")
        status_label = "Archived" if class_row.get("is_archived") else "Active"
        st.caption(f"Status: **{status_label}** • Commences: {start_label if start_label else 'TBD'}")

        class_students_df = get_class_students(int(selected_class))
        if class_students_df.empty:
            st.info("No students assigned yet.")
        else:
            df_roster = class_students_df.copy()
            df_roster["assigned_at"] = df_roster["assigned_at"].astype(str)
            st.dataframe(df_roster[["name", "email", "is_active", "assigned_at"]], use_container_width=True)

        current_student_ids = class_students_df["user_id"].tolist() if not class_students_df.empty else []
        available_students = filtered_students[~filtered_students["user_id"].isin(current_student_ids)]

        with st.form("adm_update_class_roster"):
            add_choices = available_students["user_id"].tolist()
            add_selection = st.multiselect(
                "Add students",
                add_choices,
                format_func=lambda x: f"{available_students.loc[available_students['user_id']==x,'name'].values[0]}"
                if not available_students.empty else str(x),
            )
            remove_selection = st.multiselect(
                "Remove students",
                class_students_df["user_id"].tolist() if not class_students_df.empty else [],
                format_func=lambda x: f"{class_students_df.loc[class_students_df['user_id']==x,'name'].values[0]}"
                if not class_students_df.empty else str(x),
            )
            if st.form_submit_button("Update Classroom", type="primary"):
                assign_students_to_class(int(selected_class), add_selection)
                unassign_students_from_class(int(selected_class), remove_selection)
                st.success("Classroom roster updated.")
                st.rerun()

        archive_label = "Restore Classroom" if class_row.get("is_archived") else "Archive Classroom"
        if st.button(archive_label, type="secondary"):
            current_archived = bool(class_row.get("is_archived"))
            set_class_archived(int(selected_class), not current_archived)
            st.success("Classroom archived." if not current_archived else "Classroom restored.")
            st.rerun()


def render_admin_section():
    st.title("Admin Section")

    _, filtered_students = render_student_overview()
    render_pending_registrations()
    render_classroom_management(filtered_students)
    render_spelling_admin()

if __name__ == "__main__":
    main()
