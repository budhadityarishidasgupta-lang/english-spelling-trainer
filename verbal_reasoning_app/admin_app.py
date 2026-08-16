import streamlit as st

from verbal_reasoning_app.repository.vr_repository import ensure_paper_catalog, init_vr_tables
from verbal_reasoning_app.services.vr_csv_service import ingest_csv_bytes


st.set_page_config(page_title="VR Admin", page_icon="🧠", layout="centered")
st.title("🧠 Verbal Reasoning Admin")
st.caption("CSV ingestion is idempotent: re-uploading enriches/updates matching VR content and does not delete papers or attempts.")

init_vr_tables()
ensure_paper_catalog()

uploaded = st.file_uploader("Upload Verbal Reasoning question CSV", type=["csv"])
if uploaded is not None:
    st.write(f"File: **{uploaded.name}**")
    if st.button("Validate & Import", type="primary", use_container_width=True):
        try:
            result = ingest_csv_bytes(uploaded.getvalue())
            st.success(f"Imported {result['imported']} rows.")
            st.caption("Detected headers: " + ", ".join(result["headers"]))
            if result["errors"]:
                st.error(f"{len(result['errors'])} rows were rejected. No silent corrections were made.")
                for error in result["errors"][:100]:
                    st.write(error)
        except Exception as exc:
            st.error(str(exc))
