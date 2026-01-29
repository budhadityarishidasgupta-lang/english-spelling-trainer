import streamlit as st
import pandas as pd

from math_app.db import init_math_practice_progress_table, init_math_tables
from math_app.repository.math_question_repo import insert_question
from math_app.repository.math_student_repo import get_active_math_students
from math_app.repository.math_registration_repo import (
    approve_math_registration,
    get_pending_math_registrations,
)
from math_app.repository.math_student_mgmt_repo import (
    add_students_to_class,
    auto_assign_course_for_class,
    create_class,
    enroll_student_in_course,
    get_class_defaults,
    list_active_math_students,
    list_classes,
    set_class_defaults,
    set_student_class,
)

init_math_tables()

st.set_page_config(
    page_title="WordSprint Maths — Admin",
    page_icon="📘",
    layout="wide",
)

st.title("📘 WordSprint Maths — Admin Console")
st.caption("Unified admin shell: Students • Classes • Practice • Test • Content • Settings")
st.markdown("---")


def render_practice_admin():
    init_math_tables()
    init_math_practice_progress_table()

    st.title("🧮 WordSprint Maths — Admin")
    st.caption("Upload maths questions via CSV")

    st.markdown("---")

    uploaded_file = st.file_uploader(
        "Upload Maths Questions CSV",
        type=["csv"]
    )

    if uploaded_file is not None:
        try:
            df = pd.read_csv(uploaded_file, encoding="utf-8")
        except UnicodeDecodeError:
            uploaded_file.seek(0)
            df = pd.read_csv(uploaded_file, encoding="latin-1")

            # 🔑 VERY IMPORTANT: normalize column names
        df.columns = (
            df.columns
              .str.strip()
              .str.lower()
        )

        st.write("Detected CSV columns:", df.columns.tolist())

        required_columns = {
            "question_id",
            "stem",
            "option_a",
            "option_b",
            "option_c",
            "option_d",
            "option_e",
            "correct_option",
        }

        missing = required_columns - set(df.columns)

        if missing:
            st.error(f"CSV is missing required columns: {', '.join(missing)}")
            st.stop()

        st.write("Preview of uploaded data:")
        st.dataframe(df.head())

        if st.button("Import Questions"):
            for _, row in df.iterrows():
                correct_option_raw = str(row["correct_option"]).strip().upper()

                correct_option = correct_option_raw[0] if correct_option_raw else ""

                insert_question(
                    question_id=row["question_id"],
                    stem=row["stem"],
                    option_a=row["option_a"],
                    option_b=row["option_b"],
                    option_c=row["option_c"],
                    option_d=row["option_d"],
                    option_e=row["option_e"],
                    correct_option=correct_option,
                    topic=row.get("topic", ""),
                    difficulty=row.get("difficulty", ""),
                    asset_type=row.get("asset_type", ""),
                    asset_ref=row.get("asset_ref", None),
                    hint=row.get("hint", ""),
                    solution=row.get("solution", ""),
                )

            st.success("Questions imported successfully!")


tabs = st.tabs(
    ["🧑‍🎓 Students", "🏫 Classes", "🧠 Practice", "📝 Test Papers", "🏠 Landing Content", "⚙️ Settings"]
)

