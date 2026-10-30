import os
import json
import hashlib
import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

from iconlib.normalizer import IconNormalizer
from iconlib.optimizer import IconOptimizer
from iconlib.dpi_generator import DPIGenerator


# 12 gradient directions used by the Simplex noise implementation.
_GRAD3 = np.array([
    [1, 1, 0], [-1, 1, 0], [1, -1, 0], [-1, -1, 0],
    [1, 0, 1], [-1, 0, 1], [1, 0, -1], [-1, 0, -1],
    [0, 1, 1], [0, -1, 1], [0, 1, -1], [0, -1, -1],
], dtype=np.float64)


def _fade(t):
    return t * t * t * (t * (t * 6.0 - 15.0) + 10.0)


class TextureIconGenerator:
    """texture/noise/pattern/material -> raster -> style -> ICO."""

    TEXTURES = ["perlin", "simplex", "worley", "grain", "metal", "carbon",
                "wood", "marble", "dots", "grid", "stripes", "waves"]
    STYLES = ["fluent", "monochrome", "outline", "classic"]
    SIZE_MIN = 128
    SIZE_MAX = 512
    CORNER_RADIUS = 0.18

    def __init__(self):
        pass

    # --- MAIN ENTRY POINT ---

    def generate(self, texture, out_dir, style="fluent", size=256, seed=None):
        texture = str(texture).strip().lower()
        if texture not in self.TEXTURES:
            texture = "perlin"
        style = str(style).strip().lower()
        if style not in self.STYLES:
            style = "fluent"
        size = int(max(self.SIZE_MIN, min(self.SIZE_MAX, int(size))))
        if seed is None:
            seed = int.from_bytes(
                hashlib.sha256(texture.encode("utf-8")).digest()[:8], "big")
        seed = int(seed)
        rng = np.random.default_rng(seed)

        if not os.path.isdir(out_dir):
            os.makedirs(out_dir, exist_ok=True)

        # Step 1: texture -> PNG
        tex_path = os.path.join(out_dir, "texture.png")
        self._texture_to_png(texture, tex_path, size, rng)

        # Step 2: texture -> styled PNG
        styled_path = os.path.join(out_dir, "styled.png")
        self._apply_style(tex_path, styled_path, style)

        # Step 3: normalize -> multi-DPI ICO
        ico_path = os.path.join(out_dir, "texture.ico")
        IconNormalizer().normalize(styled_path, ico_path, style)

        # Step 4: optimize
        opt_path = os.path.join(out_dir, "texture_opt.ico")
        IconOptimizer().optimize_ico(ico_path, opt_path)

        # Step 5: explicit DPI set
        dpi_path = os.path.join(out_dir, "texture_dpi.ico")
        try:
            DPIGenerator().generate_dpi_set(styled_path, dpi_path)
        except Exception:
            dpi_path = None

        # Step 6: metadata
        meta_path = os.path.join(out_dir, "texture.json")
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump({
                "panel": "texture-icon",
                "texture": texture,
                "style": style,
                "size": size,
                "seed": seed,
                "outputs": {
                    "texture": tex_path,
                    "png": styled_path,
                    "ico": opt_path,
                    "dpi": dpi_path,
                    "meta": meta_path,
                },
            }, f, indent=2)

        return {
            "png": styled_path,
            "texture": tex_path,
            "ico": opt_path,
            "dpi": dpi_path,
            "meta": meta_path,
            "texture_name": texture,
            "seed": seed,
        }

    # --- TEXTURE -> PNG ---

    def _texture_to_png(self, texture, out_path, size, rng):
        arr = self._pattern(texture, size, rng)
        arr = self._normalize(arr)
        gray = np.clip(arr * 255.0, 0, 255).astype("uint8")

        rgba = np.zeros((size, size, 4), dtype="uint8")
        rgba[:, :, 0] = gray
        rgba[:, :, 1] = gray
        rgba[:, :, 2] = gray
        rgba[:, :, 3] = self._rounded_mask(size, size * self.CORNER_RADIUS)

        Image.fromarray(rgba, "RGBA").save(out_path, optimize=True)
        return out_path

    def _pattern(self, texture, size, rng):
        if texture == "perlin":
            return self._fbm(self._perlin, size, rng)
        if texture == "simplex":
            return self._fbm(self._simplex, size, rng)
        if texture == "worley":
            return self._worley(size, rng)
        if texture == "grain":
            return rng.random((size, size))
        if texture == "metal":
            return self._metal(size, rng)
        if texture == "carbon":
            return self._carbon(size)
        if texture == "wood":
            return self._wood(size, rng)
        if texture == "marble":
            return self._marble(size, rng)
        if texture == "dots":
            return self._dots(size)
        if texture == "grid":
            return self._grid(size)
        if texture == "stripes":
            return self._stripes(size)
        return self._waves(size)

    # --- PROCEDURAL NOISE ---

    @staticmethod
    def _grid_coords(size, freq):
        coords = (np.arange(size, dtype=np.float64) / size) * freq
        return np.meshgrid(coords, coords, indexing="ij")

    def _perlin(self, size, freq, rng):
        g = freq + 1
        ang = rng.random((g, g)) * (2.0 * np.pi)
        gx = np.cos(ang)
        gy = np.sin(ang)

        yy, xx = self._grid_coords(size, freq)
        x0 = np.clip(xx.astype(int), 0, freq - 1)
        y0 = np.clip(yy.astype(int), 0, freq - 1)
        xf = xx - x0
        yf = yy - y0

        n00 = gx[y0, x0] * xf + gy[y0, x0] * yf
        n10 = gx[y0, x0 + 1] * (xf - 1.0) + gy[y0, x0 + 1] * yf
        n01 = gx[y0 + 1, x0] * xf + gy[y0 + 1, x0] * (yf - 1.0)
        n11 = gx[y0 + 1, x0 + 1] * (xf - 1.0) + gy[y0 + 1, x0 + 1] * (yf - 1.0)

        u = _fade(xf)
        v = _fade(yf)
        nx0 = n00 * (1.0 - u) + n10 * u
        nx1 = n01 * (1.0 - u) + n11 * u
        return nx0 * (1.0 - v) + nx1 * v

    def _simplex(self, size, freq, rng):
        p = rng.permutation(256)
        perm = np.concatenate([p, p])
        perm12 = (perm % 12).astype(int)

        yy, xx = self._grid_coords(size, freq)
        f2 = 0.5 * (np.sqrt(3.0) - 1.0)
        g2 = (3.0 - np.sqrt(3.0)) / 6.0

        s = (xx + yy) * f2
        i = np.floor(xx + s)
        j = np.floor(yy + s)
        t = (i + j) * g2
        x0 = xx - (i - t)
        y0 = yy - (j - t)

        i1 = (x0 > y0).astype(int)
        j1 = 1 - i1
        x1 = x0 - i1 + g2
        y1 = y0 - j1 + g2
        x2 = x0 - 1.0 + 2.0 * g2
        y2 = y0 - 1.0 + 2.0 * g2

        ii = i.astype(int) & 255
        jj = j.astype(int) & 255
        gi0 = perm12[ii + perm[jj]]
        gi1 = perm12[ii + i1 + perm[jj + j1]]
        gi2 = perm12[ii + 1 + perm[jj + 1]]

        def contrib(gi, dx, dy):
            g = _GRAD3[gi]
            return g[:, :, 0] * dx + g[:, :, 1] * dy

        def att(dx, dy):
            tt = 0.5 - dx * dx - dy * dy
            return np.where(tt < 0.0, 0.0, tt ** 4)

        n = (att(x0, y0) * contrib(gi0, x0, y0)
             + att(x1, y1) * contrib(gi1, x1, y1)
             + att(x2, y2) * contrib(gi2, x2, y2))
        return 70.0 * n

    def _worley(self, size, rng, cells=10):
        pts = rng.random((cells * cells, 2)) * size
        c = np.arange(size, dtype=np.float64)
        yy, xx = np.meshgrid(c, c, indexing="ij")
        px = xx.ravel()
        py = yy.ravel()
        best = np.full(px.shape, np.inf)
        for cx, cy in pts:
            d = (px - cx) ** 2 + (py - cy) ** 2
            best = np.minimum(best, d)
        f1 = np.sqrt(best).reshape(size, size)
        hi = float(f1.max())
        return 1.0 - (f1 / hi if hi > 1e-12 else f1)

    def _fbm(self, fn, size, rng, octaves=4, base_freq=4):
        total = np.zeros((size, size), dtype=np.float64)
        amp = 1.0
        freq = base_freq
        norm = 0.0
        for _ in range(octaves):
            total += amp * fn(size, freq, rng)
            norm += amp
            amp *= 0.5
            freq *= 2
        return total / (norm if norm > 1e-12 else 1.0)

    def _value_noise(self, size, freq, rng):
        g = freq + 1
        grid = rng.random((g, g))
        yy, xx = self._grid_coords(size, freq)
        x0 = np.clip(xx.astype(int), 0, freq - 1)
        y0 = np.clip(yy.astype(int), 0, freq - 1)
        xf = xx - x0
        yf = yy - y0
        u = _fade(xf)
        v = _fade(yf)
        nx0 = grid[y0, x0] * (1.0 - u) + grid[y0, x0 + 1] * u
        nx1 = grid[y0 + 1, x0] * (1.0 - u) + grid[y0 + 1, x0 + 1] * u
        return nx0 * (1.0 - v) + nx1 * v

    # --- MATERIALS ---

    def _metal(self, size, rng):
        c = np.arange(size, dtype=np.float64)
        yy, xx = np.meshgrid(c, c, indexing="ij")
        brushed = np.sin(yy / size * size * np.pi * 3.0)
        fine = rng.random((size, size)) * 0.35
        wide = self._value_noise(size, 4, rng)
        return brushed * 0.6 + fine + wide * 0.4

    def _carbon(self, size):
        cell = max(2, size // 24)
        c = np.arange(size)
        yy, xx = np.meshgrid(c, c, indexing="ij")
        weave = ((xx // cell) + (yy // cell)) % 2
        streak = (((xx + yy) // cell) % 2) * 0.3
        return weave.astype(np.float64) * 0.8 + streak

    def _wood(self, size, rng):
        c = np.arange(size, dtype=np.float64)
        yy, xx = np.meshgrid(c, c, indexing="ij")
        cx = cy = size * 0.5
        d = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
        warp = self._value_noise(size, 4, rng)
        rings = np.sin(d * 0.18 + warp * 3.5)
        grain = rng.random((size, size)) * 0.15
        return rings + grain

    def _marble(self, size, rng):
        c = np.arange(size, dtype=np.float64)
        yy, xx = np.meshgrid(c, c, indexing="ij")
        turb = self._fbm(self._perlin, size, rng, octaves=3, base_freq=3)
        veins = np.sin((xx * 0.06) + np.sin(yy * 0.03) * 2.0 + turb * 6.0)
        return veins

    # --- PATTERNS ---

    @staticmethod
    def _index_grid(size):
        c = np.arange(size)
        return np.meshgrid(c, c, indexing="ij")

    def _dots(self, size):
        period = max(6, size // 8)
        w = max(2, period // 2)
        yy, xx = self._index_grid(size)
        return (((xx % period) < w) & ((yy % period) < w)).astype(np.float64)

    def _grid(self, size):
        period = max(6, size // 8)
        lw = max(1, period // 6)
        yy, xx = self._index_grid(size)
        return (((xx % period) < lw) | ((yy % period) < lw)).astype(np.float64)

    def _stripes(self, size):
        period = max(4, size // 12)
        yy, _ = self._index_grid(size)
        return ((yy % period) < (period // 2)).astype(np.float64)

    def _waves(self, size):
        c = np.arange(size, dtype=np.float64)
        yy, xx = np.meshgrid(c, c, indexing="ij")
        return (np.sin(xx * 0.12 + yy * 0.07) + 1.0) / 2.0

    # --- HELPERS ---

    @staticmethod
    def _normalize(arr):
        lo = float(arr.min())
        hi = float(arr.max())
        if hi - lo < 1e-12:
            return np.zeros_like(arr)
        return (arr - lo) / (hi - lo)

    def _rounded_mask(self, size, radius):
        ss = 4
        big = size * ss
        mask = Image.new("L", (big, big), 0)
        ImageDraw.Draw(mask).rounded_rectangle(
            (0, 0, big - 1, big - 1), radius=int(radius * ss), fill=255)
        return np.array(mask.resize((size, size), Image.LANCZOS))

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
