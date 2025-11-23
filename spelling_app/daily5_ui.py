import streamlit as st
from spelling_app.services.daily5_service import get_daily5_words


def render_daily5():
    st.title("🗓️ Daily-5 Mode")
    st.markdown("Your daily adaptive 5-word practice session.")

    data = get_daily5_words()

    if isinstance(data, dict) and "error" in data:
        st.error(str(data))
        return

    if not data:
        st.info("No words available yet. Add spelling words first.")
        return

    st.subheader("Today's 5 Words")
    st.write(data)
