from spelling_app.repository.student_repo import (
    get_student_courses,
    get_lessons_for_course,
    get_words_for_lesson,
    record_attempt,
    get_user_info,
)
from spelling_app.services.student_progress_service import get_student_dashboard_data
from typing import List, Dict, Any
import random
import streamlit as st

# --- Session State Keys ---
SESSION_KEYS = [
    "is_logged_in",
    "user_id",
    "user_name",
    "current_lesson",
    "word_list",
    "current_word_index",
]

# --- Core Service Functions ---

def initialize_session_state(st):
    """Initializes all required session state variables."""
    for key in SESSION_KEYS:
        if key not in st.session_state:
            if key == "is_logged_in":
                st.session_state[key] = False
            elif key == "user_id":
                st.session_state[key] = 0
            elif key == "user_name":
                st.session_state[key] = "Guest"
            else:
                st.session_state[key] = None

import bcrypt
from sqlalchemy import text
from shared.db import engine

def check_login(st, email: str, password: str) -> bool:
    """
    Checks login against the real users table using bcrypt hash verification.
    """
    sql = text("SELECT user_id, name, email, password_hash, is_active FROM users WHERE email=:e")

    with engine.connect() as conn:
        row = conn.execute(sql, {"e": email}).mappings().first()

    if not row:
        return False  # Email not found

    if not row["is_active"]:
        return False  # User disabled

    stored_hash = row["password_hash"]

    # Convert to bytes for bcrypt
    if isinstance(stored_hash, str):
        stored_hash = stored_hash.encode()

    if bcrypt.checkpw(password.encode(), stored_hash):
        # SUCCESS → update session state
        st.session_state.is_logged_in = True
        st.session_state.user_id = row["user_id"]
        st.session_state.user_name = row["name"]
        return True

    return False



def logout(st):
    """Clears session state and logs out the user."""
    for key in SESSION_KEYS:
        if key in st.session_state:
            del st.session_state[key]
    initialize_session_state(st)

def get_available_courses(user_id: int) -> List[Dict[str, Any]]:
    """Retrieves courses assigned to the user."""
    return get_student_courses(user_id)

def get_available_lessons(course_id: int, user_id: int) -> List[Dict[str, Any]]:
    """Retrieves lessons assigned to the user for a specific course."""
    return get_lessons_for_course(course_id, user_id)

def start_lesson(st, lesson_id: int) -> bool:
    """
    Initializes the session state for a new lesson.
    Returns True if the lesson has words, False otherwise.
    """
    words = get_words_for_lesson(lesson_id)
    
    if not words:
        return False
        
    # Shuffle the words for practice
    random.shuffle(words)
    
    st.session_state.current_lesson = lesson_id
    st.session_state.word_list = words
    st.session_state.current_word_index = 0
    
    return True

def get_current_word(st) -> Dict[str, Any]:
    """Retrieves the current word to be practiced."""
    if st.session_state.current_word_index < len(st.session_state.word_list):
        return st.session_state.word_list[st.session_state.current_word_index]
    return None

def submit_spelling_attempt(st, attempt_text: str) -> bool:
    """
    Processes a spelling attempt, records it, and advances the word index if correct.
    Returns True if the attempt was correct, False otherwise.
    """
    word_data = get_current_word(st)
    if word_data is None:
        return False
        
    correct_word = word_data["word"]
    is_correct = attempt_text.strip().lower() == correct_word.strip().lower()
    
    # Record the attempt
    record_attempt(
        user_id=st.session_state.user_id,
        item_id=word_data["item_id"],
        is_correct=is_correct,
        attempt_text=attempt_text
    )
    
    if is_correct:
        st.session_state.current_word_index += 1
        
    return is_correct

def get_dashboard_data(user_id: int) -> Dict[str, Any]:
    """
    Retrieves all data needed for the student dashboard, integrating the progress service.
    """
    return get_student_dashboard_data(user_id)
