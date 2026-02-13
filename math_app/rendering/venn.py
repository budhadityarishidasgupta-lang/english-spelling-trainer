def render_venn(config: dict) -> str:
    width = 500
    height = 350

    setA = config.get("setA", "")
    setB = config.get("setB", "")
    inter = config.get("intersection", "")

    return f"""
    <svg viewBox="0 0 {width} {height}"
         width="100%"
         height="auto"
         preserveAspectRatio="xMidYMid meet">

        <circle cx="220" cy="180" r="100"
                fill="rgba(100,150,255,0.5)" />
        <circle cx="320" cy="180" r="100"
                fill="rgba(255,150,150,0.5)" />

        <text x="170" y="180" font-size="16">{setA}</text>
        <text x="350" y="180" font-size="16">{setB}</text>
        <text x="270" y="180" font-size="16">{inter}</text>

    </svg>
    """
