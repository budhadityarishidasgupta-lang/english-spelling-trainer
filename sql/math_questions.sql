CREATE TABLE IF NOT EXISTS math_questions (
    id SERIAL PRIMARY KEY,
    question_id VARCHAR(50) UNIQUE NOT NULL,
    stem TEXT NOT NULL,
    option_a TEXT NOT NULL,
    option_b TEXT NOT NULL,
    option_c TEXT NOT NULL,
    option_d TEXT NOT NULL,
    option_e TEXT NOT NULL,
    correct_option CHAR(1) NOT NULL,
    topic VARCHAR(50),
    difficulty VARCHAR(20),
    asset_type VARCHAR(20),
    asset_ref TEXT,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
