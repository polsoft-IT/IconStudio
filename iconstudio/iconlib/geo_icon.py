import os
import json
import hashlib
import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

from iconlib.normalizer import IconNormalizer
from iconlib.optimizer import IconOptimizer
from iconlib.dpi_generator import DPIGenerator


class GeoIconGenerator:
    """geo -> shape/symbol raster -> style -> ICO."""

    SYMBOLS = ["pin", "marker", "region", "route", "area", "heatmap"]
    STYLES = ["fluent", "monochrome", "outline", "classic"]
    SIZE_MIN = 128
    SIZE_MAX = 512
    SUPERSAMPLE = 4

    def __init__(self):
        pass

    # --- MAIN ENTRY POINT ---

    def generate(self, geo, out_dir, symbol="pin", style="fluent", size=256):
        symbol = str(symbol).strip().lower()
        if symbol not in self.SYMBOLS:
            symbol = "pin"
        style = str(style).strip().lower()
        if style not in self.STYLES:
            style = "fluent"
        size = int(max(self.SIZE_MIN, min(self.SIZE_MAX, int(size))))

        points, values, name, bbox = self._coerce(geo, symbol)
        self._validate(symbol, points, values)

        if not os.path.isdir(out_dir):
            os.makedirs(out_dir, exist_ok=True)

        # Step 1: geo -> shape PNG
        shape_path = os.path.join(out_dir, "shape.png")
        self._geo_to_shape(points, values, name, shape_path, symbol, size)

        # Step 2: shape -> styled PNG
        styled_path = os.path.join(out_dir, "styled.png")
        self._apply_style(shape_path, styled_path, style)

        # Step 3: normalize -> multi-DPI ICO
        ico_path = os.path.join(out_dir, "geo.ico")
        IconNormalizer().normalize(styled_path, ico_path, style)

        # Step 4: optimize
        opt_path = os.path.join(out_dir, "geo_opt.ico")
        IconOptimizer().optimize_ico(ico_path, opt_path)

        # Step 5: explicit DPI set
        dpi_path = os.path.join(out_dir, "geo_dpi.ico")
        try:
            DPIGenerator().generate_dpi_set(styled_path, dpi_path)
        except Exception:
            dpi_path = None

        # Step 6: metadata
        meta_path = os.path.join(out_dir, "geo.json")
        info = self._geo_info(points, values, name, bbox)
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump({
                "panel": "geo-icon",
                "symbol": symbol,
                "style": style,
                "size": size,
                "geo": info,
                "outputs": {
                    "shape": shape_path,
                    "png": styled_path,
                    "ico": opt_path,
                    "dpi": dpi_path,
                    "meta": meta_path,
                },
            }, f, indent=2)

        return {
            "png": styled_path,
            "shape": shape_path,
            "ico": opt_path,
            "dpi": dpi_path,
            "meta": meta_path,
            "symbol": symbol,
            "geo": info,
        }

    # --- INPUT COERCION (points | bbox | region name | heat values) ---

    def _coerce(self, geo, symbol="pin"):
        if geo is None:
            raise ValueError("Geo input is required")

        points, values, name, bbox = [], [], None, None

        if isinstance(geo, dict):
            name = geo.get("name")
            raw_bbox = geo.get("bbox") or geo.get("bounds")
            raw_points = geo.get("points") or geo.get("coords") or geo.get("route")
            raw_values = geo.get("values") or geo.get("heat") or geo.get("weights") or []
            if raw_points:
                points = self._as_points(raw_points)
            if raw_bbox:
                bbox = self._as_bbox(raw_bbox)
                if not points:
                    mn_lat, mn_lon, mx_lat, mx_lon = bbox
                    points = [(mx_lat, mn_lon), (mx_lat, mx_lon),
                              (mn_lat, mx_lon), (mn_lat, mn_lon)]
            values = self._as_values(raw_values)

        elif isinstance(geo, str):
            text = geo.strip()
            if not text:
                raise ValueError("Geo input is empty")
            tokens = [t for t in text.replace(",", " ").replace(";", " ")
                      .replace("\n", " ").split() if t]
            flat_numbers = bool(tokens) and all(self._is_float(t) for t in tokens)
            if symbol == "heatmap" and flat_numbers and ";" not in text:
                values = self._as_values(tokens)
            elif self._looks_like_coords(text):
                points = self._parse_coords(text)
            else:
                name = text

        elif isinstance(geo, (list, tuple)):
            seq = list(geo)
            if not seq:
                raise ValueError("Geo input is empty")
            if all(isinstance(e, dict) for e in seq):
                points = self._as_points(seq)
            elif all(isinstance(e, (list, tuple)) and len(e) >= 2 for e in seq):
                points = self._as_points(seq)
            elif all(self._is_number(e) for e in seq):
                values = self._as_values(seq)
            else:
                points = self._as_points(seq)

        else:
            raise ValueError("Unsupported geo input type")

        if not points and not values and not name:
            raise ValueError("No coordinates, values or region name provided")
        return points, values, name, bbox

    def _validate(self, symbol, points, values):
        if symbol == "route" and len(points) < 2:
            raise ValueError("Route requires at least 2 coordinates (lat,lon)")
        if symbol == "area" and len(points) < 3:
            raise ValueError("Area requires at least 3 coordinates (lat,lon)")
        if symbol == "heatmap" and not points and not values:
            raise ValueError("Heatmap requires coordinates or numeric values")

    @staticmethod
    def _is_number(v):
        return isinstance(v, (int, float)) and not isinstance(v, bool)

    @staticmethod
    def _is_float(text):
        try:
            float(text)
            return True
        except (TypeError, ValueError):
            return False

    def _looks_like_coords(self, text):
        if "," not in text and ";" not in text and "\n" not in text:
            return False
        first = text.replace(";", " ").replace("\n", " ").replace(",", " ").split()
        if len(first) < 2:
            return False
        try:
            float(first[0])
            float(first[1])
            return True
        except ValueError:
            return False

    def _parse_coords(self, text):
        pts = []
        for chunk in text.replace("\n", ";").split(";"):
            chunk = chunk.strip()
            if not chunk:
                continue
            nums = [c for c in chunk.replace(",", " ").split() if c]
            if len(nums) < 2:
                continue
            try:
                pts.append((float(nums[0]), float(nums[1])))
            except ValueError:
                raise ValueError(f"Invalid coordinate '{chunk}' (expect 'lat,lon')")
        if not pts:
            raise ValueError("No coordinates found in input")
        return pts

    def _as_points(self, seq):
        pts = []
        for e in seq:
            if isinstance(e, dict):
                lat = e.get("lat", e.get("latitude"))
                lon = e.get("lon", e.get("lng", e.get("longitude")))
                if lat is None or lon is None:
                    continue
                pts.append((float(lat), float(lon)))
            elif isinstance(e, (list, tuple)) and len(e) >= 2:
                pts.append((float(e[0]), float(e[1])))
            else:
                raise ValueError("Points must be 'lat,lon' pairs")
        if not pts:
            raise ValueError("No valid coordinates found")
        return pts

    def _as_values(self, seq):
        try:
            return [float(v) for v in seq]
        except (TypeError, ValueError):
            raise ValueError("Values must be a sequence of numbers")

    def _as_bbox(self, b):
        if isinstance(b, dict):
            vals = [b.get("min_lat"), b.get("min_lon"),
                    b.get("max_lat"), b.get("max_lon")]
        else:
            vals = list(b)
        if len(vals) != 4 or any(v is None for v in vals):
            raise ValueError("bbox must be [min_lat, min_lon, max_lat, max_lon]")
        vals = [float(v) for v in vals]
        return (min(vals[0], vals[2]), min(vals[1], vals[3]),
                max(vals[0], vals[2]), max(vals[1], vals[3]))

    def _geo_info(self, points, values, name, bbox):
        info = {"points": len(points), "point_list": [[round(a, 6), round(b, 6)]
                                                       for a, b in points]}
        if name:
            info["name"] = name
        if bbox:
            info["bbox"] = [round(v, 6) for v in bbox]
        if values:
            info["values"] = [round(v, 6) for v in values]
            info["value_count"] = len(values)
        if points:
            lats = [p[0] for p in points]
            lons = [p[1] for p in points]
            info["center"] = [round(sum(lats) / len(lats), 6),
                              round(sum(lons) / len(lons), 6)]
            info["span"] = [round(max(lats) - min(lats), 6),
                            round(max(lons) - min(lons), 6)]
        return info

    # --- GEO -> SHAPE PNG ---

    def _geo_to_shape(self, points, values, name, out_path, symbol, size):
        if symbol == "heatmap":
            img = self._heatmap(points, values, size)
        else:
            img = self._mask_symbol(points, name, symbol, size)
        img.save(out_path, optimize=True)
        return out_path

    def _mask_symbol(self, points, name, symbol, size):
        ss = self.SUPERSAMPLE
        big = size * ss
        mask = Image.new("L", (big, big), 0)
        d = ImageDraw.Draw(mask)

        if symbol == "pin":
            self._draw_pin(d, big)
        elif symbol == "marker":
            self._draw_marker(d, big)
        elif symbol == "region":
            self._draw_region(d, points, name, big)
        elif symbol == "route":
            self._draw_route(d, points, big)
        else:  # area
            self._draw_area(d, points, big)

        mask = mask.resize((size, size), Image.LANCZOS)
        black = Image.new("RGBA", (size, size), (0, 0, 0, 255))
        clear = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        return Image.composite(black, clear, mask)

    # --- SYMBOL DRAWING (on a supersampled "L" mask) ---

    def _draw_pin(self, d, s):
        cx = s / 2.0
        cy = s * 0.36
        r = s * 0.24
        tip = s * 0.86
        d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=255)
        d.polygon([(cx - r * 0.72, cy + r * 0.55),
                   (cx + r * 0.72, cy + r * 0.55),
                   (cx, tip)], fill=255)
        hr = r * 0.42
        d.ellipse((cx - hr, cy - hr, cx + hr, cy + hr), fill=0)

    def _draw_marker(self, d, s):
        m = s * 0.18
        d.rounded_rectangle((m, m, s - m, s * 0.64), radius=s * 0.14, fill=255)
        d.polygon([(s * 0.33, s * 0.60), (s * 0.67, s * 0.60), (s / 2.0, s * 0.86)],
                  fill=255)
        cx, cy = s / 2.0, s * 0.40
        hr = s * 0.11
        d.ellipse((cx - hr, cy - hr, cx + hr, cy + hr), fill=0)

    def _draw_region(self, d, points, name, s):
        if name:
            d.polygon(self._region_polygon(name, s), fill=255)
            return
        if points:
            coords = self._project(points, s, s * 0.16)
            if len(coords) >= 3:
                d.polygon(coords, fill=255)
            else:
                xs = [p[0] for p in coords]
                ys = [p[1] for p in coords]
                pad = s * 0.12
                d.rounded_rectangle((min(xs) - pad, min(ys) - pad,
                                     max(xs) + pad, max(ys) + pad),
                                    radius=s * 0.08, fill=255)
            return
        m = s * 0.18
        d.rounded_rectangle((m, m, s - m, s - m), radius=s * 0.08, fill=255)

    def _draw_route(self, d, points, s):
        coords = self._project(points, s, s * 0.18)
        w = max(2, int(s * 0.05))
        d.line(coords, fill=255, width=w, joint="curve")
        r = w * 1.1
        for x, y in (coords[0], coords[-1]):
            d.ellipse((x - r, y - r, x + r, y + r), fill=255)
        rr = w * 0.6
        for x, y in coords[1:-1]:
            d.ellipse((x - rr, y - rr, x + rr, y + rr), fill=255)

    def _draw_area(self, d, points, s):
        coords = self._project(points, s, s * 0.18)
        d.polygon(coords, fill=255)

    def _region_polygon(self, name, s):
        digest = hashlib.sha256(str(name).encode("utf-8")).digest()
        rng = np.random.default_rng(int.from_bytes(digest[:8], "big"))
        n = 14
        radius = 0.62 + rng.random(n) * 0.50
        smooth = [(radius[i - 1] + radius[i] + radius[(i + 1) % n]) / 3.0
                  for i in range(n)]
        angles = np.linspace(-np.pi / 2, -np.pi / 2 + 2 * np.pi, n, endpoint=False)
        cx = cy = s / 2.0
        r = s * 0.36
        return [(cx + np.cos(a) * rf * r, cy + np.sin(a) * rf * r)
                for a, rf in zip(angles, smooth)]

    def _project(self, points, size, margin):
        lats = [p[0] for p in points]
        lons = [p[1] for p in points]
        min_lat, max_lat = min(lats), max(lats)
        min_lon, max_lon = min(lons), max(lons)
        span_lat = max_lat - min_lat
        span_lon = max_lon - min_lon
        inner = size - 2 * margin

        coords = []
        for lat, lon in points:
            if span_lon < 1e-12:
                x = size / 2.0
            else:
                x = margin + (lon - min_lon) / span_lon * inner
            if span_lat < 1e-12:
                y = size / 2.0
            else:
                y = margin + (max_lat - lat) / span_lat * inner
            coords.append((x, y))
        return coords

    def _heatmap(self, points, values, size):
        ys, xs = np.mgrid[0:size, 0:size].astype(np.float64)
        sigma = size * 0.11
        acc = np.zeros((size, size), dtype=np.float64)

        if points:
            pos = self._project(points, size, size * 0.16)
            weights = list(values) if values else [1.0] * len(pos)
            if len(weights) < len(pos):
                weights = weights + [1.0] * (len(pos) - len(weights))
        else:
            count = len(values)
            pos = [(size * (i + 1) / (count + 1), size / 2.0) for i in range(count)]
            weights = list(values)

        hi_w = max([abs(w) for w in weights] + [1e-9])
        for (x, y), w in zip(pos, weights):
            acc += (abs(w) / hi_w) * np.exp(
                -(((xs - x) ** 2 + (ys - y) ** 2) / (2.0 * sigma * sigma)))

        hi = float(acc.max())
        if hi > 1e-12:
            acc = acc / hi
        alpha = np.clip((acc ** 0.7) * 255.0, 0, 255).astype("uint8")

        rgba = np.zeros((size, size, 4), dtype="uint8")
        rgba[:, :, 3] = alpha
        return Image.fromarray(rgba, "RGBA")

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
