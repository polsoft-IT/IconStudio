import os
import json
from PIL import Image, ImageDraw, ImageFont

from iconlib.ui_mapper import IconUIMapper
from iconlib.color_analysis import IconColorAnalysis


# Named UI element types described by the spec, plus common aliases.
UI_ALIASES = {
    "button": "button",
    "toggle": "toggle",
    "checkbox": "checkbox",
    "check": "checkbox",
    "radio": "radio",
    "slider": "slider",
    "progress": "progress",
    "input": "input",
    "textbox": "input",
    "search": "search",
    "search box": "search",
    "searchbox": "search",
    "dropdown": "dropdown",
    "combo": "dropdown",
    "toolbar": "toolbar",
    "toolbar button": "toolbar",
    "toolbar_button": "toolbar",
    "ribbon": "ribbon",
    "ribbon tile": "ribbon",
    "ribbon_tile": "ribbon",
    "sidebar": "sidebar",
    "sidebar item": "sidebar",
    "sidebar_item": "sidebar",
    "menu": "menu",
    "menu item": "menu",
    "menu_item": "menu",
}


class UIAssetPipeline:
    def __init__(self, cache):
        self.cache = cache

    # --- MAIN ENTRY POINT ---

    def build(self, id_, ui_type, out_dir):
        if not os.path.isdir(out_dir):
            os.makedirs(out_dir)

        # Step 1: analyze icon
        mapper = IconUIMapper()
        color = IconColorAnalysis()

        path = self.cache.meta[id_]["path"]
        icon_meta = mapper.map_action(path)
        color_meta = color.analyze(path)

        ui_type = UI_ALIASES.get(str(ui_type).strip().lower(), str(ui_type).strip().lower())

        # Step 2: generate UI element
        if ui_type == "button":
            return self._button(id_, icon_meta, color_meta, out_dir)

        if ui_type == "toggle":
            return self._toggle(id_, icon_meta, color_meta, out_dir)

        if ui_type == "menu":
            return self._menu(id_, icon_meta, color_meta, out_dir)

        if ui_type == "toolbar":
            return self._toolbar(id_, icon_meta, color_meta, out_dir)

        if ui_type in ("checkbox", "radio", "slider", "progress",
                       "input", "search", "dropdown", "ribbon", "sidebar"):
            return self._generic(id_, ui_type, icon_meta, color_meta, out_dir)

        raise Exception("Unknown UI type")

    # --- HELPERS ---

    def _thumb(self, id_, size):
        thumb = self.cache.thumb64.get(id_)
        if thumb is None:
            img = Image.open(self.cache.meta[id_]["path"]).convert("RGBA")
            thumb = img.resize((size, size), Image.LANCZOS)
        return thumb.resize((size, size), Image.LANCZOS)

    def _bg_color(self, color_meta):
        palette = color_meta.get("palette") or [(255, 255, 255)]
        bg = palette[0]
        return tuple(int(c) for c in bg[:3])

    def _save(self, out_dir, name, img, meta):
        preview = os.path.join(out_dir, f"{name}.png")
        img.save(preview, optimize=True)

        meta_path = os.path.join(out_dir, f"{name}.json")
        with open(meta_path, "w") as f:
            json.dump(meta, f, indent=2)

        self._write_css(out_dir, name, meta)

        return {"preview": preview, "meta": meta_path}

    def _write_css(self, out_dir, name, meta):
        css_path = os.path.join(out_dir, f"{name}.css")
        action = str(meta.get("action", "")).replace(" ", "-")
        lines = [
            f".ui-{name} {{",
            f"  /* action: {action} */",
            "  border-radius: 12px;",
            "  padding: 8px 16px;",
            "  display: inline-flex;",
            "  align-items: center;",
            "}",
        ]
        with open(css_path, "w") as f:
            f.write("\n".join(lines) + "\n")
        return css_path

    def _font(self, size=14):
        try:
            return ImageFont.truetype("arial.ttf", size)
        except Exception:
            return ImageFont.load_default()

    def _center_text(self, draw, box, text, font, fill):
        x0, y0, x1, y1 = box
        bbox = draw.textbbox((0, 0), text, font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        draw.text((x0 + (x1 - x0 - tw) // 2, y0 + (y1 - y0 - th) // 2 - bbox[1]),
                  text, fill=fill, font=font)

    # --- BUTTON ---

    def _button(self, id_, icon_meta, color_meta, out_dir):
        thumb = self._thumb(id_, 64)
        w, h = 200, 64

        img = Image.new("RGBA", (w, h), (255, 255, 255, 0))
        draw = ImageDraw.Draw(img)

        bg = self._bg_color(color_meta)
        draw.rounded_rectangle((0, 0, w, h), radius=12, fill=bg)

        img.paste(thumb, (16, (h - 64) // 2), thumb)

        font = self._font(14)
        draw.text((90, 22), str(icon_meta["action"]), fill=(0, 0, 0), font=font)

        meta = {
            "type": "button",
            "action": icon_meta["action"],
            "color": color_meta,
            "icon": id_,
        }
        return self._save(out_dir, "button", img, meta)

    # --- TOGGLE ---

    def _toggle(self, id_, icon_meta, color_meta, out_dir):
        thumb = self._thumb(id_, 64)
        w, h = 200, 64

        img = Image.new("RGBA", (w, h), (255, 255, 255, 0))
        draw = ImageDraw.Draw(img)

        draw.rounded_rectangle((0, 0, w, h), radius=12, fill=(230, 230, 230))
        draw.ellipse((8, 8, 56, 56), fill=(255, 255, 255))

        img.paste(thumb, (120, (h - 64) // 2), thumb)

        meta = {
            "type": "toggle",
            "action": icon_meta["action"],
            "icon": id_,
        }
        return self._save(out_dir, "toggle", img, meta)

    # --- MENU ITEM ---

    def _menu(self, id_, icon_meta, color_meta, out_dir):
        thumb = self._thumb(id_, 48)
        w, h = 240, 48

        img = Image.new("RGBA", (w, h), (255, 255, 255, 0))
        draw = ImageDraw.Draw(img)

        draw.rectangle((0, 0, w, h), fill=(245, 245, 245))
        img.paste(thumb, (8, 0), thumb)

        font = self._font(14)
        draw.text((64, 16), str(icon_meta["action"]), fill=(0, 0, 0), font=font)

        meta = {
            "type": "menu",
            "action": icon_meta["action"],
            "icon": id_,
        }
        return self._save(out_dir, "menu", img, meta)

    # --- TOOLBAR BUTTON ---

    def _toolbar(self, id_, icon_meta, color_meta, out_dir):
        thumb = self._thumb(id_, 64)
        w, h = 64, 64

        img = Image.new("RGBA", (w, h), (255, 255, 255, 0))
        img.paste(thumb, (0, 0), thumb)

        meta = {
            "type": "toolbar",
            "action": icon_meta["action"],
            "icon": id_,
        }
        return self._save(out_dir, "toolbar", img, meta)

    # --- GENERIC ELEMENTS ---

    def _generic(self, id_, ui_type, icon_meta, color_meta, out_dir):
        specs = {
            "checkbox": (200, 40, "checkbox"),
            "radio": (200, 40, "radio"),
            "slider": (220, 40, "slider"),
            "progress": (220, 40, "progress"),
            "input": (220, 40, "input"),
            "search": (240, 40, "search"),
            "dropdown": (220, 40, "dropdown"),
            "ribbon": (96, 96, "ribbon"),
            "sidebar": (64, 200, "sidebar"),
        }
        w, h, name = specs[ui_type]

        thumb_size = 32 if ui_type != "ribbon" else 48
        thumb = self._thumb(id_, thumb_size)

        img = Image.new("RGBA", (w, h), (255, 255, 255, 0))
        draw = ImageDraw.Draw(img)

        bg = self._bg_color(color_meta)
        draw.rounded_rectangle((0, 0, w - 1, h - 1), radius=8, fill=(245, 245, 245))

        if ui_type == "checkbox":
            draw.rectangle((8, 8, 32, 32), outline=(90, 90, 90), width=2)
            img.paste(thumb, (8, 4), thumb)
        elif ui_type == "radio":
            draw.ellipse((8, 8, 32, 32), outline=(90, 90, 90), width=2)
            img.paste(thumb, (8, 4), thumb)
        elif ui_type == "slider":
            draw.line((40, 20, w - 12, 20), fill=(180, 180, 180), width=4)
            draw.ellipse((70, 8, 94, 32), fill=bg)
            img.paste(thumb, (4, 4), thumb)
        elif ui_type == "progress":
            draw.rounded_rectangle((40, 12, w - 12, 28), radius=8, fill=(210, 210, 210))
            draw.rounded_rectangle((40, 12, 40 + int((w - 52) * 0.6), 28), radius=8, fill=bg)
            img.paste(thumb, (4, 4), thumb)
        elif ui_type == "dropdown":
            draw.rectangle((8, 6, w - 24, h - 6), outline=(180, 180, 180), width=1)
            draw.polygon([(w - 20, 18), (w - 12, 18), (w - 16, 24)], fill=(90, 90, 90))
            img.paste(thumb, (12, 4), thumb)
        elif ui_type == "search":
            draw.ellipse((12, 8, 32, 28), outline=(120, 120, 120), width=2)
            draw.line((30, 26, 38, 34), fill=(120, 120, 120), width=2)
            draw.line((48, 20, w - 12, 20), fill=(200, 200, 200), width=2)
            img.paste(thumb, (w - 40, 4), thumb)
        elif ui_type == "input":
            draw.rectangle((8, 6, w - 8, h - 6), outline=(180, 180, 180), width=1)
            img.paste(thumb, (12, 4), thumb)
        elif ui_type == "ribbon":
            img.paste(thumb, ((w - 48) // 2, 12), thumb)
            self._center_text(draw, (0, 64, w, 92), str(icon_meta["action"])[:8],
                              self._font(11), (40, 40, 40))
        elif ui_type == "sidebar":
            img.paste(thumb, ((w - 32) // 2, (h - 32) // 2 - 8), thumb)
            self._center_text(draw, (0, (h + 24) // 2, w, h - 8),
                              str(icon_meta["action"])[:8], self._font(10), (40, 40, 40))

        meta = {
            "type": ui_type,
            "action": icon_meta["action"],
            "icon": id_,
        }
        return self._save(out_dir, name, img, meta)
