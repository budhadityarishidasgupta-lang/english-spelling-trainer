CREATE TABLE IF NOT EXISTS spelling_help_content (
    section_key VARCHAR(100) PRIMARY KEY,
    content TEXT NOT NULL,
    updated_at TIMESTAMP DEFAULT NOW()
);
