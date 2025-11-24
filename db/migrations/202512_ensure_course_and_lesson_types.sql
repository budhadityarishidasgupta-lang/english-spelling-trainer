-----------------------------------------------------
-- Ensure course_type column exists
ALTER TABLE courses
ADD COLUMN IF NOT EXISTS course_type TEXT DEFAULT 'synonym';

-----------------------------------------------------
-- Ensure lesson_type column exists
ALTER TABLE lessons
ADD COLUMN IF NOT EXISTS lesson_type TEXT DEFAULT 'synonym';

-----------------------------------------------------
-- Ensure sort_order column exists
ALTER TABLE lessons
ADD COLUMN IF NOT EXISTS sort_order INTEGER;

-----------------------------------------------------
-- Mark spelling courses correctly
UPDATE courses
SET course_type = 'spelling'
WHERE course_id IN (10, 11);

-----------------------------------------------------
-- Mark lessons belonging to spelling courses
UPDATE lessons
SET lesson_type = 'spelling'
WHERE course_id IN (10, 11);
