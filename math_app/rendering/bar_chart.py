def render_bar_chart(config: dict) -> str:
    """
    Render responsive SVG bar chart.

    Expected config:
    {
        "x_labels": ["Mon", "Tue", "Wed"],
        "values": [50, 75, 125],
        "y_max": 150
    }
    """

    width = 600
    height = 350
    margin = 60

    x_labels = config.get("x_labels", [])
    values = config.get("values", [])
    y_max = config.get("y_max", max(values) if values else 100)

    bar_count = len(values)
    if bar_count == 0:
        return "<p>Invalid bar chart config</p>"

    chart_width = width - 2 * margin
    chart_height = height - 2 * margin

    bar_width = chart_width / bar_count * 0.6
    spacing = chart_width / bar_count

    bars_svg = ""

    for i, value in enumerate(values):
        scaled_height = (value / y_max) * chart_height
        x = margin + i * spacing + (spacing - bar_width) / 2
        y = height - margin - scaled_height

        bars_svg += f"""
        <rect x="{x}" y="{y}"
              width="{bar_width}"
              height="{scaled_height}"
              fill="#4F81BD" />
        <text x="{x + bar_width/2}"
              y="{height - margin + 20}"
              text-anchor="middle"
              font-size="14">
            {x_labels[i]}
        </text>
        """

    # Y axis line
    axes_svg = f"""
    <line x1="{margin}" y1="{margin}"
          x2="{margin}" y2="{height - margin}"
          stroke="black" stroke-width="2" />
    <line x1="{margin}" y1="{height - margin}"
          x2="{width - margin}" y2="{height - margin}"
          stroke="black" stroke-width="2" />
    """

    svg = f"""
    <svg viewBox="0 0 {width} {height}"
         width="100%"
         height="auto"
         preserveAspectRatio="xMidYMid meet">

        {axes_svg}
        {bars_svg}

    </svg>
    """

    return svg

