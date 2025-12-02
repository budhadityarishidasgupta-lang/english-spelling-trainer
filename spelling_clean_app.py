import streamlit as st
import bcrypt
from sqlalchemy import text
from shared.db import fetch_all, execute


st.set_page_config(
    page_title="WordSprint Spelling (Clean)",
    layout="wide",
)

# -------- Session helpers --------
def init_session():
    if "user_id" not in st.session_state:
        st.session_state.user_id = None
    if "user_name" not in st.session_state:
        st.session_state.user_name = None
    if "role" not in st.session_state:
        st.session_state.role = "student"
    if "is_logged_in" not in st.session_state:
        st.session_state.is_logged_in = False


# -------- DB / auth helpers --------
def get_user_by_email(email: str):
    rows = fetch_all(
        """
        SELECT user_id, name, email, password_hash, is_active
        FROM users
        WHERE email = :e
        """,
        {"e": email},
    )
    if not rows:
        return None

    row = rows[0]
    mapping = getattr(row, "_mapping", row)
    return mapping


def login(email: str, password: str) -> bool:
    user = get_user_by_email(email)
    if not user:
        return False
    if not user["is_active"]:
        return False

    stored_hash = user["password_hash"]
    if isinstance(stored_hash, str):
        stored_hash = stored_hash.encode()

    if bcrypt.checkpw(password.encode(), stored_hash):
        st.session_state.user_id = user["user_id"]
        st.session_state.user_name = user["name"]
        st.session_state.is_logged_in = True
        return True
    return False


def logout():
    st.session_state.user_id = None
    st.session_state.user_name = None
    st.session_state.is_logged_in = False


# -------- UI: login + simple dashboard --------
def render_login_page():
    st.title("Student Login (Clean)")
    with st.form("login_form_clean"):
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login")

        if submitted:
            email = email.strip()
            if login(email, password):
                st.success("Login successful!")
                st.experimental_rerun()
            else:
                st.error("Invalid email or password.")


def render_student_dashboard():
    st.title("Spelling Student Dashboard (Clean)")
    st.write(f"Logged in as **{st.session_state.user_name}**")
    st.write("This is just a placeholder dashboard for now.")

    if st.button("Logout"):
        logout()
        st.experimental_rerun()

def admin_reset_password_panel():
    st.sidebar.markdown("### 🔧 Admin: Reset Password (temporary)")
    email = st.sidebar.text_input("Student email for reset", key="reset_email")
    new_pw = st.sidebar.text_input("New password", type="password", key="reset_pw")
    if st.sidebar.button("Reset password now"):
        if not email or not new_pw:
            st.sidebar.error("Please enter both email and new password.")
            return
        pw_hash = bcrypt.hashpw(new_pw.encode(), bcrypt.gensalt()).decode()
        execute(
            "UPDATE users SET password_hash = :ph WHERE email = :e",
            {"ph": pw_hash, "e": email},
        )
        st.sidebar.success(f"Password reset for {email}")

def main():
    init_session()

    # TEMP: always show admin reset panel in sidebar
    admin_reset_password_panel()

    if not st.session_state.is_logged_in:
        render_login_page()
    else:
        render_student_dashboard()


if __name__ == "__main__":
    main()
