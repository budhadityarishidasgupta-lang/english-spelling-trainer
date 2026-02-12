from math_app.rendering.bar_chart import render_bar_chart


def render_diagram(diagram_type: str, config: dict) -> str:
    if diagram_type == "bar_chart":
        return render_bar_chart(config)

    return "<p>Unsupported diagram type</p>"

