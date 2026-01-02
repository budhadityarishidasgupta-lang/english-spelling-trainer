CREATE TABLE IF NOT EXISTS math_attempts (
    id SERIAL PRIMARY KEY,
    session_id INTEGER NOT NULL,
    question_id INTEGER NOT NULL,
    selected_option CHAR(1) NOT NULL,
    is_correct BOOLEAN NOT NULL,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
