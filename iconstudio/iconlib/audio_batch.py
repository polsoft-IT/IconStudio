import os
import re
import csv
import json
from PIL import Image, ImageDraw, ImageFont

from iconlib.audio_icon import AudioIconGenerator


FONT_CANDIDATES = ["segoeui.ttf", "arial.ttf", "calibri.ttf", "DejaVuSans.ttf"]


class AudioIconBatch:
    """Folder/list of recordings -> many audio icons + contact sheet + manifest."""

    SHEET_CELL = 128
    SHEET_COLS = 4
    DEFAULT_STYLE = "fluent"
    DEFAULT_MODE = "waveform"

    def __init__(self):
        pass

    # --- MAIN ENTRY POINT ---

    def generate(self, source, out_dir, style=DEFAULT_STYLE, size=256, mode=DEFAULT_MODE,
                 palette=False):
        entries = self.load(source)
        if not entries:
            raise ValueError("No audio files found in source")

        if not os.path.isdir(out_dir):
            os.makedirs(out_dir, exist_ok=True)

        icons = []
        used = set()
        for name, path, entry_style, entry_mode in entries:
            slug = self._slug(name, used)
            sub = os.path.join(out_dir, slug)
            res = AudioIconGenerator().generate(
                path, sub, entry_style or style, size, entry_mode or mode,
                palette=palette)
            icons.append({
                "name": name,
                "slug": slug,
                "source": path,
                "style": entry_style or style,
                "mode": res["mode"],
                "audio": res["audio"],
                "palette": res["palette"],
                "png": res["png"],
                "ico": res["ico"],
                "dpi": res["dpi"],
                "meta": res["meta"],
            })

        sheet = self._sheet(icons, out_dir)

        manifest_path = os.path.join(out_dir, "batch.json")
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump({
                "panel": "audio-icon-batch",
                "style": style,
                "mode": mode,
                "size": size,
                "palette": bool(palette),
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
        for fn in sorted(os.listdir(folder)):
            path = os.path.join(folder, fn)
            if not os.path.isfile(path):
                continue
            if os.path.splitext(fn)[1].lower() not in AudioIconGenerator.AUDIO_EXTS:
                continue
            entries.append(self._entry(os.path.splitext(fn)[0], path, None, None))
        return entries

    def _from_json(self, obj):
        if isinstance(obj, list):
            entries = []
            for i, item in enumerate(obj):
                if isinstance(item, dict):
                    path = item.get("path") or item.get("file") or item.get("source")
                    if not path:
                        continue
                    name = item.get("name") or os.path.splitext(os.path.basename(str(path)))[0]
                    entries.append(self._entry(name, path, item.get("style"), item.get("mode")))
                else:
                    path = str(item)
                    name = os.path.splitext(os.path.basename(path))[0] or f"audio_{i + 1}"
                    entries.append(self._entry(name, path, None, None))
            return self._existing(entries)
        raise ValueError("Unsupported JSON structure")

    def _from_rows(self, rows):
        entries = []
        for row in rows:
            cells = [str(c).strip() for c in row]
            if not cells or all(c == "" for c in cells):
                continue
            low = [c.lower() for c in cells]
            if "path" in low or "file" in low or "source" in low:
                continue  # header row
            path = cells[0]
            name = cells[1] if len(cells) > 1 and cells[1] else None
            entry_style = cells[2] if len(cells) > 2 and cells[2] else None
            entry_mode = cells[3] if len(cells) > 3 and cells[3] else None
            if not name:
                name = os.path.splitext(os.path.basename(path))[0]
            entries.append(self._entry(name, path, entry_style, entry_mode))
        return self._existing(entries)

    def _from_lines(self, text):
        entries = []
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            entries.append(self._token_entry(line))
        return self._existing(entries)

    def _from_inline(self, text):
        entries = []
        for chunk in text.split(";"):
            chunk = chunk.strip()
            if not chunk:
                continue
            entries.append(self._token_entry(chunk))
        return self._existing(entries)

    # --- ENTRY NORMALIZATION ---

    def _entry(self, name, path, style, mode):
        name = str(name).strip() or "audio"
        return (name, str(path).strip(),
                str(style).strip().lower() if style else None,
                str(mode).strip().lower() if mode else None)

    def _token_entry(self, token):
        if "|" in token:
            parts = [p.strip() for p in token.split("|")]
            path = parts[0]
            name = parts[1] if len(parts) > 1 and parts[1] else None
            style = parts[2] if len(parts) > 2 and parts[2] else None
            mode = parts[3] if len(parts) > 3 and parts[3] else None
        else:
            path = token
            name = style = mode = None
        if not name:
            name = os.path.splitext(os.path.basename(path))[0] or "audio"
        return self._entry(name, path, style, mode)

    def _existing(self, entries):
        return [e for e in entries if os.path.isfile(e[1])]

    # --- HELPERS ---

    def _slug(self, name, used):
        base = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(name)).strip("_.") or "audio"
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
