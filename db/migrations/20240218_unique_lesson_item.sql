ALTER TABLE spelling_lesson_items
ADD CONSTRAINT unique_lesson_item UNIQUE (lesson_id, item_id);
