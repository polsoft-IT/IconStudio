import os
import re
import csv
import json
from PIL import Image, ImageDraw, ImageFont

from iconlib.data_icon import DataIconGenerator


FONT_CANDIDATES = ["segoeui.ttf", "arial.ttf", "calibri.ttf", "DejaVuSans.ttf"]


class DataIconBatch:
    SHEET_CELL = 128
    SHEET_COLS = 4

    def __init__(self):
        self.gen = DataIconGenerator()

    # --- MAIN ENTRY POINT ---

    def generate(self, source, out_dir, chart="line", style="fluent", size=256):
        series = self.load(source)
        if not series:
            raise ValueError("No data series found in source")

        if not os.path.isdir(out_dir):
            os.makedirs(out_dir, exist_ok=True)

        icons = []
        used = set()
        for name, values in series:
            slug = self._slug(name, used)
            sub = os.path.join(out_dir, slug)
            res = self.gen.generate(values, sub, chart, style, size)
            icons.append({
                "name": name,
                "slug": slug,
                "points": len(values),
                "data": values,
                "png": res["png"],
                "ico": res["ico"],
                "dpi": res["dpi"],
                "meta": res["meta"],
            })

        sheet = self._sheet(icons, out_dir)

        manifest_path = os.path.join(out_dir, "batch.json")
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump({
                "panel": "data-icon-batch",
                "chart": chart,
                "style": style,
                "size": size,
                "count": len(icons),
                "sheet": sheet,
                "icons": [
                    {
                        "name": i["name"],
                        "slug": i["slug"],
                        "points": i["points"],
                        "data": i["data"],
                        "png": i["png"],
                        "ico": i["ico"],
                        "dpi": i["dpi"],
                        "meta": i["meta"],
                    }
                    for i in icons
                ],
            }, f, indent=2)

        return {
            "icons": icons,
            "sheet": sheet,
            "manifest": manifest_path,
            "count": len(icons),
        }

    # --- SOURCE LOADING (CSV / JSON / text / inline) ---

    def load(self, source):
        if source is None:
            raise ValueError("Source is required")

        if os.path.isfile(source):
            ext = os.path.splitext(source)[1].lower()
            if ext == ".json":
                with open(source, "r", encoding="utf-8") as f:
                    return self._from_json(json.load(f))
            if ext == ".csv":
                with open(source, "r", encoding="utf-8", newline="") as f:
                    return self._from_rows(list(csv.reader(f)))
            with open(source, "r", encoding="utf-8") as f:
                return self._from_lines(f.read())

        return self._from_inline(str(source))

    def _from_json(self, obj):
        if isinstance(obj, dict):
            return [(str(k), self._numbers(v)) for k, v in obj.items()]

        if isinstance(obj, list):
            if not obj:
                return []
            if all(isinstance(v, (int, float)) for v in obj):
                return [("series_1", self._numbers(obj))]

            series = []
            for i, item in enumerate(obj):
                if isinstance(item, dict):
                    name = str(item.get("name", f"series_{i + 1}"))
                    raw = item.get("data", item.get("values", []))
                    series.append((name, self._numbers(raw)))
                elif isinstance(item, (list, tuple)):
                    series.append((f"series_{i + 1}", self._numbers(item)))
                else:
                    raise ValueError("Unsupported JSON series entry")
            return series

        if isinstance(obj, (int, float)):
            return [("series_1", [float(obj)])]

        raise ValueError("Unsupported JSON structure")

    def _from_rows(self, rows):
        series = []
        for row in rows:
            cells = [str(c).strip() for c in row]
            if not cells or all(c == "" for c in cells):
                continue
            if not self._is_number(cells[0]):
                rest = [c for c in cells[1:] if c != ""]
                # header / non-numeric row -> skip
                if not rest or not self._is_number(rest[0]):
                    continue
                name = cells[0] or f"series_{len(series) + 1}"
                values = self._numbers(rest)
            else:
                name = f"series_{len(series) + 1}"
                values = self._numbers(cells)
            series.append((name, values))
        return series

    def _from_lines(self, text):
        series = []
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                name, _, raw = line.partition("=")
                series.append((name.strip() or f"series_{len(series) + 1}",
                               self._numbers(raw)))
            else:
                series.append((f"series_{len(series) + 1}", self._numbers(line)))
        return series

    def _from_inline(self, text):
        series = []
        for chunk in text.split(";"):
            chunk = chunk.strip()
            if not chunk:
                continue
            if "=" in chunk:
                name, _, raw = chunk.partition("=")
                series.append((name.strip() or f"series_{len(series) + 1}",
                               self._numbers(raw)))
            else:
                series.append((f"series_{len(series) + 1}", self._numbers(chunk)))
        return series

    # --- HELPERS ---

    def _numbers(self, seq):
        if isinstance(seq, (int, float)):
            return [float(seq)]
        if isinstance(seq, str):
            seq = [p for p in re.split(r"[\s,;]+", seq.strip()) if p != ""]
        try:
            values = [float(v) for v in seq if str(v).strip() != ""]
        except (TypeError, ValueError):
            raise ValueError("Series must contain numbers only")
        if not values:
            raise ValueError("Series is empty")
        return values

    def _is_number(self, value):
        try:
            float(str(value).strip())
            return True
        except (TypeError, ValueError):
            return False

    def _slug(self, name, used):
        base = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(name)).strip("_.") or "series"
        base = base[:48]
        slug = base
        counter = 2
        while slug.lower() in used:
            slug = f"{base}_{counter}"
            counter += 1
        used.add(slug.lower())
        return slug

    def _font(self, size):
        for name in FONT_CANDIDATES:
            try:
                return ImageFont.truetype(name, size)
            except Exception:
                continue
        return ImageFont.load_default()

    def _sheet(self, icons, out_dir):
        cell = self.SHEET_CELL
        cols = min(self.SHEET_COLS, max(1, len(icons)))
        rows = (len(icons) + cols - 1) // cols

        pad, gap, label_h = 20, 16, 22
        w = pad * 2 + cols * cell + gap * (cols - 1)
        h = pad * 2 + rows * (cell + label_h) + gap * (rows - 1)

        sheet = Image.new("RGBA", (w, h), (255, 255, 255, 255))
        draw = ImageDraw.Draw(sheet)
        font = self._font(12)

        for idx, item in enumerate(icons):
            r = idx // cols
            c = idx % cols
            x0 = pad + c * (cell + gap)
            y0 = pad + r * (cell + label_h + gap)

            try:
                im = Image.open(item["png"]).convert("RGBA")
                im.thumbnail((cell - 16, cell - 16), Image.LANCZOS)
                sheet.paste(im, (x0 + (cell - im.width) // 2,
                                 y0 + (cell - im.height) // 2), im)
            except Exception:
                pass

            label = str(item["name"])[:18]
            tw = draw.textlength(label, font=font)
            draw.text((x0 + (cell - tw) / 2, y0 + cell + 2),
                      label, font=font, fill=(40, 40, 40))

        path = os.path.join(out_dir, "batch_sheet.png")
        sheet.save(path, optimize=True)
        return path
