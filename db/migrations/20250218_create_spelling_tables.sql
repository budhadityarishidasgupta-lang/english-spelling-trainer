CREATE TABLE IF NOT EXISTS spelling_items (
    item_id SERIAL PRIMARY KEY,
    word TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT spelling_items_word_key UNIQUE (word)
);

CREATE TABLE IF NOT EXISTS spelling_lesson_items (
    lesson_id INTEGER NOT NULL,
    item_id INTEGER NOT NULL,
    sort_order INTEGER,
    CONSTRAINT spelling_lesson_items_pk PRIMARY KEY (lesson_id, item_id),
    CONSTRAINT spelling_lesson_items_item_fk
        FOREIGN KEY (item_id) REFERENCES spelling_items (item_id)
        ON DELETE CASCADE
);
