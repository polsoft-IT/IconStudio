import numpy as np
from PIL import Image


class IconColorAnalysis:
    """Analyzes dominant colors and palette of an icon."""

    def __init__(self):
        pass

    # --- MAIN ENTRY POINT ---

    def analyze(self, path):
        img = Image.open(path).convert("RGBA")
        arr = np.array(img)

        px = arr.reshape(-1, 4)
        px = px[px[:, 3] > 10]

        if px.shape[0] == 0:
            return {
                "palette": [(255, 255, 255)],
                "dominant": (255, 255, 255),
                "color_count": 0,
                "brightness": 0.0,
                "saturation": 0.0,
            }

        colors = px[:, :3]
        max_rgb = np.max(colors, axis=1)
        min_rgb = np.min(colors, axis=1)

        brightness = float(np.mean(colors))
        saturation = float(np.mean(max_rgb - min_rgb))

        palette = self._palette(colors, k=4)
        dominant = palette[0] if palette else (255, 255, 255)

        return {
            "palette": palette,
            "dominant": dominant,
            "color_count": int(len(np.unique(colors, axis=0))),
            "brightness": brightness,
            "saturation": saturation,
        }

    # --- PALETTE EXTRACTION ---

    def _palette(self, colors, k=4):
        # quantize to reduce noise, then count occurrences
        quant = (colors // 16) * 16
        keys, counts = np.unique(quant, axis=0, return_counts=True)
        order = np.argsort(-counts)

        palette = []
        for idx in order[:k]:
            r, g, b = keys[idx]
            palette.append((int(r), int(g), int(b)))
        return palette
