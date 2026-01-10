from typing import Optional, List, Dict, Any
from sqlalchemy import text
from shared.db import engine


def _norm(s: str) -> str:
    return (s or "").strip()


def upsert_ai_hint_drafts(rows: List[Dict[str, Any]]) -> int:
    """
    Upsert AI hint drafts into spelling_hint_ai_draft.
    Expected row keys: word_id (int), course_id (int|None), hint_text (str)
    """
    if not rows:
        return 0

    sql = text("""
        INSERT INTO spelling_hint_ai_draft (word_id, course_id, hint_text, hint_style, created_by, status)
        VALUES (:word_id, :course_id, :hint_text, 'meaning_plus_spelling', 'csv', 'draft')
        ON CONFLICT (word_id, course_id, hint_style)
        DO UPDATE SET
            hint_text = EXCLUDED.hint_text,
            created_by = 'csv',
            status = 'draft',
            created_at = now();
    """)

    payload = []
    for r in rows:
        payload.append({
            "word_id": int(r["word_id"]),
            "course_id": int(r["course_id"]) if r.get("course_id") not in (None, "", "null", "NULL") else None,
            "hint_text": _norm(r.get("hint_text") or r.get("hint") or ""),
        })

    with engine.begin() as conn:
        conn.execute(sql, payload)
    return len(payload)


def approve_drafts_to_overrides(course_id: Optional[int] = None) -> int:
    """
    Promote draft hints to overrides (live table) and mark drafts approved.
    Does NOT touch spelling_words.hint (legacy fallback).
    """
    with engine.begin() as conn:
        # 1) Insert/Update overrides from drafts
        up_sql = text("""
            INSERT INTO spelling_hint_overrides (word_id, course_id, hint_text, source, updated_at)
            SELECT d.word_id, d.course_id, d.hint_text, 'ai-approved', now()
            FROM spelling_hint_ai_draft d
            WHERE d.status = 'draft'
              AND d.hint_style = 'meaning_plus_spelling'
              AND (:cid IS NULL OR d.course_id = :cid)
            ON CONFLICT (word_id, course_id)
            DO UPDATE SET
              hint_text = EXCLUDED.hint_text,
              source = 'ai-approved',
              updated_at = now();
        """)
        conn.execute(up_sql, {"cid": course_id})

        # 2) Mark drafts approved
        mark_sql = text("""
            UPDATE spelling_hint_ai_draft
               SET status = 'approved'
             WHERE status = 'draft'
               AND hint_style = 'meaning_plus_spelling'
               AND (:cid IS NULL OR course_id = :cid);
        """)
        res = conn.execute(mark_sql, {"cid": course_id})
        return int(res.rowcount or 0)


def get_override_hint(word_id: int, course_id: Optional[int]) -> Optional[str]:
    """
    Read-only: returns override hint if present (course-specific first, then global).
    NOT wired into student app yet (safe).
    """
    sql = text("""
        SELECT hint_text
        FROM spelling_hint_overrides
        WHERE word_id = :wid
          AND (course_id = :cid OR course_id IS NULL)
        ORDER BY (course_id IS NULL) ASC
        LIMIT 1;
    """)
    with engine.connect() as conn:
        row = conn.execute(sql, {"wid": int(word_id), "cid": course_id}).fetchone()
    return row[0] if row else None


def resolve_hint_preview(word_id: int, course_id: Optional[int]) -> Optional[str]:
    """
    Preview-only resolver (override -> legacy fallback).
    Does NOT change student behaviour unless you wire it later.
    """
    override = get_override_hint(word_id, course_id)
    if override:
        return override
    # Legacy fallback:
    sql = text("SELECT hint FROM spelling_words WHERE word_id = :wid;")
    with engine.connect() as conn:
        row = conn.execute(sql, {"wid": int(word_id)}).fetchone()
    return row[0] if row else None
