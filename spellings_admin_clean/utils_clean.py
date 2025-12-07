from typing import Dict, Any

import streamlit as st
import pandas as pd
from shared.db import fetch_all


# ---------------------------------------------
# Helper returns clean dict rows for dropdowns
# ---------------------------------------------
def fetch_all_simple(sql, params=None):
    rows = fetch_all(sql, params or {})
    out = []
    for r in rows:
        m = getattr(r, "_mapping", r)
        out.append(dict(m))
    return out


def read_csv_to_df(uploaded_file) -> pd.DataFrame:
    """
    Safely read an uploaded CSV into a DataFrame.
    """
    if uploaded_file is None:
        return pd.DataFrame()

    try:
        return pd.read_csv(uploaded_file)
    except Exception as e:
        st.error(f"Error reading CSV file: {e}")
        return pd.DataFrame()


def show_upload_summary(summary: Dict[str, Any]):
    """
    Display summary returned from process_spelling_csv.
    """
    if not summary:
        st.info("No summary available.")
        return

    if summary.get("error"):
        st.error(summary["error"])

    st.subheader("Upload Summary")
    st.write(f"Rows processed: {summary.get('processed', 0)}")
    st.write(f"New words created: {summary.get('created_words', 0)}")
    st.write(f"Existing words reused: {summary.get('reused_words', 0)}")
    st.write(f"New lessons created: {summary.get('created_lessons', 0)}")

    errors = summary.get("rows_with_error", [])
    if errors:
        st.warning(f"{len(errors)} rows had issues.")
        with st.expander("Show problematic rows"):
            for err in errors:
                st.write(err)
