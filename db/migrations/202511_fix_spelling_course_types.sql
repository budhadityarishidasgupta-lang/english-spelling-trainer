-- Mark spelling courses with correct type
UPDATE courses
SET course_type = 'spelling'
WHERE course_id IN (10, 11);
