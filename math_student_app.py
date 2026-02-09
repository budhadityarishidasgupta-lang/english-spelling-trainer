from datetime import datetime, timedelta

import streamlit as st
from passlib.hash import bcrypt

from math_app.db import get_db_connection, init_math_practice_progress_table, init_math_tables
from math_app.repository.math_test_repo import (
    get_random_test_questions,
    create_test_session,
    end_test_session,
)
from math_app.repository.math_question_bank_repo import export_latest_question_bank_df
from math_app.repository.math_registration_repo import create_math_registration
from math_app.repository.math_attempt_repo import record_attempt
from math_app.student_practice_app import render_practice_mode

DEFAULT_PASSWORD = "Learn1234!"
MODE_HOME = "HOME"
MODE_PRACTICE = "PRACTICE"
MODE_TEST = "TEST"
MODE_TEST_RUNNER = "TEST_RUNNER"
MODE_TEST_RESULT = "TEST_RESULT"

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
    st.session_state.mode = MODE_HOME


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


def render_home():
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

        if st.button("Submit Registration"):
            if not name or not email:
                st.error("Please enter both name and email.")
            else:
                pw_hash = bcrypt.hash(DEFAULT_PASSWORD)
                create_math_registration(name, email, pw_hash)
                st.session_state["math_registration_submitted"] = True
                st.rerun()

    if not st.session_state.is_logged_in:
        return

    st.write("What would you like to do today?")

    if st.button("📝 Test Papers", use_container_width=True):
        st.session_state["mode"] = MODE_TEST
        st.rerun()

    st.markdown("---")

    st.markdown("### 🧠 Practice & Skill Builder")
    st.caption("Step-by-step learning with hints and explanations")
    
    if st.button("🧠 Practice & Skill Builder"):
        st.session_state["mode"] = MODE_PRACTICE
        st.session_state["in_practice"] = True
        st.rerun()


def render_test_home():
    st.markdown("## 📝 Test Papers")
    st.caption("50 questions · 55 minutes · No hints")

    papers = [f"Practice Paper {i}" for i in range(1, 10)]

    for idx, name in enumerate(papers, start=1):
        with st.container(border=True):
            st.markdown(f"**{name}**")
            st.caption("50 questions · 55 minutes")
            if st.button(f"Start {name}", key=f"start_test_{idx}", use_container_width=True):
                start_test()
                st.rerun()

    if st.button("⬅ Back to Home", use_container_width=True):
        st.session_state["mode"] = MODE_HOME
        st.rerun()


def start_test():
    session_id = create_test_session(50)
    question_ids = get_random_test_questions(50)

    st.session_state["test"] = {
        "session_id": session_id,
        "question_ids": question_ids,
        "index": 0,
        "start_time": datetime.utcnow(),
        "answers": {},
        "correct": 0,
    }
    st.session_state["mode"] = MODE_TEST_RUNNER


def _fetch_question_row(question_id: int):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, question_text, options_json, correct_option
                FROM math_question_bank
                WHERE id = %s
                LIMIT 1;
                """,
                (question_id,),
            )
            row = cur.fetchone()

    if not row:
        return None

    qid, question_text, options_json, correct_option = row
    options_json = options_json or {}
    return {
        "id": qid,
        "question_text": question_text,
        "option_a": options_json.get("a", ""),
        "option_b": options_json.get("b", ""),
        "option_c": options_json.get("c", ""),
        "option_d": options_json.get("d", ""),
        "correct_option": (correct_option or "").upper(),
    }


def render_test_runner():
    test = st.session_state.get("test")
    if not test:
        st.session_state["mode"] = MODE_TEST
        st.rerun()
        return

    total_questions = len(test["question_ids"])
    if total_questions == 0:
        st.warning("No active test questions are available right now.")
        st.session_state["mode"] = MODE_TEST
        return

    TOTAL_TIME = timedelta(minutes=55)
    elapsed = datetime.utcnow() - test["start_time"]
    remaining = TOTAL_TIME - elapsed

    if remaining.total_seconds() <= 0:
        finish_test()
        st.rerun()
        return

    mins, secs = divmod(int(remaining.total_seconds()), 60)
    st.markdown(f"### ⏱ Time left: {mins:02d}:{secs:02d}")

    q_idx = test["index"]
    qid = test["question_ids"][q_idx]
    row = _fetch_question_row(qid)

    if row is None:
        st.error("Unable to load this question.")
        return

    st.markdown(f"### Question {q_idx + 1} of {total_questions}")
    st.write(row["question_text"])

    options = {
        "A": row["option_a"],
        "B": row["option_b"],
        "C": row["option_c"],
        "D": row["option_d"],
    }

    choice = st.radio(
        "Select an answer",
        options=list(options.keys()),
        format_func=lambda k: f"{k}. {options[k]}",
        key=f"test_choice_{q_idx}",
    )

    if st.button("Next", use_container_width=True):
        submit_test_answer(qid, choice)
        if q_idx >= total_questions - 1:
            finish_test()
        else:
            test["index"] += 1
        st.rerun()


def submit_test_answer(question_id: int, selected: str):
    test = st.session_state["test"]
    row = _fetch_question_row(question_id)
    if row is None:
        return

    correct_opt = row["correct_option"]
    is_correct = selected == correct_opt

    record_attempt(
        session_id=test["session_id"],
        question_id=question_id,
        selected_option=selected,
        is_correct=is_correct,
    )

    if is_correct:
        test["correct"] += 1


def finish_test():
    test = st.session_state["test"]
    end_test_session(test["session_id"], test["correct"])
    st.session_state["test_result"] = {
        "score": test["correct"],
        "total": len(test["question_ids"]),
    }
    st.session_state.pop("test", None)
    st.session_state["mode"] = MODE_TEST_RESULT


def render_test_result():
    res = st.session_state.get("test_result")
    if not res:
        st.session_state["mode"] = MODE_HOME
        st.rerun()
        return

    st.markdown("## 🏁 Test Complete")
    st.markdown(f"### Score: **{res['score']} / {res['total']}**")

    if st.button("⬅ Back to Home", use_container_width=True):
        st.session_state.pop("test_result", None)
        st.session_state["mode"] = MODE_HOME
        st.rerun()
# ------------------------------------------------------------
# MODE SWITCH
# ------------------------------------------------------------
def main():
    mode = st.session_state.get("mode", MODE_HOME)

    if mode == MODE_HOME:
        render_home()
        return

    if mode == MODE_PRACTICE:
        render_practice_mode()
        return

    if mode == MODE_TEST:
        render_test_home()
        return

    if mode == MODE_TEST_RUNNER:
        render_test_runner()
        return

    if mode == MODE_TEST_RESULT:
        render_test_result()
        return

    st.session_state["mode"] = MODE_HOME
    st.rerun()


main()
