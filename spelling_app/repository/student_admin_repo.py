from shared.db import fetch_all, execute
from datetime import date
import hashlib

# --- Hashing Utility (for temporary password) ---

def _hash_password(password: str) -> str:
    """Hashes a password using SHA-256 for temporary storage."""
    return hashlib.sha256(password.encode()).hexdigest()

# --- User Management ---

def create_student_user(name: str, email: str, temp_password: str = "Learn123!") -> int | dict:
    """
    Creates a new student user and assigns them to the 'spelling' category.
    Returns the new user_id or an error dict.
    """
    hashed_password = _hash_password(temp_password)
    
    # 1. Insert into users table
    result = execute(
        """
        INSERT INTO users (name, email, password, role)
        VALUES (:n, :e, :p, 'student')
        RETURNING id
        """,
        {
            "n": name,
            "e": email,
            "p": hashed_password,
        },
    )

    if isinstance(result, dict) and "error" in result:
        return result

    # The execute function for INSERT RETURNING should return a list of rows or an error dict.
    # Assuming it returns the ID directly or a list containing the ID.
    new_user_id = result[0]["id"] if isinstance(result, list) and result else result

    # 2. Insert into user_categories table
    category_result = execute(
        """
        INSERT INTO user_categories (user_id, category)
        VALUES (:uid, 'spelling')
        """,
        {"uid": new_user_id},
    )

    if isinstance(category_result, dict) and "error" in category_result:
        # In a real app, we would roll back the user creation here.
        return category_result

    return new_user_id

def get_spelling_students():
    """
    Retrieves all students in the 'spelling' category with their class name.
    """
    rows = fetch_all(
        """
        SELECT u.id, u.name, u.email, u.is_active,
               (SELECT name FROM classes cl 
                JOIN class_students cs ON cs.class_id = u.id
                WHERE cs.student_id = u.id LIMIT 1) AS class_name
        FROM users u
        JOIN user_categories c ON c.user_id = u.id
        WHERE c.category = 'spelling'
        ORDER BY u.name;
        """
    )
    return rows

# --- Classroom Management ---

def get_all_classes():
    """
    Retrieves all classrooms.
    """
    rows = fetch_all(
        """
        SELECT class_id, name, start_date, is_archived, archived_at
        FROM classes
        ORDER BY is_archived ASC, start_date DESC
        """
    )
    return rows

def create_classroom(name: str, start_date: date) -> int | dict:
    """
    Creates a new classroom.
    """
    result = execute(
        """
        INSERT INTO classes (name, start_date)
        VALUES (:n, :sd)
        RETURNING class_id
        """,
        {"n": name, "sd": start_date},
    )
    return result[0]["class_id"] if isinstance(result, list) and result else result

def archive_classroom(class_id: int) -> dict | None:
    """
    Archives a classroom.
    """
    return execute(
        """
        UPDATE classes
        SET is_archived = TRUE, archived_at = NOW()
        WHERE class_id = :id
        """,
        {"id": class_id},
    )

def get_class_roster(class_id: int):
    """
    Retrieves the roster for a specific class.
    """
    rows = fetch_all(
        """
        SELECT u.id, u.name, u.email
        FROM users u
        JOIN class_students cs ON cs.student_id = u.id
        WHERE cs.class_id = :cid
        ORDER BY u.name
        """,
        {"cid": class_id},
    )
    return rows

def assign_student_to_class(class_id: int, student_id: int) -> dict | None:
    """
    Assigns a student to a class.
    """
    return execute(
        """
        INSERT INTO class_students (class_id, student_id)
        VALUES (:cid, :sid)
        ON CONFLICT (class_id, student_id) DO NOTHING
        """,
        {"cid": class_id, "sid": student_id},
    )

def unassign_student_from_class(class_id: int, student_id: int) -> dict | None:
    """
    Unassigns a student from a class.
    """
    return execute(
        """
        DELETE FROM class_students
        WHERE class_id = :cid AND student_id = :sid
        """,
        {"cid": class_id, "sid": student_id},
    )
