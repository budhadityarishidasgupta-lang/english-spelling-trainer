from math_app.db import get_db_connection


def create_math_registration(name, email, password_hash, class_name=None):
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO math_pending_registrations
                (name, email, password_hash, class_name)
                VALUES (%s, %s, %s, %s)
                """,
                (name, email.lower(), password_hash, class_name),
            )
            conn.commit()
    finally:
        if conn:
            conn.close()


def get_pending_math_registrations():
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT registration_id, name, email, class_name, created_at
                FROM math_pending_registrations
                WHERE status = 'PENDING'
                ORDER BY created_at
                """
            )
            rows = cur.fetchall()
            return rows
    finally:
        if conn:
            conn.close()


def approve_math_registration(reg_id: int):
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            # fetch pending record
            cur.execute(
                """
                SELECT name, email, password_hash, class_name
                FROM math_pending_registrations
                WHERE registration_id = %s AND status = 'PENDING'
                """,
                (reg_id,),
            )
            row = cur.fetchone()
            if not row:
                return False

            name, email, password_hash, class_name = row

            # create user in shared users table
            cur.execute(
                """
                INSERT INTO users (name, email, password_hash, role, status, app_source, class_name)
                VALUES (%s, %s, %s, 'student', 'ACTIVE', 'math', %s)
                ON CONFLICT (email)
                DO UPDATE SET
                    status = 'ACTIVE',
                    app_source = 'math'
                """,
                (name, email, password_hash, class_name),
            )

            # mark registration approved
            cur.execute(
                """
                UPDATE math_pending_registrations
                SET status = 'APPROVED'
                WHERE registration_id = %s
                """,
                (reg_id,),
            )

            conn.commit()
            return True
    finally:
        if conn:
            conn.close()
