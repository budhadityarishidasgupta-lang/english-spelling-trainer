import streamlit as st

st.set_page_config(
    page_title="WordSprint Maths Admin",
    page_icon="🧮",
    layout="wide"
)

st.title("🧮 WordSprint Maths — Admin")
st.caption("Upload and manage maths practice papers")

st.markdown("---")

st.warning(
    "Maths admin scaffold created.\n\n"
    "Next steps:\n"
    "- CSV upload & validation\n"
    "- Question preview\n"
    "- Idempotent import into math_* tables"
)
