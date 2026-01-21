-- Activate spelling lessons for a specific course.
-- Replace the course_id value as needed before running.

SELECT
    lesson_id,
    lesson_name,
    is_active
FROM spelling_lessons
WHERE course_id = 9
ORDER BY lesson_id;

UPDATE spelling_lessons
SET is_active = TRUE
WHERE course_id = 9;

-- Rollback if needed.
UPDATE spelling_lessons
SET is_active = FALSE
WHERE course_id = 9;
