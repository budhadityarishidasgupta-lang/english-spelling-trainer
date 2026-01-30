import streamlit as st
from passlib.hash import bcrypt

from math_app.db import get_db_connection, init_math_practice_progress_table, init_math_tables
from math_app.repository.math_question_repo import get_all_questions
from math_app.repository.math_session_repo import create_session, end_session
from math_app.repository.math_registration_repo import create_math_registration
from math_app.repository.math_attempt_repo import record_attempt
from math_app.student_practice_app import render_practice_mode

init_math_tables()
init_math_practice_progress_table()

st.set_page_config(
    page_title="WordSprint Maths",
    page_icon="🧮",
    layout="centered"
)

st.title("🧮 WordSprint Maths")
st.caption("Focused maths practice from past papers")

# ------------------------------------------------------------
# STUDENT SHELL (HOME + MODE ROUTING)
# ------------------------------------------------------------
if "mode" not in st.session_state:
    st.session_state.mode = "home"


def is_active_math_user(email: str) -> bool:
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT 1
                FROM users
                WHERE email = %s
                  AND role = 'student'
                  AND status = 'ACTIVE'
                  AND app_source = 'math'
                """,
                (email.lower(),),
            )
            return cur.fetchone() is not None
    finally:
        if conn:
            conn.close()


def authenticate_student(email: str, password: str):
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT user_id, name, password_hash
                FROM users
                WHERE email = %s
                  AND role = 'student'
                """,
                (email.lower(),),
            )
            row = cur.fetchone()
            if not row:
                return None
            user_id, name, password_hash = row
            if not bcrypt.verify(password, password_hash or ""):
                return None
            return {"user_id": user_id, "name": name}
    finally:
        if conn:
            conn.close()


def render_student_home():
    if "is_logged_in" not in st.session_state:
        st.session_state.is_logged_in = False

    if st.session_state.get("math_registration_submitted"):
        st.markdown("## ✅ Registration Received")
        st.success(
            "Thank you for registering for **WordSprint Maths**.\n\n"
            "### What happens next?\n"
            "• Your registration has been received\n"
            "• Please complete payment using the Revolut link (if not already done)\n"
            "• An admin will review and activate your account\n\n"
            "You’ll be able to log in once approval is complete."
        )

        st.info(
            "⏳ This usually takes a short time. "
            "If you’ve already paid, no further action is needed."
        )

        if st.button("⬅ Back to Login"):
            st.session_state.pop("math_registration_submitted", None)
            st.rerun()

        st.markdown("---")
        return

    student_id = st.session_state.get("student_id")
    course_id = st.session_state.get("course_id")

    st.markdown("---")
    st.subheader("Welcome 👋")

    if not st.session_state.is_logged_in:
        st.write("Please log in to continue.")
        with st.form("math_login_form"):
            email = st.text_input("Email", key="login_email")
            password = st.text_input("Password", type="password", key="login_password")
            submitted = st.form_submit_button("Login")

            if submitted:
                user = authenticate_student(email, password)
                if not user:
                    st.error("Invalid email or password.")
                    return
                if not is_active_math_user(email):
                    st.error(
                        "You are not registered for Maths yet or your account is not approved. "
                        "Please register for Maths and wait for admin approval."
                    )
                    return
                st.session_state.is_logged_in = True
                st.session_state.student_id = user["user_id"]
                st.session_state.student_name = user["name"]
                st.experimental_rerun()
        st.write("New to Maths? Register below.")

    with st.expander("📝 Register for Maths", expanded=False):
        name = st.text_input("Student Name")
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        confirm = st.text_input("Confirm Password", type="password")
        class_name = st.text_input("Class (optional)")

        if st.button("Submit Registration"):
            if password != confirm:
                st.error("Passwords do not match")
            else:
                pw_hash = bcrypt.hash(password)
                create_math_registration(name, email, pw_hash, class_name)
                st.session_state["math_registration_submitted"] = True
                st.rerun()

    if not st.session_state.is_logged_in:
        return

    st.write("What would you like to do today?")

    st.markdown("### 📝 Test Papers")
    st.caption("Timed exam-style questions")
    if st.button("Start Test Papers", use_container_width=True):
        st.session_state.mode = "test"
        st.experimental_rerun()

    st.markdown("---")

    st.markdown("### 🧠 Practice & Skill Builder")
    st.caption("Step-by-step learning with hints and explanations")
    
    if st.button("Start Practice", use_container_width=True):
        st.session_state["mode"] = "PRACTICE"
    from math_app.student_practice_app import render_practice_mode

    mode = st.session_state.get("mode", "TEST")
    
    # --- PRACTICE STICKY ROUTING ---
    if st.session_state.get("in_practice"):
        render_practice_mode()
    elif mode == "TEST":
        render_test_mode(...)
    elif mode == "PRACTICE":
        render_practice_mode()


