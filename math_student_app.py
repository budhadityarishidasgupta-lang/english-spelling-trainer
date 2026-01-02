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
    solution,
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
    key="selected_option",
    disabled=st.session_state.answered,
)

if st.button("Submit", disabled=st.session_state.answered):
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
        st.session_state.answered = True

if st.session_state.feedback is not None:
    if st.session_state.feedback:
        st.success("✅ Correct!")
    else:
        st.error(f"❌ Incorrect. Correct answer: {correct_option}")

    st.write(f"Correct answer: {correct_option}")

    option_labels = {
        "A": option_a,
        "B": option_b,
        "C": option_c,
        "D": option_d,
        "E": option_e,
    }

    st.markdown("### Answer options")
    for opt, text in option_labels.items():
        if opt == correct_option:
            bg = "#e8f5e9"
            color = "#1b5e20"
            prefix = "✅"
        elif st.session_state.selected_option == opt:
            bg = "#ffebee"
            color = "#b71c1c"
            prefix = "⚠️"
        else:
            bg = "#f5f5f5"
            color = "#424242"
            prefix = ""

        st.markdown(
            f"<div style='padding: 10px; border-radius: 8px; margin-bottom: 8px; background-color: {bg}; color: {color}; border: 1px solid #e0e0e0;'>"
            f"{prefix} <strong>{opt}.</strong> {text}"
            "</div>",
            unsafe_allow_html=True,
        )

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
