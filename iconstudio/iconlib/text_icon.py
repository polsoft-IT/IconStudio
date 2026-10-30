import os
import json
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance

from iconlib.normalizer import IconNormalizer
from iconlib.optimizer import IconOptimizer


FONT_CANDIDATES = ["arial.ttf", "segoeui.ttf", "calibri.ttf", "DejaVuSans.ttf"]


class TextIconGenerator:
    STYLES = ["fluent", "monochrome", "outline", "classic"]

    def __init__(self):
        pass

    # --- MAIN ENTRY POINT ---

    def generate(self, text, out_dir, style="fluent", size=256):
        if not os.path.isdir(out_dir):
            os.makedirs(out_dir)

        # Step 1: glyph -> raster
        png_path = os.path.join(out_dir, "glyph.png")
        self._glyph_to_png(text, png_path, size, style)

        # Step 2: style transform
        styled_path = os.path.join(out_dir, "styled.png")
        self._apply_style(png_path, styled_path, style)

        # Step 3: normalize DPI + ICO
        norm = IconNormalizer()
        ico_path = os.path.join(out_dir, "glyph.ico")
        norm.normalize(styled_path, ico_path, style)

        # Step 4: optimize
        opt = IconOptimizer()
        opt_path = os.path.join(out_dir, "glyph_opt.ico")
        opt.optimize_ico(ico_path, opt_path)

        # Step 5: metadata + sprite sheet
        meta_path = os.path.join(out_dir, "glyph.json")
        self._metadata(meta_path, text, style, size)

        sprite_path = os.path.join(out_dir, "glyph_sprite.png")
        self._sprite_sheet(styled_path, sprite_path)

        return {
            "png": styled_path,
            "ico": opt_path,
            "meta": meta_path,
            "sprite": sprite_path,
        }

    # --- TEXT -> GLYPH PNG ---

    def _glyph_to_png(self, text, out_path, size, style):
        img = Image.new("RGBA", (size, size), (255, 255, 255, 0))
        draw = ImageDraw.Draw(img)

        font = self._fit_font(draw, text, size)

        bbox = draw.textbbox((0, 0), text, font=font)
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
        x = (size - w) // 2 - bbox[0]
        y = (size - h) // 2 - bbox[1]

        draw.text((x, y), text, fill=(0, 0, 0), font=font)
        img.save(out_path, optimize=True)
        return out_path

    def _fit_font(self, draw, text, size):
        target = int(size * 0.85)
        font_size = int(size * 0.6)
        while font_size > 8:
            font = self._load_font(font_size)
            bbox = draw.textbbox((0, 0), text, font=font)
            if (bbox[2] - bbox[0]) <= target and (bbox[3] - bbox[1]) <= target:
                return font
            font_size -= 4
        return self._load_font(10)

    def _load_font(self, font_size):
        for name in FONT_CANDIDATES:
            try:
                return ImageFont.truetype(name, font_size)
            except Exception:
                continue
        return ImageFont.load_default()

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
            gray = img.convert("L")
            arr = np.array(gray)
            rgba = np.zeros((arr.shape[0], arr.shape[1], 4), dtype=np.uint8)
            rgba[:, :, 0] = arr
            rgba[:, :, 1] = arr
            rgba[:, :, 2] = arr
            rgba[:, :, 3] = np.array(img)[:, :, 3]
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

    # --- SPRITE SHEET ---

    def _sprite_sheet(self, src, out_path):
        img = Image.open(src).convert("RGBA")
        sizes = [16, 24, 32, 48, 64, 128, 256]
        frames = [img.resize((s, s), Image.LANCZOS) for s in sizes]

        w = sum(f.width for f in frames)
        h = max(f.height for f in frames)
        sheet = Image.new("RGBA", (w, h), (255, 255, 255, 0))

        x = 0
        for f in frames:
            sheet.paste(f, (x, h - f.height), f)
            x += f.width

        sheet.save(out_path, optimize=True)
        return out_path

    # --- METADATA ---

    def _metadata(self, out_path, text, style, size):
        data = {
            "text": text,
            "style": style,
            "size": size,
            "dpi": [16, 24, 32, 48, 64, 128, 256],
        }
        with open(out_path, "w") as f:
            json.dump(data, f, indent=2)
        return out_path
