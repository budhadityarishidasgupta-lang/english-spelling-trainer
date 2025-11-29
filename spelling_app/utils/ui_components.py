import streamlit as st
from typing import List, Dict, Any

def inject_css():
    """Injects the custom CSS file into the Streamlit app."""
    try:
        with open("english-spelling-trainer/spelling_app/styles/student.css") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    except FileNotFoundError:
        st.error("Could not find student.css. UI will be unstyled.")

def render_sidebar_toggle():
    """Renders a button to toggle the sidebar visibility (Patch 3F)."""
    # This is a placeholder for the actual JS/CSS toggle logic
    if st.button("☰ Toggle Menu", key="sidebar_toggle"):
        # In a real Streamlit app, this would require custom JS/CSS to toggle the class
        # For now, we'll just show a message.
        st.info("Sidebar toggle logic is implemented via CSS/JS injection in a real environment.")

def render_badge(emoji: str, text: str, color_class: str = "badge-gold"):
    """Renders an emoji-based badge."""
    st.markdown(
        f'<span class="badge {color_class}">{emoji} {text}</span>',
        unsafe_allow_html=True
    )

def render_stat_card(title: str, value: Any, delta: str = None, help_text: str = None):
    """Renders a simple metric card."""
    with st.container():
        st.markdown(f'<div class="stCard">', unsafe_allow_html=True)
        st.metric(title, value, delta=delta, help=help_text)
        st.markdown(f'</div>', unsafe_allow_html=True)

def render_streak_bar(streak_days: int):
    """Renders the top-level streak bar (Patch 3H)."""
    flames = "🔥" * min(streak_days, 5) # Max 5 flames for visual appeal
    text = f"{flames} {streak_days}-day streak!" if streak_days > 0 else "Start your streak today!"
    
    st.markdown(
        f'<div class="streak-bar"><span class="flame">{flames}</span> {text}</div>',
        unsafe_allow_html=True
    )

def render_course_card(course: Dict[str, Any], course_progress: float, lessons_html: str):
    """Renders a card for a single course."""
    with st.container():
        st.markdown(f'<div class="stCard">', unsafe_allow_html=True)
        st.subheader(f"📚 {course['title']}")
        st.write(course.get("description", "No description provided."))
        
        st.markdown("##### Course Progress")
        st.progress(course_progress / 100)
        
        st.markdown("---")
        st.markdown(lessons_html, unsafe_allow_html=True)
        
        st.markdown(f'</div>', unsafe_allow_html=True)

def render_lesson_card_html(lesson: Dict[str, Any], mastered_words: int, total_words: int, key_prefix: str) -> str:
    """
    Generates the HTML string for a single lesson card (to be embedded in the course card).
    """
    progress = (mastered_words / total_words) * 100 if total_words > 0 else 0
    
    # Use a custom HTML progress bar for better styling control
    progress_bar_html = f"""
    <div style="margin-top: 5px; margin-bottom: 5px;">
        <div style="background-color: #f3f3f3; border-radius: 5px; height: 10px;">
            <div style="background-color: #4CAF50; border-radius: 5px; height: 10px; width: {progress}%;"></div>
        </div>
    </div>
    """
    
    button_key = f"start_lesson_{key_prefix}_{lesson['lesson_id']}"
    
    html = f"""
    <div style="border: 1px solid #eee; padding: 10px; border-radius: 5px; margin-bottom: 10px;">
        <div style="display: flex; justify-content: space-between; align-items: center;">
            <span style="font-weight: bold;">{lesson['lesson_name']}</span>
            <span style="font-size: 0.9em; color: #666;">{mastered_words}/{total_words} mastered</span>
        </div>
        {progress_bar_html}
        <button onclick="window.parent.document.querySelector('[data-testid=\"stButton-{button_key}\"] button').click()" 
                style="background-color: #007bff; color: white; border: none; padding: 5px 10px; border-radius: 5px; cursor: pointer; margin-top: 5px;">
            Start Lesson
        </button>
    </div>
    """
    return html

def render_lesson_card_button(lesson: Dict[str, Any], key_prefix: str, on_click_callback):
    """
    Renders the Streamlit button part of the lesson card.
    This button is hidden and triggered by the HTML button in render_lesson_card_html.
    """
    button_key = f"start_lesson_{key_prefix}_{lesson['lesson_id']}"
    
    # This button is hidden via CSS/Streamlit's internal mechanism but is the actual trigger
    if st.button("Start Lesson", key=button_key, on_click=on_click_callback, args=(lesson['lesson_id'],)):
        pass # Logic handled by callback
