import streamlit as st

from math_app.rendering.diagram_engine import render_diagram
from math_app.rendering.safe_render import safe_render

st.set_page_config(page_title="Diagram Sandbox", layout="centered")

st.title("🧪 Diagram Engine Sandbox")

diagram_type = st.selectbox(
    "Select Diagram Type",
    ["bar_chart", "grid_map", "triangle", "number_line", "venn"]
)

configs = {
    "bar_chart": {
        "x_labels": ["Mon", "Tue", "Wed"],
        "values": [50, 75, 125],
        "y_max": 150
    },
    "grid_map": {
        "grid_size": 8,
        "start": [2, 2],
        "path": ["right", "up", "up", "left"]
    },
    "triangle": {
        "angles": {"A": 60, "B": 40, "C": "?"}
    },
    "number_line": {
        "min": 0,
        "max": 10,
        "highlight": 7
    },
    "venn": {
        "setA": 20,
        "setB": 15,
        "intersection": 5
    }
}

config = configs[diagram_type]

st.markdown("### Rendered Diagram")

svg = render_diagram(diagram_type, config)
st.markdown(safe_render(svg), unsafe_allow_html=True)

st.markdown("---")
st.write("Raw Config Used:")
st.json(config)
