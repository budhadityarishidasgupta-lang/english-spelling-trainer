from datetime import datetime, timezone

import streamlit as st

from verbal_reasoning_app.repository.vr_repository import ensure_paper_catalog, init_vr_tables, list_active_papers
from verbal_reasoning_app.repository.vr_test_repo import (
    create_session, finalize_session, get_draft_answers, get_paper_questions,
    get_result, get_review, get_session, save_draft_answer,
)

MODE_HOME = "HOME"
MODE_PAPERS = "PAPERS"
MODE_TEST = "TEST"
MODE_RESULT = "RESULT"

st.set_page_config(page_title="Kiarolabs Verbal Reasoning", page_icon="🧠", layout="centered")
init_vr_tables()
ensure_paper_catalog()

if "vr_mode" not in st.session_state:
    st.session_state.vr_mode = MODE_HOME


def student_id():
    # MVP identity bridge. Production shell should pass the authenticated platform user_id.
    if "vr_student_id" not in st.session_state:
        st.session_state.vr_student_id = 1
    return int(st.session_state.vr_student_id)


def render_home():
    st.title("🧠 Verbal Reasoning Sprint")
    st.caption("Timed verbal reasoning practice for exam readiness")
    for code, title, description in [
        ("BASIC", "Basic", "Build strong verbal reasoning foundations."),
        ("INTERMEDIATE", "Intermediate", "Strengthen speed, accuracy and reasoning."),
        ("MASTERY", "Mastery", "Challenge yourself with exam-ready papers."),
    ]:
        with st.container(border=True):
            st.markdown(f"### {title}")
            st.write(description)
            st.caption("15 papers · 35 questions per paper · 30 minutes")
            if st.button(f"View {title} Papers", key=f"level_{code}", use_container_width=True):
                st.session_state.vr_level = code
                st.session_state.vr_mode = MODE_PAPERS
                st.rerun()


def render_papers():
    level = st.session_state.get("vr_level")
    if not level:
        st.session_state.vr_mode = MODE_HOME
        st.rerun()
    st.title(f"{level.title()} Papers")
    st.caption("35 questions · 30 minutes · explanations after submission")
    for paper in list_active_papers(level):
        with st.container(border=True):
            st.markdown(f"### {paper['title']}")
            st.caption(f"{paper['question_count']} / 35 questions loaded · {paper['duration_minutes']} minutes")
            ready = paper["question_count"] == 35
            if st.button("Start Paper" if ready else "Content not loaded yet", key=f"paper_{paper['id']}",
                         disabled=not ready, use_container_width=True):
                session_id = create_session(student_id(), paper["id"])
                st.session_state.vr_session_id = session_id
                st.session_state.vr_question_index = 0
                st.session_state.vr_mode = MODE_TEST
                st.rerun()
    if st.button("← Back to Levels", use_container_width=True):
        st.session_state.vr_mode = MODE_HOME
        st.rerun()


def _remaining_seconds(session):
    started = session["started_at"]
    if started.tzinfo is None:
        started = started.replace(tzinfo=timezone.utc)
    elapsed = (datetime.now(timezone.utc) - started).total_seconds()
    return max(0, int(session["duration_minutes"] * 60 - elapsed))


