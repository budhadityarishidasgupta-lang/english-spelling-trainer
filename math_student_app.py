import streamlit as st

from math_app.repository.math_question_repo import get_all_questions
from math_app.repository.math_session_repo import create_session, end_session
from math_app.repository.math_attempt_repo import record_attempt

st.set_page_config(
    page_title="WordSprint Maths",
    page_icon="🧮",
    layout="centered"
)

st.title("🧮 WordSprint Maths")
st.caption("Focused maths practice from past papers")

st.markdown("---")

questions = get_all_questions()

if not questions:
    st.warning("No maths questions found. Please upload questions via Admin.")
    st.stop()

if "math_session_id" not in st.session_state:
    st.session_state.math_session_id = create_session(len(questions))
    st.session_state.q_index = 0
    st.session_state.correct_count = 0
    st.session_state.feedback = None

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
) = q

st.subheader(f"Question {st.session_state.q_index + 1} of {len(questions)}")
st.write(stem)

selected = st.radio(
    "Choose an answer:",
    ["A", "B", "C", "D", "E"],
    format_func=lambda x: {
        "A": f"A. {option_a}",
        "B": f"B. {option_b}",
        "C": f"C. {option_c}",
        "D": f"D. {option_d}",
        "E": f"E. {option_e}",
    }[x],
    index=None,
)

if st.button("Submit"):
    if selected is None:
        st.warning("Please select an answer first.")
    else:
        is_correct = selected == correct_option

        record_attempt(
            session_id=st.session_state.math_session_id,
            question_id=qid,
            selected_option=selected,
            is_correct=is_correct,
        )

        if is_correct:
            st.session_state.correct_count += 1

        st.session_state.feedback = is_correct

if st.session_state.feedback is not None:
    if st.session_state.feedback:
        st.success("✅ Correct!")
    else:
        st.error(f"❌ Incorrect. Correct answer: {correct_option}")

    if st.button("Next"):
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
