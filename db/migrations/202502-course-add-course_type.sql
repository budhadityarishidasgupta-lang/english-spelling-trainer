----------------------------------------
-- Add course_type to courses table
----------------------------------------
ALTER TABLE courses
ADD COLUMN course_type TEXT DEFAULT 'synonym';
----------------------------------------
