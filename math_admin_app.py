import streamlit as st
import pandas as pd

from math_app.db import init_math_practice_progress_table, init_math_tables
from math_app.repository.math_question_repo import insert_question

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
    st.info("Coming next: approvals, classes, assignments.")

with tabs[1]:
    st.subheader("🏫 Class Management")
    st.info("Coming next: create class, assign students, auto-assign course/tests.")

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