def render_test():
    sid = st.session_state.get("vr_session_id")
    session = get_session(sid) if sid else None
    if not session or session["status"] != "IN_PROGRESS":
        st.session_state.vr_mode = MODE_RESULT if session else MODE_HOME
        st.rerun()

    questions = get_paper_questions(session["paper_id"])
    if len(questions) != 35:
        st.error("This paper is not valid: exactly 35 questions are required.")
        return

    remaining = _remaining_seconds(session)
    if remaining <= 0:
        finalize_session(sid, timed_out=True)
        st.session_state.vr_mode = MODE_RESULT
        st.rerun()

    mins, secs = divmod(remaining, 60)
    idx = max(0, min(int(st.session_state.get("vr_question_index", 0)), 34))
    q = questions[idx]
    drafts = {int(a["question_id"]): a["selected_option"] for a in get_draft_answers(sid)}

    st.caption(f"{session['title']}  ·  ⏱ {mins:02d}:{secs:02d}")
    st.progress((idx + 1) / 35)
    st.markdown(f"### Question {idx + 1} of 35")
    if q.get("question_type"):
        st.caption(q["question_type"])
    st.write(q["question_text"])

    options = {"A": q["option_a"], "B": q["option_b"], "C": q["option_c"], "D": q["option_d"]}
    current = drafts.get(int(q["question_id"]))
    choice = st.radio("Choose one answer", list(options), index=list(options).index(current) if current else None,
                      format_func=lambda x: f"{x}. {options[x]}", key=f"answer_{sid}_{q['question_id']}")
    if choice and choice != current:
        save_draft_answer(sid, q["question_id"], q["question_number"], choice)
        drafts[int(q["question_id"])] = choice

    answered = len(drafts)
    st.caption(f"Answered {answered} of 35 · Unanswered {35 - answered}")
    cols = st.columns(3)
    with cols[0]:
        if st.button("← Previous", disabled=idx == 0, use_container_width=True):
            st.session_state.vr_question_index = idx - 1
            st.rerun()
    with cols[1]:
        if st.button("Next →", disabled=idx == 34, use_container_width=True):
            st.session_state.vr_question_index = idx + 1
            st.rerun()
    with cols[2]:
        if st.button("Submit Paper", type="primary", use_container_width=True):
            finalize_session(sid)
            st.session_state.vr_mode = MODE_RESULT
            st.rerun()

    st.markdown("#### Question navigator")
    nav_cols = st.columns(7)
    for n in range(35):
        with nav_cols[n % 7]:
            qid = int(questions[n]["question_id"])
            marker = "✓" if qid in drafts else "·"
            if st.button(f"{n+1}{marker}", key=f"nav_{sid}_{n}", use_container_width=True):
                st.session_state.vr_question_index = n
                st.rerun()


def render_result():
    sid = st.session_state.get("vr_session_id")
    result = get_result(sid) if sid else None
    if not result:
        st.session_state.vr_mode = MODE_HOME
        st.rerun()
    score = int(result["correct_count"] or 0)
    total = int(result["total_questions"] or 35)
    pct = round(score * 100 / total)
    st.title("🏁 Paper Complete")
    st.markdown(f"## {score} / {total} — {pct}%")
    st.write(f"Answered: **{result['answered_count']}** · Unanswered: **{result['unanswered_count']}**")
    if result["status"] == "TIMED_OUT":
        st.warning("Time expired and the paper was submitted automatically.")

    st.markdown("### Review answers")
    for row in get_review(sid):
        label = "✅" if row["is_correct"] else "❌"
        with st.expander(f"{label} Question {row['question_number']}"):
            st.write(row["question_text"])
            opts = {"A": row["option_a"], "B": row["option_b"], "C": row["option_c"], "D": row["option_d"]}
            selected = row["selected_option"]
            st.write("Your answer:", f"{selected}. {opts[selected]}" if selected else "Unanswered")
            correct = row["correct_option"]
            st.write("Correct answer:", f"{correct}. {opts[correct]}")
            st.info(row["explanation"])

    if st.button("Back to Verbal Reasoning", use_container_width=True):
        for key in ("vr_session_id", "vr_question_index"):
            st.session_state.pop(key, None)
        st.session_state.vr_mode = MODE_HOME
        st.rerun()


def main():
    mode = st.session_state.get("vr_mode", MODE_HOME)
    {MODE_HOME: render_home, MODE_PAPERS: render_papers, MODE_TEST: render_test, MODE_RESULT: render_result}.get(mode, render_home)()


if __name__ == "__main__":
    main()
