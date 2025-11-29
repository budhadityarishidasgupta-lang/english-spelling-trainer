from spelling_app.repository.student_repo import (
    get_user_stats_detailed,
    get_lesson_progress_detailed,
    get_course_progress_detailed,
)
from typing import List, Dict, Any
from datetime import datetime, timedelta

# --- Badge Definitions ---
BADGE_DEFINITIONS = [
    {"key": "accuracy_gold", "emoji": "🏅", "text": "Accuracy Ace (80%+)", "threshold": 0.80, "stat": "accuracy"},
    {"key": "accuracy_silver", "emoji": "🥈", "text": "Accuracy Pro (70%+)", "threshold": 0.70, "stat": "accuracy"},
    {"key": "mastery_star", "emoji": "⭐", "text": "Word Master (20+ words)", "threshold": 20, "stat": "mastered_words"},
    {"key": "lesson_completer", "emoji": "🎯", "text": "Lesson Completer (5 lessons)", "threshold": 5, "stat": "lessons_completed"},
    {"key": "streak_bronze", "emoji": "🥉", "text": "3-Day Streak", "threshold": 3, "stat": "current_streak"},
    {"key": "streak_silver", "emoji": "🥈", "text": "5-Day Streak", "threshold": 5, "stat": "current_streak"},
    {"key": "streak_gold", "emoji": "🥇", "text": "7-Day Streak", "threshold": 7, "stat": "current_streak"},
]

def calculate_current_streak(attempts_by_day: Dict[str, int]) -> int:
    """
    Calculates the current consecutive day streak based on attempts.
    """
    today = datetime.now().date()
    streak = 0
    
    # Check today and yesterday first
    for i in range(7): # Check up to the last 7 days
        check_date = today - timedelta(days=i)
        date_str = check_date.strftime("%Y-%m-%d")
        
        if date_str in attempts_by_day and attempts_by_day[date_str] > 0:
            streak += 1
        elif i == 0: # If no attempts today, check yesterday
            continue
        else: # Gap found
            break
            
    return streak

def get_student_dashboard_data(user_id: int) -> Dict[str, Any]:
    """
    Aggregates all data needed for the student dashboard.
    """
    stats = get_user_stats_detailed(user_id)
    
    # 1. Calculate Streak
    attempts_by_day = stats.get("attempts_by_day", {})
    current_streak = calculate_current_streak(attempts_by_day)
    
    # 2. Calculate Badges
    user_badges = []
    
    # Prepare stats for badge checking
    accuracy = stats.get("accuracy", 0)
    mastered_words = stats.get("mastered_words", 0)
    lessons_completed = stats.get("lessons_completed", 0)
    
    for badge in BADGE_DEFINITIONS:
        stat_value = 0
        if badge["stat"] == "accuracy":
            stat_value = accuracy
        elif badge["stat"] == "mastered_words":
            stat_value = mastered_words
        elif badge["stat"] == "lessons_completed":
            stat_value = lessons_completed
        elif badge["stat"] == "current_streak":
            stat_value = current_streak
            
        if stat_value >= badge["threshold"]:
            user_badges.append({
                "emoji": badge["emoji"],
                "text": badge["text"],
                "key": badge["key"]
            })
            
    # 3. Final Data Structure
    dashboard_data = {
        "total_attempts": stats.get("total_attempts", 0),
        "correct_attempts": stats.get("correct_attempts", 0),
        "accuracy": accuracy,
        "mastered_words": mastered_words,
        "current_streak": current_streak,
        "badges": user_badges,
        "attempts_by_day": attempts_by_day,
    }
    
    return dashboard_data

def get_lesson_progress_data(user_id: int, lesson_id: int) -> Dict[str, Any]:
    """
    Retrieves detailed progress for a single lesson.
    """
    return get_lesson_progress_detailed(user_id, lesson_id)

def get_course_progress_data(user_id: int, course_id: int) -> Dict[str, Any]:
    """
    Retrieves detailed progress for a single course.
    """
    return get_course_progress_detailed(user_id, course_id)
