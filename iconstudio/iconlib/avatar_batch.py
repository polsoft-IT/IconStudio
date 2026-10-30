import os
import re
import csv
import json
from PIL import Image, ImageDraw, ImageFont

from iconlib.avatar3d import Fluent3DAvatar


FONT_CANDIDATES = ["segoeui.ttf", "arial.ttf", "calibri.ttf", "DejaVuSans.ttf"]


class Fluent3DAvatarBatch:
    """Roster -> many Fluent 3D avatars + contact sheet + manifest."""

    SHEET_CELL = 128
    SHEET_COLS = 4
    DEFAULT_STYLE = "fluent3d"

    def __init__(self, ai_url=None, ai_key=None):
        self.ai_url = ai_url
        self.ai_key = ai_key

    # --- MAIN ENTRY POINT ---

    def generate(self, source, out_dir, style=DEFAULT_STYLE):
        entries = self.load(source)
        if not entries:
            raise ValueError("No roster entries found in source")

        if not os.path.isdir(out_dir):
            os.makedirs(out_dir, exist_ok=True)

        avatars = []
        used = set()
        for name, role, prompt, entry_style in entries:
            slug = self._slug(name, used)
            sub = os.path.join(out_dir, slug)
            style_used = entry_style or style
            res = Fluent3DAvatar(ai_url=self.ai_url, ai_key=self.ai_key).generate(
                prompt, sub, style_used, role=role)
            avatars.append({
                "name": name,
                "slug": slug,
                "role": role,
                "prompt": prompt,
                "style": res["style"],
                "png": res["png"],
                "ico": res["ico"],
                "base": res["base"],
                "meta": res["meta"],
            })

        sheet = self._sheet(avatars, out_dir)

        manifest_path = os.path.join(out_dir, "batch.json")
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump({
                "panel": "avatar-3d-batch",
                "style": style,
                "count": len(avatars),
                "sheet": sheet,
                "avatars": avatars,
            }, f, indent=2)

        return {
            "avatars": avatars,
            "sheet": sheet,
            "manifest": manifest_path,
            "count": len(avatars),
        }

    # --- SOURCE LOADING (CSV / JSON / text / inline) ---

    def load(self, source):
        if source is None or str(source).strip() == "":
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
            entries = []
            for k, v in obj.items():
                entries.append(self._entry(k, v if isinstance(v, str) else None,
                                           v if isinstance(v, dict) else None))
            return entries

        if isinstance(obj, list):
            entries = []
            for i, item in enumerate(obj):
                if isinstance(item, dict):
                    entries.append(self._entry(
                        item.get("name", f"avatar_{i + 1}"),
                        item.get("prompt", item.get("description")),
                        item))
                else:
                    entries.append(self._entry(str(item), str(item), None))
            return entries

        if isinstance(obj, str):
            return self._from_inline(obj)

        raise ValueError("Unsupported JSON structure")

    def _from_rows(self, rows):
        entries = []
        for row in rows:
            cells = [str(c).strip() for c in row]
            if not cells or all(c == "" for c in cells):
                continue
            low = [c.lower() for c in cells]
            if "name" in low and ("prompt" in low or "description" in low):
                continue  # header row
            entries.append(self._row_entry(cells, len(entries) + 1))
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
        for chunk in text.split(";"):
            chunk = chunk.strip()
            if not chunk:
                continue
            entries.append(self._token_entry(chunk, len(entries) + 1))
        return entries

    # --- ENTRY NORMALIZATION ---

    def _entry(self, name, prompt, spec):
        name = str(name).strip() or "avatar"
        role = None
        style = None
        if isinstance(spec, dict):
            role = spec.get("role") or None
            style = spec.get("style") or None
            prompt = spec.get("prompt", spec.get("description", prompt))
        if prompt is None:
            prompt = name
        return (name, str(role).strip().lower() if role else None,
                str(prompt).strip(), str(style).strip().lower() if style else None)

    def _row_entry(self, cells, idx):
        name = cells[0] or f"avatar_{idx}"
        role = cells[1] if len(cells) > 1 else None
        prompt = cells[2] if len(cells) > 2 else None
        style = cells[3] if len(cells) > 3 else None
        return self._entry(name, prompt or name, {"role": role, "style": style})

    def _token_entry(self, token, idx):
        if "|" in token:
            parts = [p.strip() for p in token.split("|")]
            name = parts[0] or f"avatar_{idx}"
            role = parts[1] if len(parts) > 1 and parts[1] else None
            prompt = parts[2] if len(parts) > 2 and parts[2] else name
            style = parts[3] if len(parts) > 3 and parts[3] else None
            return self._entry(name, prompt, {"role": role, "style": style})

        if "=" in token:
            name, _, prompt = token.partition("=")
            return self._entry(name.strip() or f"avatar_{idx}",
                               prompt.strip() or name.strip(), None)

        return self._entry(token.strip(), token, None)

    # --- HELPERS ---

    def _slug(self, name, used):
        base = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(name)).strip("_.") or "avatar"
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

    def _sheet(self, avatars, out_dir):
        cell = self.SHEET_CELL
        cols = min(self.SHEET_COLS, max(1, len(avatars)))
        rows = (len(avatars) + cols - 1) // cols

        pad, gap, label_h = 20, 16, 22
        w = pad * 2 + cols * cell + gap * (cols - 1)
        h = pad * 2 + rows * (cell + label_h) + gap * (rows - 1)

        sheet = Image.new("RGBA", (w, h), (255, 255, 255, 255))
        draw = ImageDraw.Draw(sheet)
        font = self._font(12)

        for idx, item in enumerate(avatars):
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
