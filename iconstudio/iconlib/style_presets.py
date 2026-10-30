from PIL import Image, ImageEnhance
import numpy as np
import os


class IconStylePresets:
    def __init__(self):
        pass

    def apply_preset(self, src_path, out_path, preset):
        img = Image.open(src_path).convert("RGBA")
        if preset == "fluent_light":
            img = self._fluent_light(img)
        elif preset == "fluent_dark":
            img = self._fluent_dark(img)
        elif preset == "monochrome":
            img = self._monochrome(img)
        elif preset == "high_contrast":
            img = self._high_contrast(img)
        elif preset == "pastel":
            img = self._pastel(img)
        elif preset == "classic_xp":
            img = self._classic_xp(img)
        img.save(out_path)
        return out_path

    def _fluent_light(self, img):
        img = ImageEnhance.Brightness(img).enhance(1.25)
        img = ImageEnhance.Color(img).enhance(0.65)
        return img

    def _fluent_dark(self, img):
        img = ImageEnhance.Brightness(img).enhance(0.75)
        img = ImageEnhance.Color(img).enhance(0.55)
        return img

    def _monochrome(self, img):
        arr = np.array(img)
        gray = np.mean(arr[:, :, :3], axis=2)
        mono = np.stack([gray, gray, gray, arr[:, :, 3]], axis=2)
        return Image.fromarray(mono.astype("uint8"), "RGBA")

    def _high_contrast(self, img):
        img = ImageEnhance.Contrast(img).enhance(1.8)
        img = ImageEnhance.Color(img).enhance(1.4)
        return img

    def _pastel(self, img):
        img = ImageEnhance.Brightness(img).enhance(1.15)
        img = ImageEnhance.Color(img).enhance(0.55)
        img = ImageEnhance.Contrast(img).enhance(0.85)
        return img

    def _classic_xp(self, img):
        arr = np.array(img)
        gray = np.mean(arr[:, :, :3], axis=2)
        edges = np.abs(np.diff(gray, axis=0))
        edges = np.pad(edges, ((1, 0), (0, 0)), mode="constant")
        outline = (edges > 25).astype("uint8") * 255
        outline = np.stack([outline, outline, outline, arr[:, :, 3]], axis=2)
        combined = arr.copy()
        combined[:, :, :3] = np.maximum(combined[:, :, :3], outline[:, :, :3])
        img = Image.fromarray(combined.astype("uint8"), "RGBA")
        img = ImageEnhance.Color(img).enhance(1.3)
        return img
