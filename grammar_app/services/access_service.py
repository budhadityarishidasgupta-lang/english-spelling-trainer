from __future__ import annotations

from functools import lru_cache
from typing import Any, Iterable, List, Optional

from shared.db import execute

ALLOWED_ACCESS_CODES = {"grammar", "gsm"}
EMAIL_COLUMNS = ("user_email", "email", "login_email", "contact_email")
CODE_COLUMNS = (
    "app_code",
    "app_source",
    "entitlement",
    "entitlement_code",
    "access_code",
    "subscription_code",
    "product_code",
    "feature_code",
    "code",
)
TABLE_HINTS = (
    "membership",
    "entitlement",
    "access",
    "subscription",
    "permission",
    "app",
    "user",
)


def _safe_execute(query: str, params: Optional[dict[str, Any]] = None):
    result = execute(query, params or {})
    if isinstance(result, dict) and result.get("error"):
        raise RuntimeError(result["error"])
    return result


@lru_cache(maxsize=None)
def _table_names() -> tuple[str, ...]:
    rows = _safe_execute(
        """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
        ORDER BY table_name
        """
    )
    names: List[str] = []
    for row in rows or []:
        if hasattr(row, "_mapping"):
            names.append(str(row._mapping["table_name"]).lower())
        elif isinstance(row, dict) and "table_name" in row:
            names.append(str(row["table_name"]).lower())
        elif isinstance(row, (list, tuple)) and row:
            names.append(str(row[0]).lower())
    return tuple(names)


@lru_cache(maxsize=None)
def _table_columns(table_name: str) -> tuple[str, ...]:
    rows = _safe_execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = :table_name
        ORDER BY ordinal_position
        """,
        {"table_name": table_name},
    )
    cols: List[str] = []
    for row in rows or []:
        if hasattr(row, "_mapping"):
            cols.append(str(row._mapping["column_name"]).lower())
        elif isinstance(row, dict) and "column_name" in row:
            cols.append(str(row["column_name"]).lower())
        elif isinstance(row, (list, tuple)) and row:
            cols.append(str(row[0]).lower())
    return tuple(cols)


def _candidate_tables() -> List[str]:
    names = list(_table_names())
    ordered: List[str] = []
    if "users" in names:
        ordered.append("users")
    for table_name in names:
        if table_name == "users":
            continue
        if any(hint in table_name for hint in TABLE_HINTS):
            ordered.append(table_name)
    # Keep only unique names while preserving order.
    return list(dict.fromkeys(ordered))


def _first_existing(columns: Iterable[str], candidates: Iterable[str]) -> Optional[str]:
    column_set = {column.lower() for column in columns}
    for candidate in candidates:
        if candidate.lower() in column_set:
            return candidate.lower()
    return None


def has_grammar_access(user_email: str) -> bool:
    """
    Small, isolated access helper for GrammarSprint.

    Checks for either a GSM-style entitlement or a direct app_code/app_source
    marker for GrammarSprint access.
    """
    email = " ".join(str(user_email or "").strip().split())
    if not email:
        return False

    for table_name in _candidate_tables():
        columns = _table_columns(table_name)
        email_col = _first_existing(columns, EMAIL_COLUMNS)
        if not email_col:
            continue

        code_cols = [column for column in CODE_COLUMNS if column.lower() in columns]
        if not code_cols:
            continue

        select_cols = ", ".join([email_col] + code_cols)
        rows = _safe_execute(
            f"""
            SELECT {select_cols}
            FROM {table_name}
            WHERE LOWER(TRIM({email_col})) = LOWER(TRIM(:email))
            """,
            {"email": email},
        )
        for row in rows or []:
            if hasattr(row, "_mapping"):
                mapping = row._mapping
                values = [str(mapping.get(column, "")).strip().lower() for column in code_cols]
            elif isinstance(row, dict):
                values = [str(row.get(column, "")).strip().lower() for column in code_cols]
            elif isinstance(row, (list, tuple)):
                values = [str(row[idx + 1] if idx + 1 < len(row) else "").strip().lower() for idx in range(len(code_cols))]
            else:
                values = [str(row).strip().lower()]

            if any(value in ALLOWED_ACCESS_CODES for value in values):
                return True

    return False
