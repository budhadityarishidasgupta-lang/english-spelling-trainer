def render_practice_mode(show_back_button: bool = True):
    import streamlit as st

    from math_app.repository.math_practice_repo import (
        get_lessons_for_student,
        get_questions_for_lesson,
        get_resume_index,
        record_attempt,
    )

    st.subheader("🧠 Practice & Skill Builder")
    st.caption(
        "Lesson-based practice. One question at a time. "
        "Submit → feedback → next. Attempts are saved."
    )
    st.markdown("---")

    # ------------------------------------------------------------
    # TEMP STUDENT / COURSE SELECTOR
    # (Replace later with real auth from shell)
    # ------------------------------------------------------------
    student_id = st.number_input(
        "Student ID",
        min_value=1,
        value=int(st.session_state.get("student_id", 1)),
        step=1,
        key="practice_student_id_input",
    )

    course_id = st.number_input(
        "Course ID",
        min_value=1,
        value=int(st.session_state.get("course_id", 1)),
        step=1,
        key="practice_course_id_input",
    )

    # Persist for future shell integration
    st.session_state["student_id"] = int(student_id)
    st.session_state["course_id"] = int(course_id)

    # ------------------------------------------------------------
    # LESSON SELECTION
    # ------------------------------------------------------------
    lessons = get_lessons_for_student(course_id=int(course_id))

    if not lessons:
        st.info("No practice lessons found for this course.")
        if show_back_button:
            st.markdown("---")
            if st.button("⬅ Back to Home", use_container_width=True):
                st.session_state.mode = "home"
                st.rerun()
        return

    # Handle possible None display_name safely
    lesson_label_to_id = {
        (l.get("display_name") or f"Lesson {l['lesson_id']}"): l["lesson_id"]
        for l in lessons
    }

    lesson_label = st.selectbox(
        "Select Practice Lesson",
        options=list(lesson_label_to_id.keys()),
        key="practice_lesson_select",
    )

    lesson_id = int(lesson_label_to_id[lesson_label])

    # ------------------------------------------------------------
    # LOAD QUESTIONS
    # ------------------------------------------------------------
    questions = get_questions_for_lesson(lesson_id=int(lesson_id))

    if not questions:
        st.warning("This lesson has no questions yet.")
        if show_back_button:
            st.markdown("---")
            if st.button("⬅ Back to Home", use_container_width=True):
                st.session_state.mode = "home"
                st.rerun()
        return

    total_questions = len(questions)

    # ------------------------------------------------------------
    # SESSION STATE (NAMESPACED)
    # ------------------------------------------------------------
    if "practice_lesson_id" not in st.session_state:
        st.session_state.practice_lesson_id = None
    if "practice_q_index" not in st.session_state:
        st.session_state.practice_q_index = 0
    if "practice_submitted" not in st.session_state:
        st.session_state.practice_submitted = False
    if "practice_selected_option" not in st.session_state:
        st.session_state.practice_selected_option = None
    if "practice_feedback" not in st.session_state:
        st.session_state.practice_feedback = None

    # Reset state & apply resume when lesson changes
    if st.session_state.practice_lesson_id != lesson_id:
        st.session_state.practice_lesson_id = lesson_id
        st.session_state.practice_submitted = False
        st.session_state.practice_selected_option = None
        st.session_state.practice_feedback = None

        resume_at = get_resume_index(
            student_id=int(student_id),
            lesson_id=int(lesson_id),
        )
        st.session_state.practice_q_index = min(int(resume_at), total_questions)

    # ------------------------------------------------------------
    # RESTART PRACTICE (does NOT delete attempts)
    # ------------------------------------------------------------
    if st.button("🔄 Restart Practice", key="practice_restart"):
        st.session_state.practice_q_index = 0
        st.session_state.practice_submitted = False
        st.session_state.practice_selected_option = None
        st.session_state.practice_feedback = None
        st.rerun()

    # ------------------------------------------------------------
    # COMPLETION
    # ------------------------------------------------------------
    if st.session_state.practice_q_index >= total_questions:
        st.success("🎉 Lesson complete!")
        st.info("You may restart the lesson above to practise again.")
        if show_back_button:
            st.markdown("---")
            if st.button("⬅ Back to Home", use_container_width=True):
                st.session_state.mode = "home"
                st.rerun()
        return

    # ------------------------------------------------------------
    # CURRENT QUESTION
    # ------------------------------------------------------------
    q = questions[st.session_state.practice_q_index]

    st.subheader(f"Question {st.session_state.practice_q_index + 1} of {total_questions}")
    st.write(q["stem"])

    options = {
        "A": q["option_a"],
        "B": q["option_b"],
        "C": q["option_c"],
        "D": q["option_d"],
    }

    choice = st.radio(
        "Choose an answer:",
        options=[f"{k}) {v}" for k, v in options.items()],
        disabled=st.session_state.practice_submitted,
        key="practice_choice_radio",
    )

    selected_key = choice.split(")")[0]

    # ------------------------------------------------------------
    # SUBMIT
    # ------------------------------------------------------------
    if st.button("Submit", disabled=st.session_state.practice_submitted, key="practice_submit"):
        correct_key = (q["correct_option"] or "").strip().upper()
        is_correct = selected_key == correct_key

        record_attempt(
            student_id=int(student_id),
            lesson_id=int(lesson_id),
            question_id=int(q["question_id"]),
            selected_option=selected_key,
            is_correct=is_correct,
        )

        st.session_state.practice_submitted = True
        st.session_state.practice_selected_option = selected_key
        st.session_state.practice_feedback = {
            "is_correct": is_correct,
            "correct_key": correct_key,
            "explanation": q.get("explanation"),
        }
        st.rerun()

    # ------------------------------------------------------------
    # FEEDBACK
    # ------------------------------------------------------------
    if st.session_state.practice_submitted and st.session_state.practice_feedback:
        fb = st.session_state.practice_feedback

        if fb["is_correct"]:
            st.success("✅ Correct!")
        else:
            correct_text = options.get(fb["correct_key"], "")
            st.error(f"❌ Incorrect. Correct answer: {fb['correct_key']}) {correct_text}")

        if fb.get("explanation"):
            with st.expander("📘 Explanation"):
                st.write(fb["explanation"])

        if st.button("Next", key="practice_next"):
            st.session_state.practice_q_index += 1
            st.session_state.practice_submitted = False
            st.session_state.practice_selected_option = None
            st.session_state.practice_feedback = None
            st.rerun()

    if show_back_button:
        st.markdown("---")
        if st.button("⬅ Back to Home", use_container_width=True):
            st.session_state.mode = "home"
            st.rerun()
