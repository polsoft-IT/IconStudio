"""
IconStudio UI Theme Engine
ASCII-only.

Turns a single icon into a complete UI theme:
colors -> gradients -> shadows -> components -> presets -> export.

Integrates with the existing pipeline:
    iconlib.color_analysis, iconlib.style_analysis, iconlib.ui_assets
"""

import json
import os
import zipfile

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from iconlib.color_analysis import IconColorAnalysis
from iconlib.dpi_generator import DPIGenerator
from iconlib.layout import IconLayoutEngine
from iconlib.style_analysis import IconStyleAnalysis
from iconlib.text_icon import TextIconGenerator
from iconlib.transform import IconTransform
from iconlib.ui_assets import UIAssetPipeline


# UI components generated for every theme pack.
THEME_COMPONENTS = (
    "button", "toggle", "checkbox", "radio", "slider", "progress",
    "input", "search", "dropdown", "toolbar", "menu", "sidebar",
)

# Style presets: geometry + effect scalars.
STYLE_PRESETS = {
    "fluent":     {"radius": 12, "blur": 8, "shadow_alpha": 60, "elevation": 1.0, "desaturate": False},
    "classic":    {"radius": 3,  "blur": 4, "shadow_alpha": 40, "elevation": 0.6, "desaturate": False},
    "monochrome": {"radius": 8,  "blur": 6, "shadow_alpha": 45, "elevation": 0.8, "desaturate": True},
}

# Surface styles: panel / card geometry + effect references.
SURFACE_SPECS = {
    "panel":         {"w": 320, "h": 190, "gradient": None,      "shadow": "sm", "radius_scale": 1.0, "inset": False, "icon": True},
    "card":          {"w": 240, "h": 150, "gradient": None,      "shadow": "md", "radius_scale": 1.0, "inset": False, "icon": False},
    "card_elevated": {"w": 240, "h": 150, "gradient": "surface", "shadow": "lg", "radius_scale": 1.2, "inset": False, "icon": False},
    "panel_inset":   {"w": 320, "h": 130, "gradient": None,      "shadow": None, "radius_scale": 1.0, "inset": True,  "icon": False},
    "list_row":      {"w": 320, "h": 52,  "gradient": None,      "shadow": None, "radius_scale": 0.6, "inset": False, "icon": True},
    "header":        {"w": 320, "h": 64,  "gradient": "primary", "shadow": "sm", "radius_scale": 1.0, "inset": False, "icon": False},
}

# Theme-matched icon variants (recolored from the base icon using palette roles).
ICON_VARIANTS = (
    ("primary", "primary"),
    ("primary_dark", "primary_dark"),
    ("accent", "accent"),
    ("muted", "text_muted"),
    ("on_surface", "text"),
)

# 3D / depth treatments applied to the primary icon variant (iconlib.transform).
ICON_EFFECTS = ("bevel", "glow", "extrude")

# UI composition previews built from the base icon (iconlib.layout).
LAYOUT_TYPES = ("toolbar", "grid", "sidebar")

# Typography specimens rendered in theme colors (iconlib.text_icon).
TYPOGRAPHY_SAMPLES = (("title", "Aa"), ("accent", "Ab"), ("numeral", "42"))


def _clamp(v):
    return max(0, min(255, int(round(v))))


def _shift(rgb, delta):
    return [_clamp(rgb[0] + delta), _clamp(rgb[1] + delta), _clamp(rgb[2] + delta)]


def _mix(a, b, t):
    return [_clamp(a[i] + (b[i] - a[i]) * t) for i in range(3)]


def _lum(rgb):
    return 0.299 * rgb[0] + 0.587 * rgb[1] + 0.114 * rgb[2]


def _hex(rgb):
    return "#%02x%02x%02x" % (int(rgb[0]), int(rgb[1]), int(rgb[2]))


def _rgb(rgb):
    return tuple(int(c) for c in rgb[:3])


def _on(rgb):
    return (255, 255, 255) if _lum(rgb) < 140 else (20, 20, 20)


