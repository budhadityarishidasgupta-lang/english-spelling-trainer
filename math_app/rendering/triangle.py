def render_triangle(config: dict) -> str:
    width = 500
    height = 400
    angles = config.get("angles", {})

    return f"""
    <svg viewBox="0 0 {width} {height}"
         width="100%"
         height="auto"
         preserveAspectRatio="xMidYMid meet">

        <polygon points="250,50 100,350 400,350"
                 fill="none"
                 stroke="black"
                 stroke-width="2"/>

        <text x="250" y="40" text-anchor="middle" font-size="16">
            A = {angles.get("A","")}
        </text>

        <text x="80" y="370" font-size="16">
            B = {angles.get("B","")}
        </text>

        <text x="420" y="370" text-anchor="end" font-size="16">
            C = {angles.get("C","")}
        </text>

    </svg>
    """
