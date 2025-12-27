CREATE TABLE IF NOT EXISTS spelling_help_texts (
    id SERIAL PRIMARY KEY,
    help_key TEXT UNIQUE NOT NULL,
    title TEXT,
    body TEXT NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
