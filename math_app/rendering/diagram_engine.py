from math_app.rendering.bar_chart import render_bar_chart
from math_app.rendering.grid_map import render_grid_map
from math_app.rendering.triangle import render_triangle
from math_app.rendering.number_line import render_number_line
from math_app.rendering.venn import render_venn


def render_diagram(diagram_type: str, config: dict) -> str:
    """
    Central dispatcher for all diagram rendering.
    Pure rendering layer. No DB. No Streamlit.
    """

    if diagram_type == "bar_chart":
        return render_bar_chart(config)

    if diagram_type == "grid_map":
        return render_grid_map(config)

    if diagram_type == "triangle":
        return render_triangle(config)

    if diagram_type == "number_line":
        return render_number_line(config)

    if diagram_type == "venn":
        return render_venn(config)

    return "<p>Unsupported diagram type</p>"
