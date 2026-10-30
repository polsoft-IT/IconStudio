import os
import json
import colorsys
import hashlib
import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

from iconlib.ai_generator import AIIconGenerator
from iconlib.fluent3d import Fluent3DGenerator
from iconlib.normalizer import IconNormalizer
from iconlib.optimizer import IconOptimizer


class Fluent3DAvatar:
    STYLES = ["fluent3d", "pastel", "glossy", "cartoon"]
    ROLES = ["developer", "designer", "admin", "manager", "engineer", "support"]
    DPI_SIZES = [16, 24, 32, 48, 64, 128, 256]

    # style -> (color, brightness, contrast, bloom, gloss)
    STYLE_SPECS = {
        "fluent3d": (0.85, 1.10, 0.95, 0.15, 0.10),
        "pastel":   (0.60, 1.16, 0.88, 0.22, 0.06),
        "glossy":   (1.00, 1.08, 1.06, 0.10, 0.20),
        "cartoon":  (1.25, 1.06, 1.15, 0.08, 0.14),
    }

    STYLE_PROMPTS = {
        "fluent3d": "fluent 3d avatar",
        "pastel": "pastel 3d avatar",
        "glossy": "glossy 3d avatar",
        "cartoon": "cartoon 3d avatar",
    }

    def __init__(self, ai_url=None, ai_key=None):
        self.ai_url = ai_url or os.environ.get("ICONSTUDIO_AI_URL")
        self.ai_key = ai_key or os.environ.get("ICONSTUDIO_AI_KEY")

    # --- MAIN ENTRY POINT ---

    def generate(self, prompt, out_dir, style="fluent3d", role=None, webp=False, sprite=False):
        if not prompt or not str(prompt).strip():
            raise ValueError("Prompt must be a non-empty avatar description")
        prompt = str(prompt).strip()
        style = str(style).strip().lower()
        if style not in self.STYLES:
            style = "fluent3d"
        role = str(role).strip().lower() if role else None

        if not os.path.isdir(out_dir):
            os.makedirs(out_dir, exist_ok=True)

        ai = AIIconGenerator(api_url=self.ai_url, api_key=self.ai_key)
        f3d = Fluent3DGenerator(ai_url=self.ai_url, ai_key=self.ai_key)

        # Step 1: base avatar (AI backend when configured, procedural Fluent face otherwise)
        base_png = os.path.join(out_dir, "avatar_base.png")
        if self.ai_url:
            ai.generate_png(self._enrich_prompt(prompt, role, style), base_png)
        else:
            self._render_face(prompt, role, style, base_png)

        # Step 2: Fluent 3D shading
        shaded_png = os.path.join(out_dir, "avatar_shaded.png")
        f3d._apply_3d_shading(base_png, shaded_png)

        # Step 3: Fluent 3D normalization
        norm_png = os.path.join(out_dir, "avatar_norm.png")
        f3d._normalize_fluent3d(shaded_png, norm_png)

        # Step 4: style pass
        styled_png = os.path.join(out_dir, "avatar.png")
        self._apply_style(norm_png, styled_png, style)

        # Step 5: normalize -> ICO
        ico_path = os.path.join(out_dir, "avatar.ico")
        IconNormalizer().normalize(styled_png, ico_path, "fluent")

        # Step 6: optimize
        opt_path = os.path.join(out_dir, "avatar_opt.ico")
        IconOptimizer().optimize_ico(ico_path, opt_path)

        # Step 7: optional WebP + sprite sheet
        webp_path = self._export_webp(styled_png, out_dir) if webp else None
        sheet_path = self._sprite_sheet(styled_png, out_dir) if sprite else None

        # Step 8: metadata
        meta_path = os.path.join(out_dir, "avatar.json")
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump({
                "panel": "avatar-3d",
                "prompt": prompt,
                "style": style,
                "role": role,
                "pipeline": ["ai-base", "3d-shading", "fluent3d-normalize",
                             "style", "normalize", "optimize"],
                "dpi": self.DPI_SIZES,
                "paths": {
                    "base": base_png,
                    "shaded": shaded_png,
                    "normalized": norm_png,
                    "png": styled_png,
                    "ico": opt_path,
                    "webp": webp_path,
                    "sheet": sheet_path,
                    "meta": meta_path,
                },
            }, f, indent=2)

        return {
            "base": base_png,
            "shaded": shaded_png,
            "normalized": norm_png,
            "png": styled_png,
            "ico": opt_path,
            "webp": webp_path,
            "sheet": sheet_path,
            "meta": meta_path,
            "style": style,
            "role": role,
        }

    # --- PROCEDURAL FLUENT FACE (offline fallback) ---

    @staticmethod
    def _hsv(h, s, v, a=255):
        r, g, b = colorsys.hsv_to_rgb(h % 1.0, s, v)
        return (int(r * 255), int(g * 255), int(b * 255), int(a))

    def _render_face(self, prompt, role, style, out_path):
        text = f"{prompt} {role or ''}".lower()
        seed = int(hashlib.sha256(text.encode("utf-8")).hexdigest()[:12], 16)
        hue = (seed % 360) / 360.0

        size = 512
        ss = 4
        u = size * ss
        cx = u // 2

        img = Image.new("RGBA", (u, u), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # pastel Fluent background card
        bg = self._hsv((hue + 0.5) % 1.0, 0.16, 0.99)
        draw.rounded_rectangle([u * 0.06, u * 0.06, u * 0.94, u * 0.94],
                               radius=u * 0.18, fill=bg)

        # palette (pastel skin, hair, accent)
        skin = self._hsv(hue, 0.24, 0.99)
        skin_sh = self._hsv(hue, 0.34, 0.88)
        hair = self._hsv((hue + 0.55) % 1.0, 0.45, 0.52)
        accent = self._hsv((hue + 0.08) % 1.0, 0.55, 0.96)
        iris = self._hsv((hue + 0.52) % 1.0, 0.52, 0.62)

        is_robot = "robot" in text or "android" in text or "bot" in text
        if is_robot:
            skin = (206, 212, 222, 255)
            skin_sh = (176, 183, 196, 255)
            hair = (96, 104, 118, 255)

        hw = u * 0.155   # head half width
        hh = u * 0.185   # head half height
        cy = u * 0.55

        # soft ground shadow
        shadow = Image.new("RGBA", (u, u), (0, 0, 0, 0))
        sd = ImageDraw.Draw(shadow)
        sd.ellipse([cx - hw * 1.15, cy + hh * 0.70, cx + hw * 1.15, cy + hh * 1.06],
                   fill=(0, 0, 0, 55))
        shadow = shadow.filter(ImageFilter.GaussianBlur(u * 0.02))
        img = Image.alpha_composite(img, shadow)
        draw = ImageDraw.Draw(img)

        # neck + ears
        draw.rounded_rectangle([cx - hw * 0.34, cy + hh * 0.72,
                                cx + hw * 0.34, cy + hh * 1.28],
                               radius=hw * 0.30, fill=skin_sh)
        draw.ellipse([cx - hw * 1.06, cy - hh * 0.12, cx - hw * 0.82, cy + hh * 0.30], fill=skin)
        draw.ellipse([cx + hw * 0.82, cy - hh * 0.12, cx + hw * 1.06, cy + hh * 0.30], fill=skin)

        # head
        draw.ellipse([cx - hw, cy - hh, cx + hw, cy + hh], fill=skin)

        # hair
        draw.ellipse([cx - hw * 1.02, cy - hh * 1.10, cx + hw * 1.02, cy - hh * 0.28], fill=hair)
        draw.ellipse([cx - hw * 1.02, cy - hh * 0.90, cx - hw * 0.72, cy + hh * 0.25], fill=hair)
        draw.ellipse([cx + hw * 0.72, cy - hh * 0.90, cx + hw * 1.02, cy + hh * 0.25], fill=hair)

        # eyes
        eye_dx = hw * 0.42
        eye_y = cy - hh * 0.08
        er = hw * 0.245
        for sgn in (-1, 1):
            ex = cx + sgn * eye_dx
            draw.ellipse([ex - er, eye_y - er * 0.9, ex + er, eye_y + er * 0.9],
                         fill=(255, 255, 255, 255))
            ir = er * 0.55
            draw.ellipse([ex - ir, eye_y - ir, ex + ir, eye_y + ir], fill=iris)
            pr = ir * 0.50
            draw.ellipse([ex - pr, eye_y - pr, ex + pr, eye_y + pr], fill=(30, 30, 40, 255))
            hr = pr * 0.55
            draw.ellipse([ex - pr + hr * 0.5, eye_y - pr - hr * 0.4,
                          ex - pr + hr * 2.2, eye_y - pr + hr * 1.0],
                         fill=(255, 255, 255, 255))
            # eyebrow
            bw = hw * 0.30
            by = eye_y - er * 1.9
            draw.line([ex - bw, by, ex + bw, by], fill=hair, width=int(u * 0.011))

        # nose
        draw.line([cx, cy + hh * 0.05, cx - hw * 0.10, cy + hh * 0.26],
                  fill=skin_sh, width=int(u * 0.008))

        # smile
        mw = hw * 0.42
        my = cy + hh * 0.46
        draw.arc([cx - mw, my - mw * 0.85, cx + mw, my + mw * 0.85],
                 start=20, end=160, fill=(150, 70, 80, 255), width=int(u * 0.012))

        # blush (translucent overlay)
        blush = Image.new("RGBA", (u, u), (0, 0, 0, 0))
        bd = ImageDraw.Draw(blush)
        for sgn in (-1, 1):
            bx = cx + sgn * hw * 0.68
            by = cy + hh * 0.30
            rr = hw * 0.22
            bd.ellipse([bx - rr, by - rr, bx + rr, by + rr],
                       fill=self._hsv((hue + 0.97) % 1.0, 0.55, 0.95, 110))
        blush = blush.filter(ImageFilter.GaussianBlur(u * 0.02))
        img = Image.alpha_composite(img, blush)
        draw = ImageDraw.Draw(img)

        visor = self._make_visor(text, u, cx, eye_y, hw, er, hue)
        if visor is not None:
            img = Image.alpha_composite(img, visor)
            draw = ImageDraw.Draw(img)

        self._draw_accessories(draw, text, role, u, cx, cy, hw, hh, er,
                               eye_dx, eye_y, hue, accent, is_robot)

        img.resize((size, size), Image.LANCZOS).save(out_path, format="PNG")
        return out_path

    def _make_visor(self, text, u, cx, eye_y, hw, er, hue):
        if not ("cyberpunk" in text or "hacker" in text or "neon" in text):
            return None
        lw = int(u * 0.010)
        visor = Image.new("RGBA", (u, u), (0, 0, 0, 0))
        vd = ImageDraw.Draw(visor)
        box = [cx - hw * 0.95, eye_y - er * 1.30, cx + hw * 0.95, eye_y + er * 1.30]
        vd.rounded_rectangle(box, radius=er * 0.8,
                             fill=self._hsv((hue + 0.55) % 1.0, 0.85, 1.0, 150))
        vd.rounded_rectangle(box, radius=er * 0.8,
                             outline=self._hsv((hue + 0.55) % 1.0, 0.9, 1.0), width=lw)
        return visor.filter(ImageFilter.GaussianBlur(u * 0.006))

    def _draw_accessories(self, draw, text, role, u, cx, cy, hw, hh, er,
                          eye_dx, eye_y, hue, accent, is_robot):
        lw = int(u * 0.010)

        if is_robot:
            draw.line([cx, cy - hh * 1.0, cx, cy - hh * 1.5], fill=accent, width=lw * 2)
            draw.ellipse([cx - hw * 0.09, cy - hh * 1.63,
                          cx + hw * 0.09, cy - hh * 1.45], fill=accent)

        if "glass" in text or role == "developer":
            frame = self._hsv((hue + 0.5) % 1.0, 0.35, 0.35)
            for sgn in (-1, 1):
                ex = cx + sgn * eye_dx
                draw.rounded_rectangle([ex - er * 1.15, eye_y - er * 1.05,
                                        ex + er * 1.15, eye_y + er * 1.05],
                                       radius=er * 0.5, outline=frame, width=lw)
            draw.line([cx - er * 0.8, eye_y, cx + er * 0.8, eye_y], fill=frame, width=lw)

        if "headset" in text or "support" in text or role == "support":
            draw.arc([cx - hw * 1.25, cy - hh * 1.25, cx + hw * 1.25, cy + hh * 0.55],
                     start=200, end=340, fill=accent, width=lw * 2)
            for sgn in (-1, 1):
                ex = cx + sgn * hw * 1.12
                draw.rounded_rectangle([ex - hw * 0.12, cy - hh * 0.10,
                                        ex + hw * 0.12, cy + hh * 0.35],
                                       radius=hw * 0.10, fill=accent)

        if "cap" in text or role == "engineer" or role == "manager":
            draw.pieslice([cx - hw * 1.05, cy - hh * 1.42, cx + hw * 1.05, cy - hh * 0.05],
                          start=180, end=360, fill=accent)
            draw.rounded_rectangle([cx - hw * 1.18, cy - hh * 0.44,
                                    cx + hw * 1.18, cy - hh * 0.24],
                                   radius=hw * 0.10, fill=accent)

    # --- PROMPT ENRICHMENT ---

    def _enrich_prompt(self, prompt, role, style):
        bits = [prompt]
        if role:
            bits.append(f"{role} role")
        bits.append(self.STYLE_PROMPTS.get(style, "fluent 3d avatar"))
        bits.append("soft shadows, glossy highlights, pastel colors, expressive face, person avatar")
        return ", ".join(bits)

    # --- STYLE PASS ---

    def _apply_style(self, src, dst, style):
        color, bright, contrast, bloom, gloss = self.STYLE_SPECS.get(
            style, self.STYLE_SPECS["fluent3d"])

        img = Image.open(src).convert("RGBA")
        if color != 1.0:
            img = ImageEnhance.Color(img).enhance(color)
        if bright != 1.0:
            img = ImageEnhance.Brightness(img).enhance(bright)
        if contrast != 1.0:
            img = ImageEnhance.Contrast(img).enhance(contrast)

        arr = np.array(img).copy()
        if bloom > 0:
            bl = np.array(img.filter(ImageFilter.GaussianBlur(8)))
            arr[:, :, :3] = (arr[:, :, :3] * (1.0 - bloom) + bl[:, :, :3] * bloom).astype("uint8")
        if gloss > 0:
            gl = np.array(img.filter(ImageFilter.GaussianBlur(3)))
            arr[:, :, :3] = (arr[:, :, :3] * (1.0 - gloss) + gl[:, :, :3] * gloss).astype("uint8")

        Image.fromarray(arr, "RGBA").save(dst, optimize=True)
        return dst

    # --- OPTIONAL OUTPUTS ---

    def _export_webp(self, src, out_dir):
        path = os.path.join(out_dir, "avatar.webp")
        try:
            Image.open(src).convert("RGBA").save(path, format="WEBP", lossless=True)
            return path
        except Exception:
            return None

    def _sprite_sheet(self, src, out_dir):
        path = os.path.join(out_dir, "avatar_sheet.png")
        try:
            base = Image.open(src).convert("RGBA")
            pad = 8
            width = sum(self.DPI_SIZES) + pad * (len(self.DPI_SIZES) + 1)
            height = max(self.DPI_SIZES) + pad * 2
            sheet = Image.new("RGBA", (width, height), (255, 255, 255, 0))
            x = pad
            for s in self.DPI_SIZES:
                thumb = base.resize((s, s), Image.LANCZOS)
                sheet.paste(thumb, (x, (height - s) // 2), thumb)
                x += s + pad
            sheet.save(path, optimize=True)
            return path
        except Exception:
            return None
