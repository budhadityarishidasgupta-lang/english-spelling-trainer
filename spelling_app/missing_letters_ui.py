import streamlit as st
from spelling_app.services.missing_letters_service import get_missing_letter_words


def render_missing_letters():
    st.title("🔡 Missing-Letter Mode")
    st.markdown("Practice spelling with missing letters.")

    data = get_missing_letter_words()

    if isinstance(data, dict) and "error" in data:
        st.error(str(data))
        return

    if not data:
        st.info("No words available yet.")
        return

    st.subheader("Words prepared for Missing-Letter Mode:")
    st.write(data)
