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

option_labels = {
    "A": option_a,
    "B": option_b,
    "C": option_c,
    "D": option_d,
    "E": option_e,
}

st.markdown(
    """
    <style>
    .option-card button {
        width: 100%;
        text-align: left;
        border: 2px solid #e0e0e0;
        background-color: #f9fafb;
        color: #1f2937;
        border-radius: 12px;
        padding: 14px 16px;
        margin-bottom: 12px;
        font-weight: 500;
    }

    .option-card button:hover {
        border-color: #93c5fd;
        background-color: #eef2ff;
        color: #1d4ed8;
    }

    .option-card.selected button {
        border-color: #60a5fa;
        background-color: #e0f2fe;
        color: #1d4ed8;
    }

    .option-card.correct button,
    .option-card.correct button:disabled {
        border-color: #4ade80 !important;
        background-color: #ecfdf3 !important;
        color: #166534 !important;
    }

    .option-card.incorrect button,
    .option-card.incorrect button:disabled {
        border-color: #fca5a5 !important;
        background-color: #fef2f2 !important;
        color: #991b1b !important;
    }

    .option-card button:disabled {
        opacity: 1 !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

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
