import streamlit as st

from verbal_reasoning_app.repository.vr_repository import (
    ensure_paper_catalog,
    init_vr_tables,
    list_active_papers,
)


MODE_HOME = "HOME"
MODE_PAPERS = "PAPERS"


st.set_page_config(
    page_title="Kiarolabs Verbal Reasoning",
    page_icon="🧠",
    layout="centered",
)

init_vr_tables()
ensure_paper_catalog()

if "vr_mode" not in st.session_state:
    st.session_state.vr_mode = MODE_HOME


def render_home():
    st.title("🧠 Verbal Reasoning Sprint")
    st.caption("Timed verbal reasoning practice for exam readiness")
    st.markdown("### Choose your level")

    levels = [
        ("BASIC", "Basic", "Build strong verbal reasoning foundations."),
        ("INTERMEDIATE", "Intermediate", "Strengthen speed, accuracy and reasoning."),
        ("MASTERY", "Mastery", "Challenge yourself with exam-ready papers."),
    ]

    for level_code, title, description in levels:
        with st.container(border=True):
            st.markdown(f"### {title}")
            st.write(description)
            st.caption("15 papers · 35 questions per paper · 30 minutes")
            if st.button(f"View {title} Papers", key=f"vr_level_{level_code}", use_container_width=True):
                st.session_state.vr_level = level_code
                st.session_state.vr_mode = MODE_PAPERS
                st.rerun()


def render_papers():
    level = st.session_state.get("vr_level")
    if not level:
        st.session_state.vr_mode = MODE_HOME
        st.rerun()
        return

    st.title(f"{level.title()} Papers")
    st.caption("Each paper contains 35 questions and has a 30-minute time limit.")

    papers = list_active_papers(level)
    for paper in papers:
        with st.container(border=True):
            st.markdown(f"### {paper['title']}")
            st.caption(
                f"{paper['question_count']} / 35 questions loaded · "
                f"{paper['duration_minutes']} minutes"
            )
            ready = paper["question_count"] == 35
            if st.button(
                "Start Paper" if ready else "Content not loaded yet",
                key=f"vr_paper_{paper['id']}",
                use_container_width=True,
                disabled=not ready,
            ):
                # Test runner is intentionally added in the next isolated increment.
                st.session_state.vr_selected_paper_id = paper["id"]
                st.info("Paper selected. Test runner will be enabled in the next build increment.")

    if st.button("← Back to Levels", use_container_width=True):
        st.session_state.vr_mode = MODE_HOME
        st.session_state.pop("vr_level", None)
        st.rerun()


def main():
    mode = st.session_state.get("vr_mode", MODE_HOME)
    if mode == MODE_HOME:
        render_home()
    elif mode == MODE_PAPERS:
        render_papers()
    else:
        st.session_state.vr_mode = MODE_HOME
        st.rerun()


if __name__ == "__main__":
    main()
