# spelling_app/repository/attempts_repo.py

from shared.db import fetch_all


def _to_dict(row):
    """Convert SQLAlchemy row or mapping to dict safely."""
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
    """Normalize fetch_all results into list."""
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


def get_spelling_attempts_summary():
    """
    Returns per-student performance summary from spelling_attempts.
    Summary includes:
        - user_id
        - name
        - total_attempts
        - accuracy
        - last_attempt
    """

    sql = """
        SELECT
            a.student_id AS user_id,
            u.name AS student_name,
            COUNT(*) AS total_attempts,
            AVG(CASE WHEN a.is_correct THEN 1 ELSE 0 END) AS accuracy,
            MAX(a.attempted_at) AS last_attempt
        FROM spelling_attempts a
        LEFT JOIN users u ON u.user_id = a.student_id
        GROUP BY a.student_id, u.name
        ORDER BY last_attempt DESC NULLS LAST;
    """

    rows = fetch_all(sql)

    if isinstance(rows, dict):  # DB error
        return rows

    rows = _to_list(rows)
    return [_to_dict(r) for r in rows]
