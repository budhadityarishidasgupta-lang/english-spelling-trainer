CREATE TABLE IF NOT EXISTS spelling_enrollments (
    id SERIAL PRIMARY KEY,
    student_id INTEGER NOT NULL,
    course_id INTEGER NOT NULL,
    assigned_on TIMESTAMP DEFAULT NOW(),

    UNIQUE(student_id, course_id),

    FOREIGN KEY (student_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (course_id) REFERENCES courses(course_id) ON DELETE CASCADE
);