class UIThemeGenerator:
    """Generates a production-ready UI theme pack from a base icon."""

    def __init__(self, cache):
        self.cache = cache

    # --- MAIN ENTRY POINT ---

    def generate(self, base_id, out_dir, style="fluent"):
        if base_id not in self.cache.meta:
            raise ValueError(f"Icon with id {base_id} not found in cache")

        if not os.path.isdir(out_dir):
            os.makedirs(out_dir, exist_ok=True)

        style = str(style).strip().lower()
        if style not in STYLE_PRESETS:
            style = "fluent"

        path = self.cache.meta[base_id]["path"]
        color_meta = IconColorAnalysis().analyze(path)
        style_meta = IconStyleAnalysis().analyze(path)

        # Step 1: colors
        palette = self._build_palette(color_meta, style)
        gradients = self._build_gradients(palette)
        shadows = self._build_shadows(palette, style)
        effects = self._build_effects(style_meta, style)

        # Step 2: components
        components, errors = self._build_components(base_id, out_dir)

        # Step 2b: surface styles (panels / cards) + theme-matched icon set
        surfaces = self._build_surfaces(base_id, palette, gradients, shadows, effects, out_dir)
        icons = self._build_icon_set(base_id, palette, out_dir)

        # Step 2c: UI compositions + typography specimens
        layouts = self._build_layouts(base_id, out_dir)
        typography = self._build_typography(palette, out_dir)

        # Step 3: preview sheet + component sprite sheet
        preview = self._build_preview(palette, gradients, shadows, effects,
                                      components, surfaces, icons, layouts,
                                      typography, out_dir, base_id, style)
        sheet = self._build_sheet(components, out_dir)

        # Step 4: design tokens (json / css / ini)
        tokens = self._build_tokens(palette, gradients, shadows, effects,
                                    components, surfaces, icons, layouts,
                                    typography, style, base_id, path, out_dir)

        # Step 5: pack everything
        pack = self._pack(out_dir)

        return {
            "palette": palette,
            "gradients": gradients,
            "shadows": shadows,
            "effects": effects,
            "components": components,
            "surfaces": surfaces,
            "icons": icons,
            "layouts": layouts,
            "typography": typography,
            "preview": preview,
            "sheet": sheet,
            "tokens": tokens,
            "pack": pack,
            "errors": errors,
        }

    # --- PALETTE GENERATION ---

    def _build_palette(self, color_meta, style):
        preset = STYLE_PRESETS[style]
        dominant = color_meta.get("dominant") or (0, 120, 215)
        primary = [int(c) for c in dominant[:3]]

        if preset["desaturate"]:
            g = _clamp(_lum(primary))
            primary = [g, g, g]

        accent = _shift(primary, 30 if preset["desaturate"] else 46)
        classic = style == "classic"

        return {
            "primary": primary,
            "primary_dark": _shift(primary, -44),
            "primary_light": _shift(primary, 72),
            "accent": accent,
            "accent_soft": _mix(accent, [255, 255, 255], 0.74),
            "background": [238, 238, 238] if classic else [243, 245, 249],
            "surface": [255, 255, 255],
            "surface_alt": [222, 222, 222] if classic else [230, 234, 241],
            "border": [198, 203, 212],
            "text": [24, 26, 32],
            "text_muted": [112, 117, 128],
            "success": [64, 160, 43],
            "warning": [223, 142, 29],
            "danger": [210, 15, 57],
            "shadow": [0, 0, 0, preset["shadow_alpha"]],
        }

    # --- GRADIENTS ---

    def _build_gradients(self, palette):
        return [
            {"name": "primary", "from": palette["primary_dark"],
             "to": palette["primary_light"], "angle": 90},
            {"name": "accent", "from": palette["accent"],
             "to": palette["primary"], "angle": 90},
            {"name": "surface", "from": palette["surface"],
             "to": palette["surface_alt"], "angle": 180},
            {"name": "glass", "from": _mix(palette["surface"], palette["primary_light"], 0.28),
             "to": palette["surface_alt"], "angle": 135},
        ]

    # --- SHADOWS ---

    def _build_shadows(self, palette, style):
        alpha = STYLE_PRESETS[style]["shadow_alpha"]
        blur = STYLE_PRESETS[style]["blur"]
        return {
            "sm": {"color": [0, 0, 0, alpha // 2], "blur": max(1, blur // 2), "offset": [0, 1]},
            "md": {"color": [0, 0, 0, alpha], "blur": max(1, blur), "offset": [0, 3]},
            "lg": {"color": [0, 0, 0, alpha], "blur": blur * 2, "offset": [0, 8]},
        }

    # --- EFFECTS ---

    def _build_effects(self, style_meta, style):
        preset = STYLE_PRESETS[style]
        return {
            "bloom": bool(style_meta.get("saturation", 0) > 60),
            "depth": bool(style_meta.get("shading", False)),
            "ambient_occlusion": bool(style_meta.get("shading", False)),
            "accent_glow": bool(style_meta.get("gradient", False)),
            "detected_style": style_meta.get("style", "unknown"),
            "radius": preset["radius"],
            "elevation": preset["elevation"],
        }

    # --- COMPONENT GENERATION ---

    def _build_components(self, base_id, out_dir):
        pipe = UIAssetPipeline(self.cache)
        comps = {}
        errors = []
        root = os.path.join(out_dir, "components")

        for kind in THEME_COMPONENTS:
            target = os.path.join(root, kind)
            try:
                res = pipe.build(base_id, kind, target)
                meta = {}
                try:
                    with open(res["meta"], "r", encoding="utf-8") as f:
                        meta = json.load(f)
                except Exception:
                    pass
                comps[kind] = {
                    "preview": res["preview"],
                    "meta": res["meta"],
                    "css": os.path.join(target, f"{kind}.css"),
                    "action": meta.get("action", ""),
                    "icon": base_id,
                }
            except Exception as e:
                errors.append({"component": kind, "error": str(e)})

        return comps, errors

    # --- SURFACE STYLES (PANELS / CARDS) ---

    def _build_surfaces(self, base_id, palette, gradients, shadows, effects, out_dir):
        root = os.path.join(out_dir, "surfaces")
        os.makedirs(root, exist_ok=True)

        grad_map = {g["name"]: g for g in gradients}
        results = {}

        for name, spec in SURFACE_SPECS.items():
            img = self._render_surface(name, spec, base_id, palette, grad_map,
                                       shadows, effects)
            path = os.path.join(root, f"{name}.png")
            img.save(path, optimize=True)
            results[name] = {
                "preview": path,
                "radius": max(2, int(round(effects["radius"] * spec["radius_scale"]))),
                "shadow": spec["shadow"],
                "gradient": spec["gradient"],
                "inset": spec["inset"],
            }

        return results

    def _render_surface(self, name, spec, base_id, palette, grad_map, shadows, effects):
        w, h = spec["w"], spec["h"]
        radius = max(2, int(round(effects["radius"] * spec["radius_scale"])))

        sh_key = spec["shadow"]
        sh = shadows.get(sh_key) if sh_key else None
        pad = 12
        if sh:
            pad = max(pad, sh["blur"] * 2 + abs(sh["offset"][1]) * 2 + 10)

        canvas = Image.new("RGBA", (w + pad * 2, h + pad * 2), (0, 0, 0, 0))

        if sh:
            ox, oy = sh["offset"]
            layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
            ImageDraw.Draw(layer).rounded_rectangle(
                (pad + ox, pad + oy, pad + ox + w, pad + oy + h),
                radius=radius, fill=(0, 0, 0, sh["color"][3]))
            layer = layer.filter(ImageFilter.GaussianBlur(max(1, sh["blur"])))
            canvas = Image.alpha_composite(canvas, layer)

        gname = spec["gradient"]
        base_col = palette["surface_alt"] if spec["inset"] else palette["surface"]
        if gname and gname in grad_map:
            g = grad_map[gname]
            body = self._rounded_fill((w, h), radius, g["from"], g["to"])
            text_col = _on(_mix(g["from"], g["to"], 0.5))
            sub_col = text_col
        else:
            body = self._rounded_fill((w, h), radius, base_col, base_col)
            text_col = _rgb(palette["text"])
            sub_col = _rgb(palette["text_muted"])

        canvas.alpha_composite(body, (pad, pad))

        d = ImageDraw.Draw(canvas)
        d.rounded_rectangle((pad, pad, pad + w - 1, pad + h - 1), radius=radius,
                            outline=_rgb(palette["border"]), width=1)

        if spec["inset"]:
            d.rounded_rectangle((pad + 2, pad + 2, pad + w - 3, pad + h - 3),
                                radius=max(2, radius - 2),
                                outline=tuple(_mix(palette["surface"], [0, 0, 0], 0.08)) + (255,),
                                width=1)

        f_t = self._font(14)
        f_s = self._font(11)

        tx = pad + 16
        if spec["icon"] and h >= 96:
            thumb = self._surface_thumb(base_id, 28)
            if thumb is not None:
                canvas.alpha_composite(thumb, (tx, pad + 16))
                tx += 38

        d = ImageDraw.Draw(canvas)
        d.text((tx, pad + 16), name.replace("_", " ").title(), font=f_t, fill=text_col)
        d.text((tx, pad + 38), f"radius {radius}px", font=f_s, fill=sub_col)

        if h >= 130:
            for i in range(3):
                ly = pad + 72 + i * 16
                lw = int((w - 32) * (0.9 - i * 0.18))
                d.rounded_rectangle((pad + 16, ly, pad + 16 + lw, ly + 8),
                                    radius=4, fill=tuple(_mix(base_col, palette["border"], 0.45)) + (255,))

        return canvas

    def _rounded_fill(self, size, radius, c1, c2):
        w, h = size
        grad = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        gd = ImageDraw.Draw(grad)
        for y in range(h):
            gd.line((0, y, w, y), fill=tuple(_mix(c1, c2, y / max(1, h - 1))))
        mask = Image.new("L", (w, h), 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, w - 1, h - 1),
                                               radius=radius, fill=255)
        grad.putalpha(mask)
        return grad

    def _surface_thumb(self, base_id, size):
        try:
            thumb = Image.open(self.cache.meta[base_id]["path"]).convert("RGBA")
        except Exception:
            return None
        thumb.thumbnail((size, size), Image.LANCZOS)
        cell = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        cell.alpha_composite(thumb, ((size - thumb.width) // 2,
                                     (size - thumb.height) // 2))
        return cell

    # --- THEME-MATCHED ICON SET ---

    def _build_icon_set(self, base_id, palette, out_dir):
        root = os.path.join(out_dir, "icons")
        os.makedirs(root, exist_ok=True)

        src = Image.open(self.cache.meta[base_id]["path"]).convert("RGBA")
        cell = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
        src.thumbnail((256, 256), Image.LANCZOS)
        cell.alpha_composite(src, ((256 - src.width) // 2, (256 - src.height) // 2))

        variants = {}
        for name, role in ICON_VARIANTS:
            tinted = self._tint(cell, palette[role])
            path = os.path.join(root, f"{name}.png")
            tinted.save(path, optimize=True)
            variants[name] = path

        try:
            ico_path = os.path.join(root, "icon_set.ico")
            DPIGenerator().generate_dpi_set(variants["primary"], ico_path)
            variants["ico"] = ico_path
        except Exception:
            pass

        sheet = self._icon_sheet(variants, root)
        effects = self._build_effect_icons(variants["primary"], out_dir)

        return {
            "variants": {k: v for k, v in variants.items() if k != "ico"},
            "ico": variants.get("ico"),
            "sheet": sheet,
            "effects": effects,
        }

    def _build_effect_icons(self, primary_png, out_dir):
        root = os.path.join(out_dir, "icons", "effects")
        os.makedirs(root, exist_ok=True)

        tr = IconTransform()
        variants = {}
        for mode in ICON_EFFECTS:
            path = os.path.join(root, f"{mode}.png")
            try:
                tr.transform(primary_png, path, mode)
                variants[mode] = path
            except Exception:
                continue

        sheet = self._compose_sheet(
            [(m, p) for m, p in variants.items()],
            os.path.join(out_dir, "icons", "effects_sheet.png"))

        return {"variants": variants, "sheet": sheet}

    def _tint(self, img, color):
        arr = np.array(img).astype(float)
        rgb = arr[:, :, :3]
        lum = (0.299 * rgb[:, :, 0] + 0.587 * rgb[:, :, 1] +
               0.114 * rgb[:, :, 2]) / 255.0
        tgt = np.array([color[0], color[1], color[2]], dtype=float)
        out = tgt[None, None, :] * (0.35 + 0.65 * lum[:, :, None])
        arr[:, :, :3] = np.clip(out, 0, 255)
        return Image.fromarray(arr.astype("uint8"), "RGBA")

    def _icon_sheet(self, variants, root):
        names = [n for n, _ in ICON_VARIANTS if n in variants]
        return self._compose_sheet([(n, variants[n]) for n in names],
                                   os.path.join(root, "icons_sheet.png"))

    def _compose_sheet(self, items, path, cell=96):
        cells = []
        for name, src in items:
            im = self._open_img(src)
            if im is not None:
                cells.append((name, im))
        if not cells:
            return None

        pad, gap = 16, 12
        w = pad * 2 + len(cells) * cell + gap * (len(cells) - 1)
        h = pad * 2 + cell + 20
        sheet = Image.new("RGBA", (max(w, 1), h), (255, 255, 255, 255))
        d = ImageDraw.Draw(sheet)
        f = self._font(11)
        x = pad
        for name, im in cells:
            im = im.copy()
            im.thumbnail((cell, cell), Image.LANCZOS)
            d.text((x, pad), name, font=f, fill=(45, 45, 45))
            sheet.paste(im, (x + (cell - im.width) // 2, pad + 22), im)
            x += cell + gap

        sheet.save(path, optimize=True)
        return path

    def _open_img(self, src):
        try:
            return Image.open(src).convert("RGBA")
        except Exception:
            return None

    # --- UI COMPOSITIONS (iconlib.layout) ---

    def _build_layouts(self, base_id, out_dir):
        root = os.path.join(out_dir, "layouts")
        os.makedirs(root, exist_ok=True)

        engine = IconLayoutEngine()
        layouts = {}
        for layout_type in LAYOUT_TYPES:
            try:
                res = engine.layout([base_id], layout_type, self.cache, root)
                layouts[layout_type] = res["preview"]
            except Exception:
                continue
        return layouts

    # --- TYPOGRAPHY SPECIMENS (iconlib.text_icon) ---

    def _build_typography(self, palette, out_dir):
        root = os.path.join(out_dir, "typography")
        os.makedirs(root, exist_ok=True)

        roles = {"title": palette["text"], "accent": palette["primary"],
                 "numeral": palette["accent"]}
        gen = TextIconGenerator()
        specimens = {}
        for name, text in TYPOGRAPHY_SAMPLES:
            sub = os.path.join(root, name)
            try:
                res = gen.generate(text, sub, "fluent", 128)
                im = self._tint(Image.open(res["png"]).convert("RGBA"),
                                roles.get(name, palette["text"]))
                path = os.path.join(root, f"{name}.png")
                im.save(path, optimize=True)
                specimens[name] = path
            except Exception:
                continue

        sheet = self._compose_sheet([(n, p) for n, p in specimens.items()],
                                    os.path.join(out_dir, "typography_sheet.png"))

        return {"specimens": specimens, "sheet": sheet}

    # --- PREVIEW SHEET ---

    def _build_preview(self, palette, gradients, shadows, effects,
                       components, surfaces, icons, layouts, typography,
                       out_dir, base_id, style):
        W, H = 900, 1800
        img = Image.new("RGBA", (W, H), _rgb(palette["surface_alt"]) + (255,))

        f_big = self._font(22)
        f_med = self._font(14)
        f_sm = self._font(12)
        f_xs = self._font(10)

        # Header band with primary gradient.
        header = Image.new("RGBA", (W, 66), _rgb(palette["primary"]) + (255,))
        hd = ImageDraw.Draw(header)
        for x in range(W):
            hd.line((x, 0, x, 66),
                    fill=tuple(_mix(palette["primary_dark"], palette["primary_light"], x / W)))
        img.paste(header, (0, 0))

        draw = ImageDraw.Draw(img)
        on = _on(palette["primary"])
        draw.text((24, 12), "UI THEME ENGINE", font=f_big, fill=on)
        draw.text((24, 42),
                  f"base icon #{base_id}   |   style {style}   |   "
                  f"radius {effects['radius']}px",
                  font=f_sm, fill=on)

        # Color roles.
        y = 96
        draw.text((24, y), "COLOR ROLES", font=f_med, fill=_rgb(palette["text"]))
        y += 24
        swatches = [
            ("primary", palette["primary"]),
            ("primary_light", palette["primary_light"]),
            ("primary_dark", palette["primary_dark"]),
            ("accent", palette["accent"]),
            ("background", palette["background"]),
            ("surface", palette["surface"]),
            ("border", palette["border"]),
            ("text", palette["text"]),
        ]
        cw, ch, gap = 100, 54, 6
        for i, (name, col) in enumerate(swatches):
            x = 24 + i * (cw + gap)
            draw.rounded_rectangle((x, y, x + cw, y + ch), radius=8,
                                   fill=_rgb(col), outline=_rgb(palette["border"]))
            draw.text((x + 4, y + ch + 3), name, font=f_xs,
                      fill=_rgb(palette["text_muted"]))
        y += ch + 26

        # Gradients.
        draw.text((24, y), "GRADIENTS", font=f_med, fill=_rgb(palette["text"]))
        y += 24
        for g in gradients:
            self._draw_gradient(draw, (24, y, 24 + 820, y + 20), g["from"], g["to"])
            draw.text((24 + 828, y + 4), g["name"], font=f_xs,
                      fill=_rgb(palette["text_muted"]))
            y += 28
        y += 10

        # Shadows.
        draw.text((24, y), "SHADOWS / EFFECTS", font=f_med, fill=_rgb(palette["text"]))
        y += 22
        card_y = y + 14
        for i, key in enumerate(("sm", "md", "lg")):
            img = self._paste_shadow_card(img, 24 + i * 270, card_y, 220, 58,
                                          shadows[key], palette, shadows[key]["blur"] + 6,
                                          f"{key} elevation", f_sm)
        y = card_y + 58 + shadows["lg"]["blur"] * 2 + 26

        # Components grid.
        draw = ImageDraw.Draw(img)
        draw.text((24, y), "COMPONENTS", font=f_med, fill=_rgb(palette["text"]))
        y += 22
        cx, cy, col = 24, y, 0
        for name, comp in components.items():
            try:
                cimg = Image.open(comp["preview"]).convert("RGBA")
            except Exception:
                continue
            cimg.thumbnail((250, 92), Image.LANCZOS)
            draw.text((cx, cy), name, font=f_xs, fill=_rgb(palette["text_muted"]))
            img.paste(cimg, (cx, cy + 14), cimg)
            col += 1
            cx += 288
            if col == 3:
                col = 0
                cx = 24
                cy += 128
        y = cy + 128 + 10

        # Surface styles (panels / cards).
        draw = ImageDraw.Draw(img)
        draw.text((24, y), "SURFACE STYLES", font=f_med, fill=_rgb(palette["text"]))
        y += 24
        sx, sy, scol = 24, y, 0
        for name, surf in surfaces.items():
            try:
                simg = Image.open(surf["preview"]).convert("RGBA")
            except Exception:
                continue
            simg.thumbnail((262, 160), Image.LANCZOS)
            draw.text((sx, sy), name, font=f_xs, fill=_rgb(palette["text_muted"]))
            img.paste(simg, (sx, sy + 14), simg)
            scol += 1
            sx += 288
            if scol == 3:
                scol = 0
                sx = 24
                sy += 196
        y = sy + 196

        # Theme-matched icon set.
        draw = ImageDraw.Draw(img)
        draw.text((24, y), "ICON SET (THEME-MATCHED)", font=f_med, fill=_rgb(palette["text"]))
        y += 24
        ix = 24
        for name, ipath in icons.get("variants", {}).items():
            iimg = self._open_img(ipath)
            if iimg is None:
                continue
            iimg.thumbnail((64, 64), Image.LANCZOS)
            draw.text((ix, y), name, font=f_xs, fill=_rgb(palette["text_muted"]))
            img.paste(iimg, (ix, y + 14), iimg)
            ix += 96
        y += 84

        # 3D / depth icon treatments.
        draw = ImageDraw.Draw(img)
        draw.text((24, y), "ICON EFFECTS", font=f_med, fill=_rgb(palette["text"]))
        y += 24
        ex = 24
        for name, epath in icons.get("effects", {}).get("variants", {}).items():
            eimg = self._open_img(epath)
            if eimg is None:
                continue
            eimg.thumbnail((72, 72), Image.LANCZOS)
            draw.text((ex, y), name, font=f_xs, fill=_rgb(palette["text_muted"]))
            img.paste(eimg, (ex, y + 14), eimg)
            ex += 104
        y += 92

        # UI compositions (toolbar / grid / sidebar).
        draw = ImageDraw.Draw(img)
        draw.text((24, y), "UI COMPOSITIONS", font=f_med, fill=_rgb(palette["text"]))
        y += 24
        lx, ly = 24, y
        for name, lpath in layouts.items():
            limg = self._open_img(lpath)
            if limg is None:
                continue
            limg.thumbnail((250, 120), Image.LANCZOS)
            draw.text((lx, ly), name, font=f_xs, fill=_rgb(palette["text_muted"]))
            img.paste(limg, (lx, ly + 14), limg)
            lx += 288
        y += 148

        # Typography specimens.
        draw = ImageDraw.Draw(img)
        draw.text((24, y), "TYPOGRAPHY", font=f_med, fill=_rgb(palette["text"]))
        y += 24
        tx = 24
        for name, tpath in typography.get("specimens", {}).items():
            timg = self._open_img(tpath)
            if timg is None:
                continue
            timg.thumbnail((72, 72), Image.LANCZOS)
            draw.text((tx, y), name, font=f_xs, fill=_rgb(palette["text_muted"]))
            img.paste(timg, (tx, y + 14), timg)
            tx += 104
        y += 92

        img = img.crop((0, 0, W, min(H, y)))
        preview_path = os.path.join(out_dir, "theme_preview.png")
        img.save(preview_path, optimize=True)
        return preview_path

    def _draw_gradient(self, draw, box, c1, c2):
        x0, y0, x1, y1 = box
        steps = max(1, x1 - x0)
        for i in range(steps):
            draw.line((x0 + i, y0, x0 + i, y1), fill=tuple(_mix(c1, c2, i / steps)))

    def _paste_shadow_card(self, img, x, y, w, h, shadow, palette, radius, label, font):
        blur = max(1, shadow["blur"])
        pad = blur * 2 + 8
        ox, oy = shadow["offset"]
        alpha = shadow["color"][3]

        layer = Image.new("RGBA", (w + pad * 2, h + pad * 2), (0, 0, 0, 0))
        ld = ImageDraw.Draw(layer)
        ld.rounded_rectangle((pad + ox, pad + oy, pad + ox + w, pad + oy + h),
                             radius=radius, fill=(0, 0, 0, alpha))
        layer = layer.filter(ImageFilter.GaussianBlur(blur))

        full = Image.new("RGBA", img.size, (0, 0, 0, 0))
        full.paste(layer, (x - pad, y - pad), layer)
        img = Image.alpha_composite(img, full)

        d = ImageDraw.Draw(img)
        d.rounded_rectangle((x, y, x + w, y + h), radius=radius,
                            fill=_rgb(palette["surface"]), outline=_rgb(palette["border"]))
        d.text((x + 14, y + h // 2 - 8), label, font=font, fill=_rgb(palette["text"]))
        return img

    # --- COMPONENT SPRITE SHEET ---

    def _build_sheet(self, components, out_dir):
        pad, gap, cell_h = 16, 16, 122
        items = []
        for name, comp in components.items():
            try:
                im = Image.open(comp["preview"]).convert("RGBA")
            except Exception:
                continue
            im.thumbnail((220, cell_h - 34), Image.LANCZOS)
            items.append((name, im))

        if not items:
            return None

        w = pad * 2 + sum(im.width for _, im in items) + gap * (len(items) - 1)
        h = pad * 2 + cell_h
        sheet = Image.new("RGBA", (max(w, 1), h), (255, 255, 255, 255))
        d = ImageDraw.Draw(sheet)
        f = self._font(11)
        x = pad
        for name, im in items:
            d.text((x, pad), name, font=f, fill=(45, 45, 45))
            sheet.paste(im, (x, pad + 20), im)
            x += im.width + gap

        path = os.path.join(out_dir, "components_sheet.png")
        sheet.save(path, optimize=True)
        return path

    # --- DESIGN TOKENS ---

    def _build_tokens(self, palette, gradients, shadows, effects,
                      components, surfaces, icons, layouts, typography,
                      style, base_id, path, out_dir):
        tokens = {
            "name": f"iconstudio-theme-{base_id}",
            "style": style,
            "source": {"icon_id": base_id, "path": path},
            "colors": palette,
            "gradients": gradients,
            "shadows": shadows,
            "effects": effects,
            "components": {
                name: {
                    "type": name,
                    "action": comp.get("action", ""),
                    "icon": comp.get("icon"),
                }
                for name, comp in components.items()
            },
            "surfaces": {
                name: {
                    "radius": surf["radius"],
                    "shadow": surf["shadow"],
                    "gradient": surf["gradient"],
                    "inset": surf["inset"],
                }
                for name, surf in surfaces.items()
            },
            "icons": {
                "variants": icons.get("variants", {}),
                "effects": icons.get("effects", {}).get("variants", {}),
                "ico": icons.get("ico"),
            },
            "layouts": layouts,
            "typography": typography.get("specimens", {}),
        }

        json_path = os.path.join(out_dir, "theme.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(tokens, f, indent=2)

        css_path = self._write_css(palette, gradients, shadows, effects,
                                   surfaces, style, out_dir)
        ini_path = self._write_ini(palette, effects, components, surfaces,
                                   icons, layouts, typography, style, out_dir)

        return {"json": json_path, "css": css_path, "ini": ini_path}

    def _write_css(self, palette, gradients, shadows, effects, surfaces, style, out_dir):
        lines = [":root {", f"  /* style: {style} */"]
        for key, val in palette.items():
            if key == "shadow":
                continue
            lines.append(f"  --color-{key.replace('_', '-')}: {_hex(val)};")
        lines.append(f"  --shadow-color: rgba(0, 0, 0, {palette['shadow'][3] / 255:.2f});")
        for g in gradients:
            lines.append(f"  --gradient-{g['name']}: "
                         f"linear-gradient({g['angle']}deg, {_hex(g['from'])}, {_hex(g['to'])});")
        for name, sh in shadows.items():
            ox, oy = sh["offset"]
            lines.append(f"  --shadow-{name}: {ox}px {oy}px {sh['blur']}px "
                         f"rgba(0, 0, 0, {sh['color'][3] / 255:.2f});")
        lines.append(f"  --radius: {effects['radius']}px;")
        lines.append(f"  --elevation: {effects['elevation']};")
        lines.append("}")

        for name, surf in surfaces.items():
            shadow = f"var(--shadow-{surf['shadow']})" if surf["shadow"] else "none"
            if surf["gradient"]:
                fill = f"var(--gradient-{surf['gradient']})"
            else:
                fill = "var(--color-surface-alt)" if surf["inset"] else "var(--color-surface)"
            lines.append("")
            lines.append(f".ui-{name.replace('_', '-')} {{")
            lines.append(f"  background: {fill};")
            lines.append(f"  border-radius: {surf['radius']}px;")
            lines.append(f"  box-shadow: {shadow};")
            lines.append(f"  padding: {12 if surf['inset'] else 16}px;")
            lines.append("}")

        path = os.path.join(out_dir, "theme.css")
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        return path

    def _write_ini(self, palette, effects, components, surfaces,
                   icons, layouts, typography, style, out_dir):
        lines = ["[Theme]", f"style={style}", "generator=IconStudio UIThemeGenerator", ""]
        lines.append("[Colors]")
        for key, val in palette.items():
            if key == "shadow":
                lines.append(f"shadow_rgba={','.join(str(c) for c in val)}")
            else:
                lines.append(f"{key}={_hex(val)}")
        lines.append("")
        lines.append("[Effects]")
        for key, val in effects.items():
            lines.append(f"{key}={val}")
        lines.append("")
        lines.append("[Components]")
        for name, comp in components.items():
            lines.append(f"{name}={comp.get('action', '')}")
        lines.append("")
        lines.append("[Surfaces]")
        for name, surf in surfaces.items():
            lines.append(f"{name}=radius:{surf['radius']},"
                         f"shadow:{surf['shadow'] or 'none'},"
                         f"gradient:{surf['gradient'] or 'none'},"
                         f"inset:{surf['inset']}")
        lines.append("")
        lines.append("[Icons]")
        for name, ipath in icons.get("variants", {}).items():
            lines.append(f"{name}={os.path.basename(ipath)}")
        if icons.get("ico"):
            lines.append(f"ico={os.path.basename(icons['ico'])}")
        lines.append("")
        lines.append("[IconEffects]")
        for name, epath in icons.get("effects", {}).get("variants", {}).items():
            lines.append(f"{name}={os.path.basename(epath)}")
        lines.append("")
        lines.append("[Layouts]")
        for name, lpath in layouts.items():
            lines.append(f"{name}={os.path.basename(lpath)}")
        lines.append("")
        lines.append("[Typography]")
        for name, tpath in typography.get("specimens", {}).items():
            lines.append(f"{name}={os.path.basename(tpath)}")

        path = os.path.join(out_dir, "theme.ini")
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        return path

    # --- PACK ---

    def _pack(self, out_dir):
        pack_path = os.path.join(out_dir, "themepack.zip")
        exts = (".png", ".json", ".css", ".ini")
        with zipfile.ZipFile(pack_path, "w", zipfile.ZIP_DEFLATED) as z:
            for root, _dirs, files in os.walk(out_dir):
                for fn in files:
                    if not fn.lower().endswith(exts):
                        continue
                    full = os.path.join(root, fn)
                    rel = os.path.relpath(full, out_dir)
                    z.write(full, rel)
        return pack_path

    # --- HELPERS ---

    def _font(self, size):
        for name in ("segoeui.ttf", "arial.ttf", "DejaVuSans.ttf"):
            try:
                return ImageFont.truetype(name, size)
            except Exception:
                continue
        return ImageFont.load_default()
