import os
import re
import csv
import json
from PIL import Image, ImageDraw, ImageFont

from iconlib.texture_icon import TextureIconGenerator


FONT_CANDIDATES = ["segoeui.ttf", "arial.ttf", "calibri.ttf", "DejaVuSans.ttf"]


class TextureIconBatch:
    """Many procedural textures (folder/CSV/JSON/TXT/inline) -> icons + sheet + manifest."""

    SHEET_CELL = 128
    SHEET_COLS = 4
    DEFAULT_STYLE = "fluent"

    def __init__(self):
        self.gen = TextureIconGenerator()

    # --- MAIN ENTRY POINT ---

    def generate(self, source, out_dir, style=DEFAULT_STYLE, size=256):
        entries = self.load(source)
        if not entries:
            raise ValueError("No textures found in source")

        if not os.path.isdir(out_dir):
            os.makedirs(out_dir, exist_ok=True)

        icons = []
        used = set()
        for name, texture, entry_style, entry_seed in entries:
            slug = self._slug(name, used)
            sub = os.path.join(out_dir, slug)
            res = self.gen.generate(
                texture, sub, entry_style or style, size, entry_seed)
            icons.append({
                "name": name,
                "slug": slug,
                "texture": res["texture_name"],
                "style": entry_style or style,
                "seed": res["seed"],
                "png": res["png"],
                "ico": res["ico"],
                "dpi": res["dpi"],
                "meta": res["meta"],
            })

        sheet = self._sheet(icons, out_dir)

        manifest_path = os.path.join(out_dir, "batch.json")
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump({
                "panel": "texture-icon-batch",
                "style": style,
                "size": size,
                "count": len(icons),
                "sheet": sheet,
                "icons": icons,
            }, f, indent=2)

        return {
            "icons": icons,
            "sheet": sheet,
            "manifest": manifest_path,
            "count": len(icons),
        }

    # --- SOURCE LOADING (folder / CSV / JSON / text / inline) ---

    def load(self, source):
        if source is None or str(source).strip() == "":
            raise ValueError("Source is required")

        if os.path.isdir(source):
            return self._from_dir(source)

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

    def _from_dir(self, folder):
        entries = []
        exts = (".json", ".csv", ".txt")
        for fn in sorted(os.listdir(folder)):
            path = os.path.join(folder, fn)
            if not os.path.isfile(path):
                continue
            ext = os.path.splitext(fn)[1].lower()
            if ext not in exts:
                continue
            stem = os.path.splitext(fn)[0]
            try:
                if ext == ".json":
                    with open(path, "r", encoding="utf-8") as f:
                        parsed = self._from_json(json.load(f))
                elif ext == ".csv":
                    with open(path, "r", encoding="utf-8", newline="") as f:
                        parsed = self._from_rows(list(csv.reader(f)))
                else:
                    with open(path, "r", encoding="utf-8") as f:
                        parsed = self._from_lines(f.read())
            except Exception:
                continue
            for i, (_name, texture, style, seed) in enumerate(parsed):
                nm = stem if len(parsed) == 1 else f"{stem}_{i + 1}"
                entries.append((nm, texture, style, seed))
        return entries

    def _from_json(self, obj):
        if isinstance(obj, list):
            entries = []
            for i, item in enumerate(obj):
                if isinstance(item, dict):
                    entries.append(self._entry_from_dict(item, f"texture_{i + 1}"))
                else:
                    entries.append((f"texture_{i + 1}", item, None, None))
            return entries

        if isinstance(obj, dict):
            if "texture" in obj:
                return [self._entry_from_dict(obj, "texture_1")]
            entries = []
            for key, value in obj.items():
                if isinstance(value, dict):
                    entries.append(self._entry_from_dict(value, str(key)))
                else:
                    entries.append((str(key), value, None, None))
            return entries

        return [("texture_1", obj, None, None)]

    def _entry_from_dict(self, item, default_name):
        name = str(item.get("name", default_name))
        texture = item.get("texture")
        style = item.get("style")
        seed = item.get("seed")
        return self._entry(name, texture, style, seed)

    def _from_rows(self, rows):
        entries = []
        for row in rows:
            cells = [str(c).strip() for c in row]
            if not cells or all(c == "" for c in cells):
                continue
            low = [c.lower() for c in cells]
            if "texture" in low or "name" in low:
                continue  # header row
            name = cells[0] or f"texture_{len(entries) + 1}"
            texture = cells[1] if len(cells) > 1 and cells[1] else cells[0]
            style = cells[2] if len(cells) > 2 and cells[2] else None
            seed = cells[3] if len(cells) > 3 and cells[3] else None
            entries.append(self._entry(name, texture, style, seed))
        return entries

    def _from_lines(self, text):
        entries = []
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            entries.append(self._token_entry(line, len(entries) + 1))
        return entries

    def _from_inline(self, text):
        entries = []
        for chunk in re.split(r"\n|//", text):
            chunk = chunk.strip()
            if not chunk:
                continue
            entries.append(self._token_entry(chunk, len(entries) + 1))
        return entries

    # --- ENTRY NORMALIZATION ---

    def _entry(self, name, texture, style, seed):
        name = str(name).strip() or "texture"
        texture = str(texture).strip().lower() if texture else None
        style = str(style).strip().lower() if style else None
        seed = self._as_int(seed)
        return (name, texture, style, seed)

    def _token_entry(self, token, index):
        if "|" in token:
            parts = [p.strip() for p in token.split("|")]
            name = parts[0] or f"texture_{index}"
            texture = parts[1] if len(parts) > 1 and parts[1] else None
            style = parts[2] if len(parts) > 2 and parts[2] else None
            seed = parts[3] if len(parts) > 3 and parts[3] else None
        else:
            name = token
            texture = token
            style = None
            seed = None
        return self._entry(name, texture, style, seed)

    @staticmethod
    def _as_int(value):
        if value is None or value == "":
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    # --- HELPERS ---

    def _slug(self, name, used):
        base = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(name)).strip("_.") or "texture"
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
