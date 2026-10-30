import numpy as np
from PIL import Image


class IconStyleAnalysis:
    def __init__(self):
        pass

    # --- MAIN ENTRY POINT ---

    def analyze(self, path):
        img = Image.open(path).convert("RGBA")
        arr = np.array(img)

        # remove transparent pixels
        px = arr.reshape(-1, 4)
        px = px[px[:, 3] > 10]

        if px.shape[0] == 0:
            return {
                "unique_colors": 0,
                "brightness": 0.0,
                "saturation": 0.0,
                "outline": False,
                "gradient": False,
                "shading": False,
                "style": "unknown",
            }

        # --- COLOR METRICS ---
        unique_colors = int(len(np.unique(px[:, :3], axis=0)))
        brightness = float(np.mean(px[:, :3]))
        max_rgb = np.max(px[:, :3], axis=1)
        min_rgb = np.min(px[:, :3], axis=1)
        saturation = float(np.mean(max_rgb - min_rgb))

        # --- OUTLINE DETECTION ---
        outline = self._detect_outline(arr)

        # --- GRADIENT DETECTION ---
        gradient = self._detect_gradient(arr)

        # --- SHADING DETECTION ---
        shading = self._detect_shading(arr)

        # --- STYLE CLASSIFICATION ---
        style = self._classify_style(unique_colors, saturation, gradient, shading, outline)

        return {
            "unique_colors": unique_colors,
            "brightness": brightness,
            "saturation": saturation,
            "outline": outline,
            "gradient": gradient,
            "shading": shading,
            "style": style,
        }

    # --- OUTLINE DETECTION ---

    def _detect_outline(self, arr):
        gray = np.mean(arr[:, :, :3], axis=2)
        edges = np.abs(gray[:, 1:] - gray[:, :-1]).mean() + np.abs(gray[1:, :] - gray[:-1, :]).mean()
        return bool(edges > 20)

    # --- GRADIENT DETECTION ---

    def _detect_gradient(self, arr):
        h, w, _ = arr.shape
        left = np.mean(arr[:, :w // 2, :3])
        right = np.mean(arr[:, w // 2:, :3])
        diff = abs(left - right)
        return bool(diff > 15)

    # --- SHADING DETECTION (3D) ---

    def _detect_shading(self, arr):
        blur = np.mean(arr[:, :, :3]) - np.mean(arr[:, :, :3].astype(float) * 0.9)
        return bool(blur > 5)

    # --- STYLE CLASSIFICATION ---

    def _classify_style(self, unique_colors, saturation, gradient, shading, outline):
        # Fluent 3D
        if shading and gradient and unique_colors > 20:
            return "fluent3d"

        # Fluent 2D
        if gradient and saturation < 60 and unique_colors < 20:
            return "fluent2d"

        # Skeuomorphic
        if shading and unique_colors > 50:
            return "skeuomorphic"

        # Classic
        if unique_colors > 30 and saturation > 80:
            return "classic"

        # Monochrome
        if unique_colors < 5 and saturation < 20:
            return "monochrome"

        # Outline
        if outline and unique_colors < 10:
            return "outline"

        # Glyph
        if unique_colors < 8 and saturation < 40:
            return "glyph"

        return "unknown"
