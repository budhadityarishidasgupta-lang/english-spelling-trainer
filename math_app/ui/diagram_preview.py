import streamlit as st
from math_app.rendering.diagram_engine import render_diagram
from math_app.rendering.safe_render import safe_render

st.set_page_config(page_title="Math Diagram Preview", layout="centered")
st.title("🧪 Diagram Preview — Bar Chart")

sample_config = {
    "x_labels": ["Mon", "Tue", "Wed", "Thu", "Fri"],
    "values": [50, 75, 125, 60, 90],
    "y_max": 150,
}

svg = render_diagram("bar_chart", sample_config)
st.markdown(safe_render(svg), unsafe_allow_html=True)

st.subheader("Config used")
st.json(sample_config)
