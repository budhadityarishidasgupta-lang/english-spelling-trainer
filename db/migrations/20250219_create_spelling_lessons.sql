CREATE TABLE IF NOT EXISTS spelling_lessons (
    lesson_id SERIAL PRIMARY KEY,
    course_id INTEGER NOT NULL,
    lesson_name TEXT NOT NULL,
    sort_order INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (course_id, lesson_name),
    FOREIGN KEY (course_id) REFERENCES courses(course_id) ON DELETE CASCADE
);

-- Clear existing lesson items to prevent FK constraint errors (Critical 3)
DELETE FROM spelling_lesson_items;

ALTER TABLE spelling_lesson_items
ADD CONSTRAINT spelling_lesson_items_lesson_fk
FOREIGN KEY (lesson_id)
REFERENCES spelling_lessons (lesson_id)
ON DELETE CASCADE;
