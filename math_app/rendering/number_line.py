def render_number_line(config: dict) -> str:
    min_val = config.get("min", 0)
    max_val = config.get("max", 10)
    highlight = config.get("highlight", None)

    width = 600
    height = 150
    margin = 50
    length = max_val - min_val
    spacing = (width - 2 * margin) / length

    ticks = ""
    for i in range(min_val, max_val + 1):
        x = margin + (i - min_val) * spacing
        ticks += f'<line x1="{x}" y1="60" x2="{x}" y2="80" stroke="black"/>'
        ticks += f'<text x="{x}" y="100" text-anchor="middle" font-size="14">{i}</text>'

    highlight_svg = ""
    if highlight is not None:
        x = margin + (highlight - min_val) * spacing
        highlight_svg = f'<circle cx="{x}" cy="70" r="8" fill="red"/>'

    return f"""
    <svg viewBox="0 0 {width} {height}"
         width="100%"
        
         preserveAspectRatio="xMidYMid meet">
        <line x1="{margin}" y1="70"
              x2="{width - margin}" y2="70"
              stroke="black" stroke-width="2"/>
        {ticks}
        {highlight_svg}
    </svg>
    """
