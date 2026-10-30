import os
import json
import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

from iconlib.normalizer import IconNormalizer
from iconlib.optimizer import IconOptimizer
from iconlib.dpi_generator import DPIGenerator


class DataIconGenerator:
    CHARTS = ["line", "bar", "area", "donut", "sparkline"]
    STYLES = ["fluent", "monochrome", "outline", "classic"]
    SIZE_MIN = 128
    SIZE_MAX = 512

    def __init__(self):
        pass

    # --- MAIN ENTRY POINT ---

    def generate(self, data, out_dir, chart="line", style="fluent", size=256):
        values = self._coerce(data)
        chart = str(chart).strip().lower()
        if chart not in self.CHARTS:
            chart = "line"
        style = str(style).strip().lower()
        if style not in self.STYLES:
            style = "fluent"
        size = int(max(self.SIZE_MIN, min(self.SIZE_MAX, int(size))))

        if not os.path.isdir(out_dir):
            os.makedirs(out_dir, exist_ok=True)

        # Step 1: data -> chart PNG
        chart_path = os.path.join(out_dir, "chart.png")
        self._chart_to_png(values, chart_path, chart, size)

        # Step 2: chart -> styled PNG
        styled_path = os.path.join(out_dir, "styled.png")
        self._apply_style(chart_path, styled_path, style)

        # Step 3: normalize -> multi-DPI ICO
        norm = IconNormalizer()
        ico_path = os.path.join(out_dir, "data.ico")
        norm.normalize(styled_path, ico_path, style)

        # Step 4: optimize
        opt = IconOptimizer()
        opt_path = os.path.join(out_dir, "data_opt.ico")
        opt.optimize_ico(ico_path, opt_path)

        # Step 5: explicit DPI set
        dpi_path = os.path.join(out_dir, "data_dpi.ico")
        try:
            DPIGenerator().generate_dpi_set(styled_path, dpi_path)
        except Exception:
            dpi_path = None

        # Step 6: metadata
        meta_path = os.path.join(out_dir, "data.json")
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump({
                "panel": "data-icon",
                "data": values,
                "chart": chart,
                "style": style,
                "size": size,
                "points": len(values),
                "stats": {
                    "min": min(values),
                    "max": max(values),
                    "mean": sum(values) / len(values),
                    "sum": sum(values),
                },
                "outputs": {
                    "chart": chart_path,
                    "png": styled_path,
                    "ico": opt_path,
                    "dpi": dpi_path,
                    "meta": meta_path,
                },
            }, f, indent=2)

        return {
            "png": styled_path,
            "chart": chart_path,
            "ico": opt_path,
            "dpi": dpi_path,
            "meta": meta_path,
        }

    # --- INPUT HELPERS ---

    def _coerce(self, data):
        if data is None:
            raise ValueError("Data must be a list of numbers")
        if isinstance(data, (int, float)):
            data = [data]
        try:
            values = [float(v) for v in data]
        except (TypeError, ValueError):
            raise ValueError("Data must be a list of numbers")
        if not values:
            raise ValueError("Data must contain at least one number")
        return values

    # --- DATA -> CHART PNG ---

    def _chart_to_png(self, data, out_path, chart, size):
        img = Image.new("RGBA", (size, size), (255, 255, 255, 0))
        draw = ImageDraw.Draw(img)

        arr = np.array(data, dtype="float64")
        lo, hi = float(arr.min()), float(arr.max())
        span = hi - lo
        if span <= 1e-9:
            norm = np.full(arr.shape, 0.5, dtype="float64")
        else:
            norm = (arr - lo) / span

        margin = max(12, size // 10)
        inner = size - margin * 2
        count = len(norm)

        points = []
        for i, v in enumerate(norm):
            if count == 1:
                x = size // 2
            else:
                x = margin + int((i / (count - 1)) * inner)
            y = int(size - margin - float(v) * inner)
            points.append((x, y))

        if chart == "line":
            draw.line(points, fill=(0, 0, 0, 255),
                      width=max(3, size // 32), joint="curve")
        elif chart == "sparkline":
            draw.line(points, fill=(0, 0, 0, 255),
                      width=max(2, size // 64), joint="curve")
        elif chart == "area":
            base = size - margin
            area = points + [(points[-1][0], base), (points[0][0], base)]
            draw.polygon(area, fill=(0, 0, 0, 180))
            draw.line(points, fill=(0, 0, 0, 255), width=max(2, size // 64))
        elif chart == "bar":
            self._draw_bars(draw, norm, size, margin, inner)
        elif chart == "donut":
            img = self._draw_donut(img, draw, norm, size)

        img.save(out_path, optimize=True)
        return out_path

    def _draw_bars(self, draw, norm, size, margin, inner):
        n = max(1, len(norm))
        slot = inner / n
        gap = max(1, int(slot * 0.18))
        base = size - margin
        for i, v in enumerate(norm):
            x0 = margin + int(i * slot) + gap
            x1 = margin + int((i + 1) * slot) - gap
            if x1 <= x0:
                x1 = x0 + 1
            y0 = int(base - float(v) * inner)
            draw.rectangle((x0, y0, x1, base), fill=(0, 0, 0, 255))

    def _draw_donut(self, img, draw, norm, size):
        cx = cy = size // 2
        r = int(size * 0.36)
        total = float(norm.sum())

        if total <= 1e-9:
            draw.ellipse((cx - r, cy - r, cx + r, cy + r),
                         outline=(0, 0, 0, 255), width=max(4, size // 32))
        else:
            angle = -90.0
            for v in norm:
                sweep = 360.0 * (float(v) / total)
                draw.pieslice((cx - r, cy - r, cx + r, cy + r),
                              angle, angle + sweep, fill=(0, 0, 0, 255))
                angle += sweep

        # punch a genuine transparent hole
        hole = max(2, int(r * 0.55))
        arr = np.array(img)
        yy, xx = np.ogrid[:size, :size]
        mask = (xx - cx) ** 2 + (yy - cy) ** 2 <= hole ** 2
        arr[mask, 3] = 0
        return Image.fromarray(arr, "RGBA")

    # --- STYLE APPLICATION ---

    def _apply_style(self, src, dst, style):
        img = Image.open(src).convert("RGBA")

        if style == "fluent":
            img = ImageEnhance.Color(img).enhance(0.75)
            img = ImageEnhance.Brightness(img).enhance(1.1)
            img = ImageEnhance.Contrast(img).enhance(0.9)
            bloom = img.filter(ImageFilter.GaussianBlur(6))
            arr = np.array(img).copy()
            bl = np.array(bloom)
            arr[:, :, :3] = (arr[:, :, :3] * 0.85 + bl[:, :, :3] * 0.15).astype("uint8")
            Image.fromarray(arr, "RGBA").save(dst, optimize=True)
            return dst

        if style == "monochrome":
            arr = np.array(img)
            gray = np.array(img.convert("L"))
            rgba = np.zeros((gray.shape[0], gray.shape[1], 4), dtype="uint8")
            rgba[:, :, 0] = gray
            rgba[:, :, 1] = gray
            rgba[:, :, 2] = gray
            rgba[:, :, 3] = arr[:, :, 3]
            Image.fromarray(rgba, "RGBA").save(dst, optimize=True)
            return dst

        if style == "outline":
            outline = img.filter(ImageFilter.FIND_EDGES)
            arr = np.array(outline).copy()
            arr[:, :, 3] = np.array(img)[:, :, 3]
            Image.fromarray(arr, "RGBA").save(dst, optimize=True)
            return dst

        # classic
        img = ImageEnhance.Color(img).enhance(1.4)
        img = ImageEnhance.Contrast(img).enhance(1.2)
        img.save(dst, optimize=True)
        return dst
