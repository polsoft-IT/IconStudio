from PIL import Image, ImageEnhance, ImageFilter
import numpy as np
import os

DPI_SIZES = [16, 24, 32, 48, 64, 128, 256]


class IconNormalizer:
    def __init__(self):
        pass

    def normalize(self, src_path, out_path, target_style="fluent"):
        img = Image.open(src_path).convert("RGBA")
        img = self._normalize_size(img)
        dpi_icons = self._normalize_dpi(img)
        if target_style == "fluent":
            dpi_icons = [self._normalize_fluent(i) for i in dpi_icons]
        elif target_style == "classic":
            dpi_icons = [self._normalize_classic(i) for i in dpi_icons]
        elif target_style == "monochrome":
            dpi_icons = [self._normalize_monochrome(i) for i in dpi_icons]
        largest = max(dpi_icons, key=lambda i: i.size[0])
        largest.save(
            out_path,
            format="ICO",
            sizes=[(s, s) for s in DPI_SIZES]
        )
        return out_path

    def _normalize_size(self, img):
        w, h = img.size
        if w < 256 or h < 256:
            img = img.resize((256, 256), Image.LANCZOS)
            img = img.filter(ImageFilter.SMOOTH_MORE)
        if w > 512 or h > 512:
            img = img.resize((512, 512), Image.LANCZOS)
        return img

    def _normalize_dpi(self, img):
        icons = []
        for size in DPI_SIZES:
            resized = img.resize((size, size), Image.LANCZOS)
            icons.append(resized)
        return icons

    def _normalize_fluent(self, img):
        img = ImageEnhance.Brightness(img).enhance(1.15)
        img = ImageEnhance.Color(img).enhance(0.65)
        img = ImageEnhance.Contrast(img).enhance(0.85)
        img = img.filter(ImageFilter.SMOOTH_MORE)
        return img

    def _normalize_classic(self, img):
        img = ImageEnhance.Contrast(img).enhance(1.4)
        img = ImageEnhance.Color(img).enhance(1.3)
        img = ImageEnhance.Sharpness(img).enhance(1.2)
        return img

    def _normalize_monochrome(self, img):
        arr = np.array(img)
        gray = np.mean(arr[:, :, :3], axis=2)
        mono = np.stack([gray, gray, gray, arr[:, :, 3]], axis=2)
        return Image.fromarray(mono.astype("uint8"), "RGBA")
