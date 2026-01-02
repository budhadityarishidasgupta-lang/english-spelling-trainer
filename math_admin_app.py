import streamlit as st
import pandas as pd

from math_app.repository.math_question_repo import insert_question

st.set_page_config(
    page_title="WordSprint Maths Admin",
    page_icon="🧮",
    layout="wide"
)

st.title("🧮 WordSprint Maths — Admin")
st.caption("Upload maths questions via CSV")

st.markdown("---")

uploaded_file = st.file_uploader(
    "Upload Maths Questions CSV",
    type=["csv"]
)

if uploaded_file is not None:
    df = pd.read_csv(uploaded_file)

    st.write("Preview of uploaded data:")
    st.dataframe(df.head())

    if st.button("Import Questions"):
        for _, row in df.iterrows():
            insert_question(
                question_id=row["question_id"],
                stem=row["stem"],
                option_a=row["option_a"],
                option_b=row["option_b"],
                option_c=row["option_c"],
                option_d=row["option_d"],
                option_e=row["option_e"],
                correct_option=row["correct_option"],
                topic=row.get("topic", ""),
                difficulty=row.get("difficulty", ""),
                asset_type=row.get("asset_type", ""),
                asset_ref=row.get("asset_ref", None),
            )

        st.success("Questions imported successfully!")