with tabs[0]:
    st.subheader("🧑‍🎓 Student Management")

    subtabs = st.tabs(["🟡 Pending Approvals", "🟢 Active Students"])

    with subtabs[0]:
        st.markdown("### 🟡 Pending Registrations")
        pending = get_pending_math_registrations()
        if not pending:
            st.info("No pending Maths registrations.")
        else:
            for r in pending:
                reg_id, name, email, class_name, created_at = r
                cols = st.columns([3, 3, 2, 2])
                cols[0].write(name)
                cols[1].write(email)
                cols[2].write(class_name or "-")
                if cols[3].button("Approve", key=f"approve_{reg_id}"):
                    approve_math_registration(reg_id)
                    st.success(f"Approved {name}")
                    st.rerun()

    with subtabs[1]:
        st.markdown("### 🟢 Active Maths Students")
        students = list_active_math_students()
        if not students:
            st.info("No active maths students yet.")
        else:
            df = pd.DataFrame(students)
            st.dataframe(df, use_container_width=True)

            st.markdown("#### Assign Class / Course (Manual)")
            user_id = st.number_input("User ID", min_value=1, step=1)
            class_name = st.text_input("Class name (optional)")
            course_id = st.number_input("Course ID (optional)", min_value=0, step=1)

            col1, col2 = st.columns(2)
            with col1:
                if st.button("Save Class", use_container_width=True):
                    set_student_class(int(user_id), class_name.strip() or None)
                    st.success("Class updated.")
                    st.rerun()
            with col2:
                if st.button("Assign Course", use_container_width=True):
                    if int(course_id) <= 0:
                        st.warning("Enter a valid Course ID (>0).")
                    else:
                        enroll_student_in_course(int(user_id), int(course_id))
                        st.success("Course assigned.")
                        st.rerun()

        st.caption("Test paper assignment is auto-enabled by default for Maths students in this MVP.")

with tabs[1]:
    st.subheader("🏫 Class Management")

    st.markdown("### Create Class")
    new_class = st.text_input("New class name")
    if st.button("➕ Create Class"):
        if new_class.strip():
            create_class(new_class.strip())
            st.success("Class created (or already existed).")
            st.rerun()
        else:
            st.warning("Enter a class name.")

    st.markdown("---")
    st.markdown("### Existing Classes")
    classes = list_classes()
    if not classes:
        st.info("No classes created yet.")
    else:
        st.dataframe(pd.DataFrame(classes), use_container_width=True)

    st.markdown("---")
    st.markdown("### Assign Students to Class")
    class_id = st.number_input("Class ID", min_value=1, step=1)
    students = get_active_math_students()
    student_options = {
        f"{student['name']} ({student['email']})": student["id"]
        for student in students
    }
    selected_students = st.multiselect(
        "Select Students",
        options=list(student_options.keys()),
    )
    selected_student_ids = [
        student_options[label] for label in selected_students
    ]

    if st.button("👥 Add Students"):
        add_students_to_class(int(class_id), selected_student_ids)
        st.success("Students added (idempotent).")
        st.rerun()

    st.markdown("---")
    st.markdown("### Class Defaults (Auto-Assign)")
    defaults = (
        get_class_defaults(int(class_id))
        if class_id
        else {"default_course_id": None, "auto_assign_course": True, "auto_assign_tests": True}
    )

    default_course_id = st.number_input(
        "Default Course ID",
        min_value=0,
        step=1,
        value=int(defaults.get("default_course_id") or 0),
    )
    auto_assign_course = st.checkbox(
        "Auto-assign course to class students",
        value=bool(defaults.get("auto_assign_course", True)),
    )
    auto_assign_tests = st.checkbox(
        "Auto-assign tests to class students",
        value=bool(defaults.get("auto_assign_tests", True)),
    )

    if st.button("💾 Save Class Defaults"):
        set_class_defaults(
            int(class_id),
            int(default_course_id) if int(default_course_id) > 0 else None,
            bool(auto_assign_course),
            bool(auto_assign_tests),
        )
        st.success("Defaults saved.")
        st.rerun()

    if st.button("⚡ Apply Auto-Assign Now"):
        auto_assign_course_for_class(int(class_id))
        st.success("Auto-assign applied (course enrollments upserted).")
        st.rerun()

with tabs[2]:
    st.subheader("🧠 Practice Admin")
    if "render_practice_admin" in globals():
        render_practice_admin()
    else:
        st.info("Practice admin will be mounted here next.")

with tabs[3]:
    st.subheader("📝 Test Papers Admin")
    if "render_test_admin" in globals():
        render_test_admin()
    else:
        st.info("Test papers admin will be mounted here next.")

with tabs[4]:
    st.subheader("🏠 Landing Content")
    st.info("Coming next: edit landing headline/intro/registration help/payment link.")

with tabs[5]:
    st.subheader("⚙️ Settings")
    st.info("Coming next: defaults for course/tests and auto-assignment.")
