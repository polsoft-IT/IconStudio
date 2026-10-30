from PIL import Image
import numpy as np


class IconStyleDetector:
    def __init__(self):
        pass

    def detect_style(self, path):
        try:
            img = Image.open(path).convert("RGBA")
        except Exception:
            return "unknown"
        arr = np.array(img)
        pixels = arr.reshape(-1, 4)
        pixels = pixels[pixels[:, 3] > 10]
        if len(pixels) == 0:
            return "unknown"
        brightness = np.mean(pixels[:, :3])
        max_rgb = np.max(pixels[:, :3], axis=1)
        min_rgb = np.min(pixels[:, :3], axis=1)
        saturation = np.mean(max_rgb - min_rgb)
        unique_colors = len(np.unique(pixels[:, :3], axis=0))
        edges = self._estimate_edges(img)
        if unique_colors < 8 and saturation < 20:
            return "monochrome"
        if edges > 0.15 and saturation > 40:
            return "classic"
        if brightness > 150 and saturation < 60:
            return "fluent"
        return "classic"

    def _estimate_edges(self, img):
        gray = img.convert("L")
        arr = np.array(gray)
        diff_h = np.abs(arr[:, 1:].astype(int) - arr[:, :-1].astype(int))
        diff_v = np.abs(arr[1:, :].astype(int) - arr[:-1, :].astype(int))
        edges = np.mean(diff_h) + np.mean(diff_v)
        edges /= 255.0
        return edges