def render_test_mode():
    questions = get_all_questions()

    if not questions:
        st.warning("No maths questions found. Please upload questions via Admin.")
        st.stop()

    if "math_session_id" not in st.session_state:
        st.session_state.math_session_id = create_session(len(questions))
        st.session_state.q_index = 0
        st.session_state.correct_count = 0
        st.session_state.feedback = None
        st.session_state.answered = False
        st.session_state.selected_option = None

    if "selected_option" not in st.session_state:
        st.session_state.selected_option = None

    q = questions[st.session_state.q_index]

    (
        qid,
        question_id,
        stem,
        option_a,
        option_b,
        option_c,
        option_d,
        option_e,
        correct_option,
        topic,
        difficulty,
        asset_type,
        asset_ref,
        hint,
        solution,
    ) = q

    st.subheader(f"Question {st.session_state.q_index + 1} of {len(questions)}")
    st.write(stem)

    if hint:
        with st.expander("💡 Show hint"):
            st.write(hint)

    option_labels = {
        "A": option_a,
        "B": option_b,
        "C": option_c,
        "D": option_d,
        "E": option_e,
    }

    st.markdown("### Choose an answer")
    cols = st.columns(2)

    for idx, (opt, text) in enumerate(option_labels.items()):
        col = cols[idx % 2]

        is_correct_choice = (
            st.session_state.feedback is not None and opt == correct_option
        )
        is_incorrect_choice = (
            st.session_state.feedback is False
            and st.session_state.selected_option == opt
        )
        is_selected = (
            st.session_state.feedback is None
            and st.session_state.selected_option == opt
        )

        classes = ["option-card"]
        if is_correct_choice:
            classes.append("correct")
        elif is_incorrect_choice:
            classes.append("incorrect")
        elif is_selected:
            classes.append("selected")

        with col:
            st.markdown(f"<div class='{ ' '.join(classes) }'>", unsafe_allow_html=True)
            label = f"{opt}. {text}"
            if st.button(
                label,
                key=f"option_{opt}",
                use_container_width=True,
                disabled=st.session_state.answered,
            ):
                st.session_state.selected_option = opt
            st.markdown("</div>", unsafe_allow_html=True)

    if st.button("Submit", disabled=st.session_state.answered):
        selected_option = st.session_state.selected_option
        if selected_option is None:
            st.warning("Please select an answer first.")
        else:
            is_correct = selected_option == correct_option

            record_attempt(
                session_id=st.session_state.math_session_id,
                question_id=qid,
                selected_option=selected_option,
                is_correct=is_correct,
            )

            if is_correct:
                st.session_state.correct_count += 1

            st.session_state.feedback = is_correct
            st.session_state.answered = True

    if st.session_state.feedback is not None:
        if st.session_state.feedback:
            st.success("✅ Correct!")
        else:
            st.error(f"❌ Incorrect. Correct answer: {correct_option}")

        if solution:
            if st.session_state.feedback:
                with st.expander("📘 See solution / explanation"):
                    st.write(solution)
            else:
                st.write(solution)

        if st.button("Next"):
            st.session_state.answered = False
            st.session_state.selected_option = None
            st.session_state.q_index += 1
            st.session_state.feedback = None

            if st.session_state.q_index >= len(questions):
                end_session(
                    st.session_state.math_session_id,
                    st.session_state.correct_count
                )

                st.markdown("---")
                st.success("🎉 Practice Complete!")
                st.write(
                    f"Final Score: **{st.session_state.correct_count} / {len(questions)}**"
                )
                st.stop()

            st.experimental_rerun()
# ------------------------------------------------------------
# MODE SWITCH
# ------------------------------------------------------------
if st.session_state.mode == "home":
    render_student_home()
elif st.session_state.mode == "test":
    render_test_mode()
elif st.session_state.mode == "practice":
    render_practice_mode(show_back_button=True)
else:
    st.session_state.mode = "home"
    st.experimental_rerun()
