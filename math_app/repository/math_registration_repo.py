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
    """
    Returns pending maths registrations without assuming PK column name.
    """
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT *
                FROM math_pending_registrations
                WHERE status = 'PENDING'
                ORDER BY created_at
                """
            )
            rows = cur.fetchall()

            col_names = [desc[0] for desc in cur.description]

            results = []
            for row in rows:
                record = dict(zip(col_names, row))
                results.append(record)

            return results
    finally:
        if conn:
            conn.close()


def approve_math_registration(registration_pk):
    """
    Approves a pending maths registration using dynamic PK handling.
    """
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            # Fetch pending record dynamically
            cur.execute(
                """
                SELECT *
                FROM math_pending_registrations
                WHERE status = 'PENDING'
                """,
            )
            rows = cur.fetchall()
            col_names = [desc[0] for desc in cur.description]

            target = None
            for row in rows:
                record = dict(zip(col_names, row))
                if record[col_names[0]] == registration_pk:
                    target = record
                    break

            if not target:
                return False

            name = target["name"]
            email = target["email"]
            password_hash = target["password_hash"]
            class_name = target.get("class_name")

            # Create or activate user
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

            # Mark approved (use PK column dynamically)
            cur.execute(
                f"""
                UPDATE math_pending_registrations
                SET status = 'APPROVED'
                WHERE {col_names[0]} = %s
                """,
                (registration_pk,),
            )

            conn.commit()
            return True
    finally:
        if conn:
            conn.close()
