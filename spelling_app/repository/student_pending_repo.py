# spelling_app/repository/student_pending_repo.py

from typing import List, Dict, Optional

from shared.db import fetch_all
from spelling_app.repository.registration_repo import (
    create_pending_registration as create_pending_registration_with_token,
    generate_registration_token,
)
from passlib.hash import bcrypt


DEFAULT_STUDENT_PASSWORD = "Learn123!"


def _to_dict(row):
    if row is None:
        return None
    if isinstance(row, dict):
        return row
    if hasattr(row, "_mapping"):
        return dict(row._mapping)
    try:
        return dict(row)
    except Exception:
        return None


def _to_list(rows):
    if rows is None:
        return []
    if isinstance(rows, list):
        return rows
    if hasattr(rows, "all"):
        try:
            return rows.all()
        except Exception:
            return []
    return []


# -------------------------
# Pending registration CRUD
# -------------------------

def create_pending_registration(student_name: str, email: str, token: str = None) -> Dict:
    """
    Create a pending registration entry.
    Returns dict with either {'id': ...} or {'error': '...'}.
    """
    reg_token = token or generate_registration_token()

    rows = create_pending_registration_with_token(
        student_name=student_name, email=email, token=reg_token
    )

    if isinstance(rows, dict):  # DB error
        return rows

    rows = _to_list(rows)
    
    if not rows:
        # ON CONFLICT path: email already exists either as pending or user
        return {"error": "A registration with this email already exists or is already a user."}

    row = rows[0]
    if hasattr(row, "_mapping"):
        return {"id": row._mapping.get("id")}
    if isinstance(row, dict):
        return {"id": row.get("id")}
    try:
        return {"id": row[0]}
    except Exception:
        return {"error": "Could not read pending registration ID."}


def list_pending_registrations() -> List[Dict]:
    """
    Return all pending registrations ordered by requested_at.
    """
    sql = """
        SELECT id, student_name, email, requested_at
        FROM spelling_pending_registrations
        ORDER BY requested_at ASC;
    """
    rows = fetch_all(sql)

    if isinstance(rows, dict):
        return []

    rows = _to_list(rows)
    return [_to_dict(r) for r in rows]


def delete_pending_registration(pending_id: int) -> Dict:
    """
    Remove a pending registration (used for 'disregard' or after approve).
    """
    sql = """
        DELETE FROM spelling_pending_registrations
        WHERE id = :pid;
    """
    return fetch_all(sql, {"pid": pending_id})


# -------------------------
# User creation from pending
# -------------------------

def _hash_password(plain: str) -> str:
    return bcrypt.hash(plain)


def _get_user_by_email(email: str) -> Optional[Dict]:
    rows = fetch_all(
        """
        SELECT user_id, name, email, role
        FROM users
        WHERE LOWER(email) = LOWER(:email)
        LIMIT 1;
        """,
        {"email": email},
    )
    if isinstance(rows, dict):
        return None
    rows = _to_list(rows)
    if not rows:
        return None
    return _to_dict(rows[0])


def _create_student_user(name: str, email: str) -> Dict:
    """
    Insert into users table with default password Learn123! and role='student'.
    Returns {'user_id': ...} or {'error': '...'}.
    """

    APP_SOURCE = "spelling"

    # HARD GUARD – do not allow silent mis-tagging
    if APP_SOURCE != "spelling":
        raise RuntimeError("Invalid app_source for spelling student creation")

    print(f"[SPELLING_USER_CREATE] email={email}, app_source={APP_SOURCE}")

    password_hash = _hash_password(DEFAULT_STUDENT_PASSWORD)

    sql = """
        INSERT INTO users (
            name,
            email,
            password_hash,
            role,
            status,
            is_active,
            app_source
        )
        VALUES (
            :name,
            :email,
            :password_hash,
            'student',
            'ACTIVE',
            TRUE,
            'spelling'
        )
        RETURNING user_id;
    """

    rows = fetch_all(
        sql,
        {
            "name": name,
            "email": email,
            "password_hash": password_hash,
        },
    )

    if isinstance(rows, dict):
        return rows

    rows = _to_list(rows)
    if not rows:
        return {"error": "User creation returned no rows."}

    row = rows[0]
    if hasattr(row, "_mapping"):
        return {"user_id": row._mapping.get("user_id")}
    if isinstance(row, dict):
        return {"user_id": row.get("user_id")}
    try:
        return {"user_id": row[0]}
    except Exception:
        return {"error": "Could not read user_id from INSERT."}


def approve_pending_registration(pending_id: int) -> Dict:
    """
    Approve a pending registration:
      1) Look up pending row
      2) If user already exists in users: error
      3) Create student user with default password
      4) Delete pending registration
    Returns summary dict.
    """
    # 1) Fetch pending row
    rows = fetch_all(
        """
        SELECT id, student_name, email
        FROM spelling_pending_registrations
        WHERE id = :pid;
        """,
        {"pid": pending_id},
    )

    if isinstance(rows, dict):
        return rows

    rows = _to_list(rows)
    if not rows:
        return {"error": "Pending registration not found."}

    pending = _to_dict(rows[0])
    name = pending["student_name"]
    email = pending["email"]

    # 2) Check if user already exists
    existing_user = _get_user_by_email(email)
    if existing_user:
        # Delete pending because user is already active
        delete_pending_registration(pending_id)
        return {
            "info": "User already exists; pending registration removed.",
            "user_id": existing_user["user_id"],
        }

    # 3) Create new user
    created_user = _create_student_user(name=name, email=email)
    if "error" in created_user:
        return created_user

    user_id = created_user["user_id"]

    # 4) Delete pending
    delete_pending_registration(pending_id)

    return {
        "status": "approved",
        "user_id": user_id,
        "email": email,
        "name": name,
        "default_password": DEFAULT_STUDENT_PASSWORD,
    }
