CREATE TABLE IF NOT EXISTS pending_registrations_spelling (
    id SERIAL PRIMARY KEY,
    student_name VARCHAR(200) NOT NULL,
    parent_email VARCHAR(200) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);
