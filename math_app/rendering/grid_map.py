def render_grid_map(config: dict) -> str:
    size = config.get("grid_size", 10)
    start = config.get("start", [0, 0])
    path = config.get("path", [])

    width = 500
    height = 500
    cell = width / size

    lines = ""
    for i in range(size + 1):
        pos = i * cell
        lines += f'<line x1="{pos}" y1="0" x2="{pos}" y2="{height}" stroke="#ccc"/>'
        lines += f'<line x1="0" y1="{pos}" x2="{width}" y2="{pos}" stroke="#ccc"/>'

    x, y = start
    path_svg = ""

    def get_coords(x, y):
        cx = x * cell + cell / 2
        cy = height - (y * cell + cell / 2)
        return cx, cy

    cx, cy = get_coords(x, y)
    path_svg += f'<circle cx="{cx}" cy="{cy}" r="6" fill="red"/>'

    for move in path:
        if move == "right":
            x += 1
        elif move == "left":
            x -= 1
        elif move == "up":
            y += 1
        elif move == "down":
            y -= 1

        cx, cy = get_coords(x, y)
        path_svg += f'<circle cx="{cx}" cy="{cy}" r="6" fill="blue"/>'

    return f"""
    <svg viewBox="0 0 {width} {height}"
         width="100%"
         
         preserveAspectRatio="xMidYMid meet">
        {lines}
        {path_svg}
    </svg>
    """
