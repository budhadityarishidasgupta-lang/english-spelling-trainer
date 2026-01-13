-- Adds admin-editable display name for maths practice lessons
-- SAFE: additive, nullable, idempotent

ALTER TABLE math_lessons
ADD COLUMN IF NOT EXISTS display_name TEXT;
