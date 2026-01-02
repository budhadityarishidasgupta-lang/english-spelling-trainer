import streamlit as st

from math_app.repository.math_question_repo import get_all_questions

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
else:
    q = questions[0]

    (
        _id,
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

    st.subheader(f"Question {question_id}")
    st.write(stem)

    selected = st.radio(
        "Choose an answer:",
        options=["A", "B", "C", "D", "E"],
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
            if selected == correct_option:
                st.success("✅ Correct!")
            else:
                st.error(f"❌ Incorrect. The correct answer is {correct_option}.")
