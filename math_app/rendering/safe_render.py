def safe_render(svg: str) -> str:
    """
    Wrap SVG in safe responsive container.
    Prevents overflow and UI breakage.
    """
    return f"""
    <div style="
        width:100%;
        max-width:650px;
        margin:20px auto;
        overflow:hidden;
    ">
        {svg}
    </div>
    """

