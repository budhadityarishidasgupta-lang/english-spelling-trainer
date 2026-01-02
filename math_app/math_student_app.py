import streamlit as st

st.set_page_config(
    page_title="WordSprint Maths",
    page_icon="🧮",
    layout="centered"
)

st.title("🧮 WordSprint Maths")
st.caption("Focused maths practice from past papers")

st.markdown("---")

st.info(
    "Maths app scaffold created successfully.\n\n"
    "Next steps:\n"
    "- Admin CSV upload\n"
    "- Full paper practice flow\n"
    "- Attempt tracking"
)
