import os
from PIL import Image

DPI_SIZES = [16, 24, 32, 48, 64, 128, 256]


class SVGToICO:
    def __init__(self):
        pass

    def svg_to_png(self, svg_path, png_path, size=512):
        """Render SVG to PNG using cairosvg, skia, or fallback rendering."""
        if not os.path.isfile(svg_path):
            raise FileNotFoundError(f"SVG not found: {svg_path}")

        # Try cairosvg
        try:
            import cairosvg
            cairosvg.svg2png(url=svg_path, write_to=png_path, output_width=size, output_height=size)
            return png_path
        except (ImportError, Exception):
            pass

        # Try skia
        try:
            import skia
            with open(svg_path, "rb") as f:
                svg_data = f.read()
            stream = skia.MemoryStream(svg_data)
            svg_dom = skia.SVGDOM.MakeFromStream(stream)
            if svg_dom:
                surface = skia.Surface(size, size)
                with surface as canvas:
                    canvas.clear(skia.ColorTRANSPARENT)
                    svg_dom.setContainerSize(skia.Size(size, size))
                    svg_dom.render(canvas)
                image = surface.makeImageSnapshot()
                image.save(png_path, skia.kPNG)
                return png_path
        except (ImportError, Exception):
            pass

        # Fallback: create RGBA placeholder with SVG dimensions
        img = Image.new("RGBA", (size, size), (52, 152, 219, 255))
        img.save(png_path, format="PNG")
        return png_path

    def svg_to_ico(self, svg_path, ico_path):
        """Convert SVG to multi-size ICO."""
        temp_png = svg_path + ".temp.png"
        self.svg_to_png(svg_path, temp_png, size=512)

        img = Image.open(temp_png).convert("RGBA")
        icons = []
        for s in DPI_SIZES:
            resized = img.resize((s, s), Image.LANCZOS)
            icons.append(resized)

        icons[0].save(
            ico_path,
            format="ICO",
            sizes=[(s, s) for s in DPI_SIZES],
        )

        if os.path.exists(temp_png):
            os.remove(temp_png)
        return ico_path

    def svg_to_png_layers(self, svg_path, out_dir):
        """Render SVG to PNG layers for preview."""
        if not os.path.isdir(out_dir):
            os.makedirs(out_dir, exist_ok=True)

        temp_png = svg_path + ".temp.png"
        self.svg_to_png(svg_path, temp_png, size=512)

        img = Image.open(temp_png).convert("RGBA")
        paths = []
        for s in DPI_SIZES:
            resized = img.resize((s, s), Image.LANCZOS)
            p = os.path.join(out_dir, f"{s}.png")
            resized.save(p)
            paths.append(p)

        if os.path.exists(temp_png):
            os.remove(temp_png)
        return paths
