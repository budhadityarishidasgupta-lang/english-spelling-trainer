def safe_render(svg: str) -> str:
    """
    Wrap SVG in full HTML document for iframe rendering.
    Prevents SVG being ignored in components.html().
    """

    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{
                margin: 0;
                padding: 0;
                display: flex;
                justify-content: center;
                align-items: center;
                background-color: white;
            }}
            .container {{
                width: 100%;
                max-width: 650px;
            }}
            svg {{
                width: 100%;
                height: auto;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            {svg}
        </div>
    </body>
    </html>
    """
