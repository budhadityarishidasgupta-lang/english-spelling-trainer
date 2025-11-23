import streamlit as st
from spelling_app.services.weak_words_service import load_weak_words

def render_weak_words_admin():
    st.title("🔍 Weak Words Dashboard")
    st.markdown("View words students struggle with the most.")

    data = load_weak_words()

    if isinstance(data, dict) and "error" in data:
        st.error(str(data))
        return

    if not data:
        st.info("No weak word data available yet.")
        return

    st.dataframe(data, use_container_width=True)
